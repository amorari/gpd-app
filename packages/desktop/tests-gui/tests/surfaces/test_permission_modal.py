"""UI coverage for the tool-call permission modal (surfaces tier).

Context
-------
``tests/flows/test_permission_question.py`` already pins the *HTTP* contract
of ``/permission`` — shape of GET, lifecycle of reply, error status on unknown
ids. None of that exercises the **webview UI** that is supposed to render a
modal when the sidecar emits a ``permission.asked`` event. This file closes
that gap, or — more accurately — documents the product hooks that must land
before the gap *can* be closed.

Status of the coverage gap at authoring time (2026-04-22)
---------------------------------------------------------
Two product-side pieces are missing:

1. **A renderable permission modal in ``packages/desktop/src/``.**
   The opencode TUI (``cli/cmd/tui/context/sync.tsx``) and the ACP agent
   (``acp/agent.ts``) both handle ``permission.asked`` events and render
   their own prompts, but the GPD Tauri webview does not. A codebase-wide
   search for ``permission-modal``/``PermissionModal``/``Permission.Request``
   returns zero hits under ``packages/desktop/src/``. So even if a request
   were induced, there is no DOM anchor to query.

2. **A sidecar test hook to *induce* a pending permission without a live
   tool call.**  GPD ships with ``permission: "allow"`` baked into
   ``gpd_setup.rs:494``; opencode only produces a ``Permission.Request``
   when a model actually invokes a non-allow-listed tool. Without either
   a ``permission: ask`` override or an explicit ``POST /permission/__induce``
   harness route, the only way to produce one is to (a) flip user-visible
   config and (b) drive a real LLM tool-call through Bash — both outside
   the purview of a surfaces-tier test.

Every test below is therefore ``xfail(strict=True)``. When either hook
lands, the corresponding xfail flips to XPASS and pytest fails the run,
forcing a deliberate un-gating commit rather than silent green drift.
"""
from __future__ import annotations

import time

import pytest

from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)


# ---------------------------------------------------------------------------
# Shared reasons — keep verbatim across the four xfails so the CI audit log
# groups them as "same missing hook, four call sites".
# ---------------------------------------------------------------------------

_REASON_NO_MODAL = (
    "GPD desktop webview has no permission-modal UI: a repo-wide grep for "
    "'permission-modal' / 'PermissionModal' / 'Permission.Request' returns "
    "zero hits under packages/desktop/src/. The opencode TUI and ACP agent "
    "render their own prompts; the Tauri SPA does not. Product hook missing: "
    "a SolidJS <PermissionModal> component listening for permission.asked on "
    "the event bus, mounted inside the session surface, with stable "
    "data-component=\"permission-modal\" and data-action=\"permission-allow\"/"
    "\"permission-deny\" anchors."
)

_REASON_NO_INDUCE_HOOK = (
    "GPD ships with permission: 'allow' (packages/desktop/src-tauri/src/"
    "gpd_setup.rs:494), so the sidecar never produces a Permission.Request in "
    "the default config a surfaces test runs against. Product hook missing: "
    "either (a) a ``permission: ask`` override flag we can flip per-test "
    "without mutating the seeded user config, or (b) a harness-only "
    "POST /permission/__induce route on the sidecar that synthesises a "
    "Permission.Request for a given sessionID and tool name, returning the "
    "id so the UI test can assert modal render / click Allow / click Deny."
)

