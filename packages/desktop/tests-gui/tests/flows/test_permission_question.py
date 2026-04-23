"""Coverage for /permission/* and /question/* sidecar routes.

Routes covered (see
``docs/coverage-expansion/inventory/sidecar-routes.md`` lines 210-223):

  - GET  /permission
  - POST /permission/{requestID}/reply
  - GET  /question
  - POST /question/{requestID}/reply
  - POST /question/{requestID}/reject

Config note (G1.5 inventory line 91 + 357, and
``packages/desktop/src-tauri/src/gpd_setup.rs:454``):
  GPD seeds the user's opencode config with ``"permission": "allow"``.
  That means the sidecar never produces a ``permission.asked`` event in
  default operation, so the list and lifecycle reach an empty-state
  terminal quickly. The routes themselves are still reachable and their
  response shape is part of the public contract — we pin that shape here.

Tests in this file that require the sidecar to actually surface a prompt
(i.e. end-to-end lifecycle write-through) are skipped with a reason that
names the config flag which would unlock them. Per the task constraints
we do NOT flip the permission mode — that would change user-visible app
behaviour.
"""
from __future__ import annotations

import httpx
import pytest


# ---------------------------------------------------------------------------
# /permission
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_permissions_list_shape(http):
    """GET /permission returns an array.

    Default config is ``permission: allow`` so the server-side Permission
    store is typically empty. Shape is what we care about: a JSON array,
    each entry (if any) conforming to ``Permission.Request``.
    """
    result = http.permissions()

    assert isinstance(result, list), (
        f"GET /permission must return a list, got {type(result).__name__}: "
        f"{result!r}"
    )

    # If the list is non-empty (a prior test left a pending prompt, or a
    # dev has permission: ask in their config) verify the entry shape. Per
    # Permission.Request in packages/opencode/src/permission/index.ts:42:
    #   { id, sessionID, permission, patterns, metadata, always, tool? }
    required_keys = {"id", "sessionID", "permission", "patterns", "metadata", "always"}
    for entry in result:
        assert isinstance(entry, dict), f"entry not a dict: {entry!r}"
        missing = required_keys - set(entry.keys())
        assert not missing, f"Permission.Request missing keys {missing}: {entry!r}"
        assert isinstance(entry["patterns"], list)
        assert isinstance(entry["always"], list)
        assert isinstance(entry["metadata"], dict)


@pytest.mark.flows
def test_permission_reply_to_missing_id_returns_error(http):
    """POST /permission/:id/reply on an unknown id must not silently succeed.

    We can't reliably create a real pending permission without flipping
    ``permission: allow`` off (out of scope here), but we CAN verify the
    reply route rejects unknown ids — that's enough to prove the POST path,
    validator, and error-response shape are wired.

    Acceptable error statuses: 400 (validator) or 404 (not found). The
    server at ``instance/permission.ts:12`` declares both via ``errors(400,
    404)``. Some builds surface 500 for unrecognised PermissionID shapes;
    we tolerate 5xx here to stay shape-focused rather than locking in a
    specific error contract the server may tighten later.
    """
    bogus_id = "permission_00000000000000000000000000"

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        http.permission_reply(bogus_id, reply="once")

    status = exc_info.value.response.status_code
    assert status >= 400, f"unexpected success status {status}"
    # Narrow the contract assertion without over-fitting: anything in the
    # declared error set (400/404) OR a 5xx that tells us the server
    # short-circuited on the unknown id is fine.
    assert status in (400, 404) or 500 <= status < 600, (
        f"unexpected status {status} for bogus permission id reply"
    )


@pytest.mark.skip(
    reason=(
        "Producing a real pending permission requires the sidecar config to be "
        "'permission: ask' (or per-tool 'ask'). GPD ships with 'permission: "
        "allow' (packages/desktop/src-tauri/src/gpd_setup.rs:454), so the "
        "permission-prompt lifecycle is not user-visible in the shipped app. "
        "To unlock this test locally, patch the seeded opencode.json to set "
        "'permission: ask' (or use ~/.config/opencode/config.json), relaunch "
        "GPD, and trigger a tool call (e.g. Bash)."
    )
)
@pytest.mark.flows
@pytest.mark.real_backend
def test_permission_prompt_lifecycle_ask_reply_observe(http, gpd_key):
    """Full state-machine test: ask -> read from list -> reply -> list empties.

    Flow (when permission mode is 'ask'):
      1. Create session.
      2. send_message asking the model to run a Bash command.
      3. Poll GET /permission until a Permission.Request for our session
         appears.
      4. POST /permission/:id/reply {reply: 'reject'}.
      5. Poll GET /permission until that id disappears (reply drained it).
    """
    pass  # pragma: no cover - gated by @pytest.mark.skip


# ---------------------------------------------------------------------------
# /question
# ---------------------------------------------------------------------------


@pytest.mark.flows
def test_questions_list_shape(http):
    """GET /question returns an array.

    Pending questions require an in-flight LLM call that chose to use the
    ``question`` tool — without a live prompt, the list is empty. This test
    pins the empty-state contract (array, not dict / not 404) so it never
    silently regresses.
    """
    result = http.questions()
    assert isinstance(result, list), (
        f"GET /question must return a list, got {type(result).__name__}: "
        f"{result!r}"
    )

    # If the list is non-empty (a prior test / live session left one),
    # verify the Question.Request shape
    # (packages/opencode/src/question/index.ts:62):
    #   { id, sessionID, questions: QuestionInfo[], tool? }
    required_keys = {"id", "sessionID", "questions"}
    for entry in result:
        assert isinstance(entry, dict), f"entry not a dict: {entry!r}"
        missing = required_keys - set(entry.keys())
        assert not missing, f"Question.Request missing keys {missing}: {entry!r}"
        assert isinstance(entry["questions"], list)
        for q in entry["questions"]:
            assert "question" in q and "header" in q and "options" in q, (
                f"QuestionInfo missing keys: {q!r}"
            )


@pytest.mark.flows
def test_question_reply_to_missing_id_returns_error(http):
    """POST /question/:id/reply on an unknown id must error, not succeed silently."""
    bogus_id = "question_00000000000000000000000000"

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        http.question_reply(bogus_id, answers=[["some-label"]])

    status = exc_info.value.response.status_code
    assert status in (400, 404) or 500 <= status < 600, (
        f"unexpected status {status} for bogus question id reply"
    )


@pytest.mark.flows
def test_question_reject_missing_id_returns_error(http):
    """POST /question/:id/reject on an unknown id must error.

    The reject route has no json validator (see question.ts:80) so it
    fails on the PermissionID-style id shape parse or on lookup miss.
    """
    bogus_id = "question_00000000000000000000000000"

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        http.question_reject(bogus_id)

    status = exc_info.value.response.status_code
    assert status in (400, 404) or 500 <= status < 600, (
        f"unexpected status {status} for bogus question id reject"
    )


@pytest.mark.skip(
    reason=(
        "A real Question.Request is produced only when a live model chooses to "
        "invoke the 'question' tool mid-generation. That is non-deterministic "
        "with stock Anthropic models and needs either a scripted mock provider "
        "or a prompt known to trigger the tool. This is out of scope for G3.5 "
        "(shape-only coverage); revisit under G5 (tool flows) with a "
        "deterministic test harness."
    )
)
@pytest.mark.flows
@pytest.mark.real_backend
def test_question_prompt_lifecycle_ask_reply_observe(http, gpd_key):
    """Full state-machine test: model asks question -> reply -> list empties."""
    pass  # pragma: no cover - gated by @pytest.mark.skip
