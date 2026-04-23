"""Sessions and their history must survive a quit/relaunch cycle."""
from __future__ import annotations

import pytest


@pytest.mark.lifecycle
@pytest.mark.flows
@pytest.mark.real_backend
def test_session_survives_quit_relaunch(http, app_state, gpd_key):
    ses = http.create_session()
    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "Remember the number 847392. Reply only with 'OK'."}],
    )
    pre_msgs = http.messages(ses["id"])
    assert len(pre_msgs) >= 2, "expected at least user + assistant turn"

    app_state.quit()
    app_state.wait_quit(timeout_s=15)
    app_state.launch()
    app_state.wait_launched()

    # Sidecar was killed and respawned on a new port with fresh auth creds —
    # the HTTPClient instance this test holds still points at the dead
    # sidecar. Re-point it at the new one (F9) before any further calls.
    http.rediscover(app_state.sidecar_pid())
    post_msgs = http.messages(ses["id"])
    assert len(post_msgs) == len(pre_msgs)

    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "What number did I ask you to remember?"}],
    )
    final = http.messages(ses["id"])
    assistants = [m for m in final if m["info"]["role"] == "assistant"]
    last_text = "".join(p.get("text", "") for p in assistants[-1]["parts"] if p.get("type") == "text")
    assert "847392" in last_text, f"memory lost across restart; got: {last_text!r}"
    try:
        http.delete_session(ses["id"])
    except Exception:
        pass
