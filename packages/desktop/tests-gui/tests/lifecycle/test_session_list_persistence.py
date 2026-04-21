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
    app_state.wait_quit(timeout_s=15)
    app_state.launch()
    app_state.wait_launched()

    # Sidecar was killed and respawned on a new port with fresh auth creds —
    # re-point the HTTPClient at the new sidecar before querying sessions (F9).
    http.rediscover(app_state.sidecar_pid())
    post = {s["id"] for s in http.sessions()}
    for sid in ses_ids:
        assert sid in post, f"session {sid} lost across restart"

    for sid in ses_ids:
        try:
            http.delete_session(sid)
        except Exception:
            pass
