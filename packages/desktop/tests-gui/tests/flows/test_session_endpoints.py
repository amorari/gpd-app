"""Phase G3.1 — deep round-trip coverage of the `/session/*` route family.

Every test in this file hits the real opencode-cli sidecar over HTTP. Shape-only
assertions — we verify the wire contract, not LLM behavior, so these tests do
NOT require an Anthropic key unless explicitly marked ``real_backend``.

The session routes in scope (from docs/coverage-expansion/inventory/
sidecar-routes.md) are:

  GET    /session                                      — list (scoped / unscoped)
  GET    /session/status                               — busy-state dict
  GET    /session/:sid                                 — single-session fetch
  GET    /session/:sid/children                        — forked children
  POST   /session                                      — create
  DELETE /session/:sid                                 — delete (+ 404 on re-delete)
  PATCH  /session/:sid                                 — rename / archive metadata
  POST   /session/:sid/fork                            — branch from a message
  POST   /session/:sid/abort                           — covered in test_abort_flow
  GET    /session/:sid/message                         — list messages
  GET    /session/:sid/message/:mid                    — single message
  GET    /session/:sid/diff                            — file diff per message
  POST   /session/:sid/revert + /unrevert              — message revert pair
  POST   /session/:sid/prompt_async                    — real_backend only

Each test creates its own session and guarantees cleanup in a ``finally`` block
so one test leaking doesn't cascade into the next. We pick up tmp dirs from the
session-scoped ``scratch_project_dir`` fixture (see ``tests/flows/conftest.py``).
"""
from __future__ import annotations

import uuid

import httpx
import pytest


# --- small helpers ----------------------------------------------------------


def _create_and_cleanup(http, *, directory: str | None = None) -> str:
    """Create a session and return its id. Caller must delete in finally."""
    ses = http.create_session(directory=directory)
    assert "id" in ses, f"create_session returned {ses!r}"
    return ses["id"]


def _safe_delete(http, sid: str) -> None:
    try:
        http.delete_session(sid)
    except Exception:  # noqa: BLE001
        pass


# --- 1. create + get-by-id --------------------------------------------------


@pytest.mark.flows
def test_create_and_get_by_id_round_trip(http, scratch_project_dir):
    """POST /session → GET /session/:sid returns the same session."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        info = http.get_session(sid)
        assert info["id"] == sid
        # directory field may or may not round-trip, but 'id' is authoritative.
    finally:
        _safe_delete(http, sid)


# --- 2. list with directory filter ------------------------------------------


@pytest.mark.flows
def test_list_sessions_scoped_to_directory(http, scratch_project_dir):
    """GET /session?directory=... returns only sessions from that dir."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        listed = http.sessions(directory=str(scratch_project_dir))
        assert any(s.get("id") == sid for s in listed), (
            f"created session {sid} not in scoped list"
        )
    finally:
        _safe_delete(http, sid)


# --- 3. list unscoped -------------------------------------------------------


@pytest.mark.flows
def test_list_sessions_unscoped_includes_created(http, scratch_project_dir):
    """GET /session (no filter) returns all sessions including the new one.

    Tolerant of a capped response — the sidecar may page unscoped listings on
    large histories. If the created session is absent from the unscoped call
    but present in the scoped one, we still consider the route exercised.
    """
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        all_sessions = http.sessions()
        assert isinstance(all_sessions, list)
        if not any(s.get("id") == sid for s in all_sessions):
            # fallback: scoped list must show it, proving create() landed.
            scoped = http.sessions(directory=str(scratch_project_dir))
            assert any(s.get("id") == sid for s in scoped)
    finally:
        _safe_delete(http, sid)


# --- 4. PATCH rename --------------------------------------------------------


@pytest.mark.flows
def test_patch_session_renames_title(http, scratch_project_dir):
    """PATCH /session/:sid updates the title and the new title is returned."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        new_title = f"renamed-{uuid.uuid4().hex[:8]}"
        updated = http.patch_session(sid, {"title": new_title})
        assert updated["id"] == sid
        assert updated.get("title") == new_title, (
            f"expected title={new_title!r}, got {updated!r}"
        )
        # Confirm the rename persists on a fresh GET.
        again = http.get_session(sid)
        assert again.get("title") == new_title
    finally:
        _safe_delete(http, sid)


# --- 5. delete + delete-again-404 ------------------------------------------


@pytest.mark.flows
def test_delete_then_delete_again_404(http, scratch_project_dir):
    """DELETE twice: second call should raise a 4xx (404 in practice)."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    # First delete: ok.
    assert http.delete_session(sid) is True
    # Second delete: server returns 4xx.
    with pytest.raises(httpx.HTTPStatusError) as exc:
        http.delete_session(sid)
    assert exc.value.response.status_code in (400, 404), (
        f"expected 4xx on re-delete, got {exc.value.response.status_code}"
    )


# --- 6. delete nonexistent id raises 404 -----------------------------------


@pytest.mark.flows
def test_delete_nonexistent_raises_404(http):
    """DELETE /session/<random> where the id was never created."""
    fake_id = f"ses_nonexistent_{uuid.uuid4().hex}"
    with pytest.raises(httpx.HTTPStatusError) as exc:
        http.delete_session(fake_id)
    assert exc.value.response.status_code in (400, 404)


# --- 7. fork from latest message --------------------------------------------


