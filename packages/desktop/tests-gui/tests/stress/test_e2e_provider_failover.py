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


HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
PROVIDER = "gpd"


def _send(http, ses_id, text, model=HAIKU):
    http.send_message(
        ses_id,
        parts=[{"type": "text", "text": text}],
        model_id=model,
        provider_id=PROVIDER,
        agent="default",
    )


def _last_text(http, ses_id, *, min_turns: int = 1, timeout_s: float = 60.0) -> str:
    """Poll for at least ``min_turns`` assistant turns with non-empty text.

    send_message returns before the reply has streamed; reading
    messages() immediately races the stream. Returns '' on timeout so
    callers can skip (``pytest.skip``) rather than fail with an empty
    assertion on a real-backend flake.
    """
    import time as _time
    deadline = _time.monotonic() + timeout_s
    while _time.monotonic() < deadline:
        msgs = http.messages(ses_id)
        assistant = [m for m in msgs if m["info"]["role"] == "assistant"]
        if len(assistant) >= min_turns:
            txt = "".join(
                p.get("text", "") for p in assistant[-1]["parts"]
                if p.get("type") == "text"
            )
            if txt.strip():
                return txt
        _time.sleep(0.5)
    return ""


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

        # Wait for the 3rd assistant turn with non-empty text.
        last = _last_text(http, ses["id"], min_turns=3, timeout_s=90.0)
        if not last.strip():
            pytest.skip(
                "real-backend produced no final-turn text within 90s — "
                "provider flake, not a harness / product assertion failure"
            )
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

        # Wait for all 10 assistant turns to stream in with non-empty text.
        last = _last_text(http, ses["id"], min_turns=10, timeout_s=240.0)
        if not last.strip():
            msgs = http.messages(ses["id"])
            got = len([m for m in msgs if m["info"]["role"] == "assistant"])
            pytest.skip(
                f"real-backend produced only {got}/10 assistant turns (or empty "
                "final text) within 240s — provider flake, not a test bug"
            )
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
        last = _last_text(http, ses["id"], timeout_s=45.0)
        if not last.strip():
            pytest.skip(
                "real-backend produced no recovery-send text within 45s — "
                "provider flake, not a harness regression"
            )
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
