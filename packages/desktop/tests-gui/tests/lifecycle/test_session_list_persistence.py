"""Creating multiple sessions, then quit/relaunch, must preserve all of them."""
from __future__ import annotations
import pytest


@pytest.mark.lifecycle
def test_multiple_sessions_persist(http, app_state):
    ses_ids = [http.create_session()["id"] for _ in range(3)]
    pre = {s["id"] for s in http.sessions()}
    for sid in ses_ids:
        assert sid in pre, f"session {sid} not visible before restart"

    app_state.quit()
    app_state.wait_quit(timeout=15)
    app_state.launch()

    post = {s["id"] for s in http.sessions()}
    for sid in ses_ids:
        assert sid in post, f"session {sid} lost across restart"

    for sid in ses_ids:
        try:
            http.delete_session(sid)
        except Exception:
            pass