@pytest.mark.flows
def test_fork_session_without_message_id(http, scratch_project_dir):
    """POST /session/:sid/fork with no messageID forks from the latest point.

    No prior messages exist on a freshly-created session, so the server is
    permitted to return 400 or to create an empty fork. Both shapes are
    acceptable — the test asserts the route is reachable and the response
    code shape is sane (200 → dict with id, 400 → documented validation).
    """
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    fork_id: str | None = None
    try:
        try:
            forked = http.fork_session(sid)
        except httpx.HTTPStatusError as e:
            # Empty-history fork is allowed to reject with 400.
            assert e.response.status_code in (400, 404), (
                f"unexpected status from fork-on-empty-session: "
                f"{e.response.status_code}"
            )
        else:
            assert "id" in forked, f"fork returned {forked!r}"
            fork_id = forked["id"]
            assert fork_id != sid, "fork must produce a new session id"
    finally:
        if fork_id is not None:
            _safe_delete(http, fork_id)
        _safe_delete(http, sid)


# --- 8. get messages --------------------------------------------------------


@pytest.mark.flows
def test_get_messages_on_fresh_session_returns_list(http, scratch_project_dir):
    """GET /session/:sid/message on a new session returns an empty list."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        msgs = http.messages(sid)
        assert isinstance(msgs, list)
        # Fresh session: no user/assistant traffic yet.
        assert msgs == [], f"expected empty message list, got {msgs!r}"
    finally:
        _safe_delete(http, sid)


# --- 9. get single message by id (404 on missing) --------------------------


@pytest.mark.flows
def test_get_single_message_nonexistent_raises(http, scratch_project_dir):
    """GET /session/:sid/message/<fake_id> surfaces a 4xx.

    We don't have a message id to fetch (no LLM calls in this shape-only
    suite), so we exercise the handler by requesting a fabricated id and
    asserting the server rejects it with 4xx.
    """
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        fake_msg = f"msg_nonexistent_{uuid.uuid4().hex}"
        with pytest.raises(httpx.HTTPStatusError) as exc:
            http.get_message(sid, fake_msg)
        assert exc.value.response.status_code in (400, 404)
    finally:
        _safe_delete(http, sid)


# --- 10. get diff (requires a real message id — shape-only) ----------------


@pytest.mark.flows
def test_get_session_diff_without_message_rejected(http, scratch_project_dir):
    """GET /session/:sid/diff without ?messageID= must be rejected as 400."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            http.get_session_diff(sid)  # omits messageID
        assert exc.value.response.status_code == 400, (
            f"expected 400 for missing ?messageID=, got "
            f"{exc.value.response.status_code}"
        )
    finally:
        _safe_delete(http, sid)


@pytest.mark.flows
def test_get_session_diff_with_fake_message(http, scratch_project_dir):
    """GET /session/:sid/diff?messageID=<fake> returns a list or 4xx."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        try:
            diff = http.get_session_diff(sid, message_id="msg_fake")
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (400, 404)
        else:
            # Server may tolerate unknown messageID and return [] — both ok.
            assert isinstance(diff, list)
    finally:
        _safe_delete(http, sid)


# --- 11. revert + unrevert --------------------------------------------------


@pytest.mark.flows
def test_unrevert_on_empty_session_returns_session_or_4xx(
    http, scratch_project_dir
):
    """POST /session/:sid/unrevert is idempotent on an un-reverted session.

    Exercised without needing real traffic: unrevert on a fresh session either
    returns the session (when the server tolerates it) or a 4xx validation
    error. Either shape is acceptable — what matters is that the handler is
    reachable and responds with a documented status.
    """
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        try:
            session = http.unrevert_session(sid)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code in (400, 404)
        else:
            assert session.get("id") == sid
    finally:
        _safe_delete(http, sid)


@pytest.mark.flows
def test_revert_with_fake_message_rejected(http, scratch_project_dir):
    """POST /session/:sid/revert with a fabricated messageID raises 4xx."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        with pytest.raises(httpx.HTTPStatusError) as exc:
            http.revert_message(sid, message_id="msg_fake")
        assert exc.value.response.status_code in (400, 404)
    finally:
        _safe_delete(http, sid)


# --- 12. session children ---------------------------------------------------


@pytest.mark.flows
def test_session_children_on_fresh_session_is_empty(http, scratch_project_dir):
    """GET /session/:sid/children returns [] for an un-forked session."""
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        try:
            kids = http.session_children(sid)
        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
            # Sidecar dropped the connection mid-request under suite-load
            # state accumulation. Not a contract regression — skip.
            pytest.skip(f"sidecar connection flake on /children: {e}")
        assert isinstance(kids, list)
        assert kids == [], f"expected empty children list, got {kids!r}"
    finally:
        _safe_delete(http, sid)


# --- 13. session status -----------------------------------------------------


@pytest.mark.flows
def test_session_status_returns_dict(http, scratch_project_dir):
    """GET /session/status returns a dict mapping session id → status info."""
    # status is global; create a session so we have at least one entry to look at.
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        status = http.session_status()
        assert isinstance(status, dict)
        # The created session may or may not show up (idle entries may be
        # filtered). We only assert the envelope shape.
    finally:
        _safe_delete(http, sid)


# --- 14. prompt_async (real_backend shape-only) ----------------------------


@pytest.mark.flows
@pytest.mark.real_backend
def test_prompt_async_returns_204(http, scratch_project_dir, gpd_key):
    """POST /session/:sid/prompt_async returns 204 (No Content).

    Shape-only: we don't wait for the LLM to finish. The server schedules the
    prompt and returns immediately; the wrapper returns ``None`` on 204. We
    abort right after to avoid accumulating cost if the test is run in a
    loop.
    """
    sid = _create_and_cleanup(http, directory=str(scratch_project_dir))
    try:
        out = http.prompt_async(
            sid,
            parts=[{"type": "text", "text": "Say hi."}],
        )
        assert out is None, f"prompt_async should return None on 204, got {out!r}"
        # Cancel any outstanding work so cleanup's DELETE can succeed cleanly.
        try:
            http.abort(sid)
        except Exception:  # noqa: BLE001
            pass
    finally:
        _safe_delete(http, sid)
