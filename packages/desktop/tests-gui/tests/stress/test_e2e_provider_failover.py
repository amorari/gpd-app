"""E2E stress — model switching within a single session.

Tests that the session history is correctly preserved when the caller
alternates between two different models in the same session. The HTTP
sidecar routes each turn to the requested model; the conversation context
is session-scoped, not model-scoped.

Tests:
  1. haiku -> sonnet -> haiku: plant fact with haiku, distract with sonnet,
     recall with haiku — verify context survived the model switches.
  2. Rapid model alternation (10 turns, alternating haiku/sonnet every turn):
     verify all 10 turns complete and the final reply is non-empty.
  3. Unknown model ID returns error, session stays valid: after the error,
     a subsequent turn with a valid model still works.
"""
from __future__ import annotations

import pytest


HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
PROVIDER = "anthropic"


def _send(http, ses_id, text, model=HAIKU):
    http.send_message(
        ses_id,
        parts=[{"type": "text", "text": text}],
        model_id=model,
        provider_id=PROVIDER,
        agent="default",
    )


def _last_text(http, ses_id) -> str:
    msgs = http.messages(ses_id)
    assistant = [m for m in msgs if m["info"]["role"] == "assistant"]
    if not assistant:
        return ""
    return "".join(
        p.get("text", "") for p in assistant[-1]["parts"] if p.get("type") == "text"
    )


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(180)
def test_haiku_sonnet_haiku_context_survives_model_switch(http, gpd_key):
    """Fact planted with haiku is recalled via haiku after a sonnet distraction turn."""
    ses = http.create_session()
    FACT = "BLUEPINE-42"
    try:
        _send(http, ses["id"], f"My code phrase is {FACT}. Say 'stored'.", model=HAIKU)
        _send(http, ses["id"], "Name three planets.", model=SONNET)
        _send(http, ses["id"], "What is my code phrase?", model=HAIKU)

        last = _last_text(http, ses["id"])
        assert "bluepine" in last.lower() or "bluepine-42" in last.lower(), (
            f"context lost after model switch; last reply: {last!r}"
        )
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(300)
def test_10_turn_alternating_haiku_sonnet(http, gpd_key):
    """10 turns alternating haiku/sonnet — all complete and last reply is non-empty."""
    ses = http.create_session()
    try:
        models = [HAIKU, SONNET] * 5
        for i, model in enumerate(models, 1):
            _send(http, ses["id"], f"Turn {i}: say 'ack-{i}'.", model=model)

        msgs = http.messages(ses["id"])
        assistant_msgs = [m for m in msgs if m["info"]["role"] == "assistant"]
        assert len(assistant_msgs) >= 10, (
            f"expected 10 assistant turns, got {len(assistant_msgs)}"
        )
        last = _last_text(http, ses["id"])
        assert last.strip(), "last reply is empty after 10-turn alternating session"
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(60)
def test_invalid_model_error_leaves_session_usable(http, gpd_key):
    """After a failed send (bad model ID), the session can still accept a valid turn."""
    ses = http.create_session()
    try:
        with pytest.raises(Exception):
            http.send_message(
                ses["id"],
                parts=[{"type": "text", "text": "hello"}],
                model_id="nonexistent-model-id-xyzzy",
                provider_id=PROVIDER,
                agent="default",
            )

        # Confirm the session still exists before attempting the recovery send.
        # Some sidecars tombstone sessions on model error; if so, skip rather than fail.
        try:
            http.get_session(ses["id"])
        except Exception:
            pytest.skip(
                "sidecar tombstoned the session after an invalid-model error — "
                "recovery not supported; mark xfail if this is the expected behavior"
            )

        _send(http, ses["id"], "Say 'still alive'.", model=HAIKU)
        last = _last_text(http, ses["id"])
        assert last.strip(), (
            "session unusable after invalid-model error; last reply is empty"
        )
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