_REASON_NEEDS_BOTH = (
    f"{_REASON_NO_MODAL}\n\nAND\n\n{_REASON_NO_INDUCE_HOOK}"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_route(path: str) -> str:
    return route_session_in_project(encode_dir_token(path))


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    """On-disk directory GPD will accept as a project (git-free is fine here)."""
    p = tmp_path_factory.mktemp("gpd_perm_modal")
    p = p.resolve()
    (p / "README.md").write_text("# permission-modal test project\n")
    return str(p)


def _induce_pending_permission(http, session_id: str, tool: str = "bash", args: dict | None = None) -> str:
    """Attempt to induce a pending Permission.Request for ``session_id``.

    There is no supported way to do this today. We try the hypothetical
    ``/permission/__induce`` harness route and fall back to raising
    ``NotImplementedError`` so the caller xfails with the canonical reason.
    If/when a real hook lands, this helper should be rewritten and the xfails
    on the four tests below removed (they should flip to XPASS and the CI
    suite will force the un-gating commit).
    """
    try:
        body = {"sessionID": session_id, "tool": tool, "args": args or {}}
        result = http._post("/permission/__induce", json=body)  # type: ignore[attr-defined]
    except Exception as e:  # route not present, 404, etc.
        raise NotImplementedError(
            f"no permission-induce hook on sidecar ({type(e).__name__}: {e})"
        ) from e
    if not isinstance(result, dict) or "id" not in result:
        raise NotImplementedError(
            f"permission-induce hook returned unexpected shape: {result!r}"
        )
    return str(result["id"])


def _poll_modal_gone(mcp, timeout_s: float = 3.0, interval_s: float = 0.1) -> bool:
    """Poll the DOM for up to ``timeout_s`` for the permission-modal to unmount.

    Click handlers that flip the modal closed do so asynchronously (event
    bus -> signal -> re-render). Asserting immediately after ``btn.click()``
    races the SolidJS scheduler and will flake. This helper polls with a short
    interval so the assertion only fires once the DOM has had a chance to
    converge — or once the deadline passes, at which point the caller asserts
    ``False`` and fails with the expected message.
    """
    gone_js = (
        '!document.querySelector(\'[data-component="permission-modal"]\')'
    )
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw = str(mcp.execute_js(gone_js) or "").strip().lower()
        if raw == "true":
            return True
        time.sleep(interval_s)
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.surfaces
@pytest.mark.xfail(strict=True, reason=_REASON_NEEDS_BOTH)
def test_permission_modal_renders_on_pending_request(mcp, http, prepared_project_path):
    """A pending Permission.Request should materialise a modal in the session surface.

    Flow:
      1. Create/navigate to a session.
      2. Induce a pending permission via the (missing) sidecar hook.
      3. Assert ``[data-component="permission-modal"]`` or a
         ``[role="dialog"]`` whose textContent matches /permission|allow|deny/i
         is visible in the session DOM.

    xfails with :data:`_REASON_NEEDS_BOTH` today.
    """
    # Navigate first so the session surface is mounted when/if the modal spawns.
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)

    # Always create a fresh session — reusing sessions[0] would skip the
    # title round-trip and leak permissions across tests. Attach a known
    # title so failures point to the right session.
    created = http.create_session(directory=prepared_project_path)
    session_id = created["id"]
    http.patch_session(session_id, {"title": "permission-modal-test"})

    # Attempt to induce. Without the product hook, this raises and the test
    # fails — which, combined with xfail(strict=True), is the signal we want.
    perm_id = _induce_pending_permission(http, session_id)

    # Would poll DOM for the modal here once the product hook lands.
    js = (
        '(() => {'
        '  const sel = document.querySelector('
        '    \'[data-component="permission-modal"], [role="dialog"]\');'
        '  if (!sel) return false;'
        '  const t = (sel.textContent || "").toLowerCase();'
        '  return /permission|allow|deny/.test(t);'
        '})()'
    )
    raw = str(mcp.execute_js(js) or "").strip().lower()
    assert raw == "true", (
        f"permission-modal not visible for induced request {perm_id!r}"
    )


@pytest.mark.surfaces
@pytest.mark.real_backend
@pytest.mark.xfail(strict=True, reason=_REASON_NEEDS_BOTH)
def test_permission_modal_allow_resolves_via_ui_click(
    mcp, http, os_input, gpd_key, prepared_project_path
):
    """Clicking the modal's Allow button should reply to the sidecar and close it.

    Flow:
      1. Induce a pending permission.
      2. Navigate to the session.
      3. Click ``[data-action="permission-allow"]`` via el.click() (fallback
         to ``os_input.click_at`` if the button is offscreen).
      4. Assert the modal unmounts AND ``http.permissions()`` no longer
         contains ``perm_id``.

    xfails because neither the UI nor the induce hook exists.
    """
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)

    created = http.create_session(directory=prepared_project_path)
    session_id = created["id"]
    http.patch_session(session_id, {"title": "permission-allow-test"})

    perm_id = _induce_pending_permission(http, session_id, tool="bash")

    # Click Allow. Would switch to os_input.click_at with element bbox if
    # el.click() is flaky due to z-index / pointer-events quirks.
    click_js = (
        '(() => {'
        '  const btn = document.querySelector(\'[data-action="permission-allow"]\');'
        '  if (!btn) return false;'
        '  btn.click();'
        '  return true;'
        '})()'
    )
    clicked = str(mcp.execute_js(click_js) or "").strip().lower()
    assert clicked == "true", "permission-allow button not found in modal"

    # Modal should unmount and the sidecar list should drop the id. The click
    # handler is async (event bus -> signal -> re-render) so we poll briefly
    # instead of asserting on the immediate post-click DOM — immediate-assert
    # races SolidJS's scheduler and flakes.
    assert _poll_modal_gone(mcp, timeout_s=3.0), (
        "permission-modal still mounted after Allow click"
    )

    still_pending = [p for p in http.permissions() if p.get("id") == perm_id]
    assert not still_pending, (
        f"permission id {perm_id} still in /permission list after UI Allow"
    )


