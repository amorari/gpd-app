"""Sessions and their history must survive a quit/relaunch cycle."""
from __future__ import annotations

import os

import pytest


@pytest.mark.lifecycle
@pytest.mark.flows
@pytest.mark.real_backend
def test_session_survives_quit_relaunch(http, app_state):
    # Inline real-backend guard: the `anthropic_key` fixture lives in
    # tests/flows/conftest.py and isn't visible from tests/lifecycle/.
    # Keeping the check inline avoids duplicating the fixture here and keeps
    # tests/lifecycle/conftest.py truly minimal (per plan task D1, step 2).
    if not os.environ.get("GPD_TEST_ANTHROPIC_KEY"):
        pytest.skip("GPD_TEST_ANTHROPIC_KEY not set; skipping real-backend lifecycle")

    ses = http.create_session()
    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "Remember the number 847392. Reply only with 'OK'."}],
        model_id="claude-4-7",
        provider_id="anthropic",
        agent="default",
    )
    pre_msgs = http.messages(ses["id"])
    assert len(pre_msgs) >= 2, "expected at least user + assistant turn"

    app_state.quit()
    app_state.wait_quit(timeout_s=15)
    app_state.launch()
    app_state.wait_launched()

    # Sidecar was killed and respawned — the http fixture instance still holds
    # the old port/creds. If the fixture doesn't auto-rediscover, this test
    # will fail on the next http call; that failure is a legit finding worth
    # escalating (gap: opencode_http.HTTPClient has no rediscover() method,
    # and the root conftest http fixture is function-scoped so it only
    # rediscovers on the NEXT test, not mid-test after a restart).
    post_msgs = http.messages(ses["id"])
    assert len(post_msgs) == len(pre_msgs)

    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "What number did I ask you to remember?"}],
        model_id="claude-4-7",
        provider_id="anthropic",
        agent="default",
    )
    final = http.messages(ses["id"])
    assistants = [m for m in final if m["info"]["role"] == "assistant"]
    last_text = "".join(p.get("text", "") for p in assistants[-1]["parts"] if p.get("type") == "text")
    assert "847392" in last_text, f"memory lost across restart; got: {last_text!r}"
    try:
        http.delete_session(ses["id"])
    except Exception:
        pass
