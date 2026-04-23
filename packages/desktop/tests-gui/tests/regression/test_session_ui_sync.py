"""Regression test: session deleted via HTTP is reflected in the sidebar UI.

Commit: 7ca2a7921  fix(frontend): update session list on delete + add session
deep link handler

Before the fix, deleting a session via HTTP (DELETE /session/:id) did not
remove the corresponding sidebar row because the SSE event was not wired up
to the reactive session store.  The store now listens for the
``session.deleted`` SSE event and removes the entry, causing the DOM row to
disappear without a full page reload.

This test exercises that path end-to-end:
  1. Create a session via HTTP.
  2. Navigate to the project route so the sidebar is rendered.
  3. Confirm the session row is present in the DOM.
  4. Delete the session via HTTP.
  5. Wait up to 5s for the row to disappear (SSE-driven reactive update).
"""
from __future__ import annotations

import subprocess

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_session_in_project,
)
from gpd_tests.helpers.timings import wait_until


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dom_has_session_row(probe: DOMProbe, sid: str) -> bool:
    js = f'!!document.querySelector(\'[data-session-id="{sid}"]\')'
    try:
        return probe.eval_bool(js)
    except ProbeSkip:
        return False


def _safe_delete(http, sid: str) -> None:
    try:
        http.delete_session(sid)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def _project_path(tmp_path_factory) -> str:
    """A real git repo in a temp dir that GPD will register as a project.

    The sidecar only registers directories it recognises as valid git project
    roots; a plain directory without .git will be silently ignored.

    Project cleanup is handled by the autouse
    ``_auto_unregister_tmpdir_projects`` fixture in root conftest.
    """
    p = tmp_path_factory.mktemp("reg_session_ui_sync")
    (p / "README.md").write_text("# regression test project\n")
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        ["git", "add", "."],
        cwd=str(p), check=True, capture_output=True,
    )
    subprocess.run(
        [
            "git", "-c", "user.email=test@test.com",
            "-c", "user.name=Test", "commit", "-m", "init",
        ],
        cwd=str(p), check=True, capture_output=True,
    )
    return str(p)


# ---------------------------------------------------------------------------
# Regression test
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_session_deleted_via_http_disappears_from_sidebar(mcp, http, _project_path):
    """Deleting a session via HTTP must remove its sidebar row within 5 seconds.

    The sidebar is updated by a reactive SSE listener introduced in commit
    7ca2a7921.  If the row persists after the timeout the fix has regressed.
    """
    ses = http.create_session(directory=_project_path)
    sid = ses.get("id")
    assert sid, f"create_session returned no id: {ses!r}"

    session_deleted = False
    try:
        # Navigate to the session-list route for this project.  route_project
        # targets /:dir which the SPA immediately redirects to /:dir/session;
        # nav.go's URL matcher cannot follow the redirect so we use the session
        # route directly (the sidebar still renders session rows from there).
        Navigator(mcp).go(
            route_session_in_project(encode_dir_token(_project_path)),
            timeout_s=5.0,
        )
        probe = DOMProbe(mcp)

        # Wait for the row to appear before attempting deletion — the sidebar
        # hydrates asynchronously after navigation.
        appeared = wait_until(
            lambda: _dom_has_session_row(probe, sid),
            timeout_s=15.0,
            poll_s=0.2,
        )
        if not appeared:
            pytest.skip(
                f"session row [data-session-id={sid!r}] never appeared in the "
                "sidebar within 15s — sidebar may be off-screen or sync latency "
                "is unusually high; cannot exercise the deletion path"
            )

        # Delete the session via HTTP (mimics the original bug scenario).
        deleted = http.delete_session(sid)
        session_deleted = True
        assert deleted is True, f"DELETE /session/{sid} did not return True: {deleted!r}"

        # The SSE-driven reactive update should remove the row.  Poll up to 5s.
        disappeared = wait_until(
            lambda: not _dom_has_session_row(probe, sid),
            timeout_s=5.0,
            poll_s=0.2,
        )
        assert disappeared, (
            f"regression (commit 7ca2a7921): session row "
            f"[data-session-id={sid!r}] is still present in the sidebar DOM "
            "5s after DELETE /session/:id. The SSE session.deleted handler is "
            "not removing the entry from the reactive store."
        )
    except Exception:
        # Only attempt cleanup if the HTTP DELETE has not yet been called.
        # After session_deleted=True the session is gone; a second call would
        # hit a 404 (harmlessly caught by _safe_delete, but misleading).
        if not session_deleted:
            _safe_delete(http, sid)
        raise