@pytest.mark.surfaces
@pytest.mark.real_backend
@pytest.mark.xfail(strict=True, reason=_REASON_NEEDS_BOTH)
def test_permission_modal_deny_aborts_via_ui_click(
    mcp, http, os_input, gpd_key, prepared_project_path
):
    """Mirror of the Allow test: clicking Deny must send reply=reject and close."""
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)

    created = http.create_session(directory=prepared_project_path)
    session_id = created["id"]
    http.patch_session(session_id, {"title": "permission-deny-test"})

    perm_id = _induce_pending_permission(http, session_id, tool="bash")

    click_js = (
        '(() => {'
        '  const btn = document.querySelector(\'[data-action="permission-deny"]\');'
        '  if (!btn) return false;'
        '  btn.click();'
        '  return true;'
        '})()'
    )
    clicked = str(mcp.execute_js(click_js) or "").strip().lower()
    assert clicked == "true", "permission-deny button not found in modal"

    # Poll for unmount rather than asserting immediately — see allow-test for
    # the async-scheduler rationale.
    assert _poll_modal_gone(mcp, timeout_s=3.0), (
        "permission-modal still mounted after Deny click"
    )

    still_pending = [p for p in http.permissions() if p.get("id") == perm_id]
    assert not still_pending, (
        f"permission id {perm_id} still in /permission list after UI Deny"
    )


@pytest.mark.surfaces
@pytest.mark.xfail(strict=True, reason=_REASON_NEEDS_BOTH)
def test_permission_modal_arguments_render_as_text_not_html(
    mcp, http, prepared_project_path
):
    """Security: tool args must be rendered as TEXT, not injected as HTML.

    Induces a permission request whose tool arguments include a
    ``<script>alert(1)</script>`` payload, then asserts:

      1. The literal string ``<script>alert(1)</script>`` is visible in the
         modal's rendered text (``textContent``).
      2. The modal's ``innerHTML`` does NOT contain ``<script``
         (case-insensitive).

    This guards against a classic XSS regression where a naive ``innerHTML =
    ...`` or an unsanitised ``<div innerHTML={arg}>`` in the modal would
    execute attacker-controlled script tags embedded in tool arguments.
    """
    Navigator(mcp).go(_session_route(prepared_project_path), timeout_s=5.0)

    created = http.create_session(directory=prepared_project_path)
    session_id = created["id"]
    http.patch_session(session_id, {"title": "permission-xss-test"})

    payload = "<script>alert(1)</script>"
    perm_id = _induce_pending_permission(
        http, session_id, tool="bash", args={"command": payload}
    )

    # Would poll until modal appears, then inspect both textContent (must
    # contain payload verbatim) and innerHTML (must NOT contain a live
    # <script> tag).
    js = (
        '(() => {'
        '  const m = document.querySelector(\'[data-component="permission-modal"]\');'
        '  if (!m) return {found: false};'
        '  return {'
        '    found: true,'
        '    textHasPayload: (m.textContent || "").includes('
        '      "<script>alert(1)</script>"),'
        '    htmlHasLiveScript: /<script/i.test(m.innerHTML || ""),'
        '  };'
        '})()'
    )
    result = mcp.execute_js(js)
    # execute_js returns either a dict (JSON round-trip) or a JSON string
    # depending on MCP bridge version; normalise defensively.
    if isinstance(result, str):
        import json as _json
        try:
            result = _json.loads(result)
        except _json.JSONDecodeError:
            result = {"found": False}

    assert isinstance(result, dict) and result.get("found"), (
        f"permission-modal not mounted for induced request {perm_id!r}"
    )
    assert result.get("textHasPayload"), (
        "modal textContent does not include the literal payload — tool arg "
        "may have been HTML-unescaped away before render"
    )
    assert not result.get("htmlHasLiveScript"), (
        "modal innerHTML contains <script — tool args are being injected as "
        "HTML. This is an XSS regression."
    )
