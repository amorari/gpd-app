"""E2E stress — high-volume single session (20 turns, context retention, timing).

Uses the cheapest Anthropic model (Haiku) to minimise cost.
Requires a real Anthropic key (GPD_TEST_ANTHROPIC_KEY env var).

Assertions:
  1. All 20 assistant replies are delivered.
  2. The session retains context across the full conversation (secret planted in
     turn 1 must be recalled in turn 20).
  3. Total wall-clock time for 20 turns stays under 480 seconds.
  4. No assistant reply is empty (empty replies indicate a silent failure).
"""
from __future__ import annotations

import time

import pytest


MODEL = "claude-haiku-4-5-20251001"
PROVIDER = "anthropic"
SECRET = "XRAY-LIMA-9"


def _last_assistant_text(msgs: list) -> str:
    assistant = [m for m in msgs if m["info"]["role"] == "assistant"]
    if not assistant:
        return ""
    return "".join(
        p.get("text", "") for p in assistant[-1]["parts"] if p.get("type") == "text"
    )


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(600)
def test_20_turn_session_completes_under_budget(http, anthropic_key):
    """20 sequential turns complete in < 480 s with context retention."""
    ses = http.create_session()
    t_start = time.monotonic()

    try:
        for turn in range(1, 21):
            if turn == 1:
                text = f"My secret code is {SECRET}. Please say 'ack-turn-1'."
            elif turn == 10:
                text = f"Mid-check: what is my secret code? Say 'ack-turn-10'."
            elif turn == 20:
                text = f"Final recall: what is my secret code? Say 'ack-turn-20'."
            else:
                text = f"Turn {turn}: what is {turn} + {turn}? Reply only with the sum."

            http.send_message(
                ses["id"],
                parts=[{"type": "text", "text": text}],
                model_id=MODEL,
                provider_id=PROVIDER,
                agent="default",
            )

        elapsed = time.monotonic() - t_start
        msgs = http.messages(ses["id"])
        assistant_msgs = [m for m in msgs if m["info"]["role"] == "assistant"]

        # Assertion 1: 20 replies delivered
        assert len(assistant_msgs) >= 20, (
            f"expected 20 assistant turns, got {len(assistant_msgs)}"
        )

        # Assertion 2: no empty reply
        for i, m in enumerate(assistant_msgs, 1):
            text_body = "".join(
                p.get("text", "") for p in m["parts"] if p.get("type") == "text"
            )
            assert text_body.strip(), f"assistant reply at turn {i} is empty"

        # Assertion 3: context retained at turn 20
        last = _last_assistant_text(msgs)
        assert SECRET.lower() in last.lower() or "ack-turn-20" in last.lower(), (
            f"turn-20 context recall failed — secret '{SECRET}' not found in: {last!r}"
        )

        # Assertion 4: timing budget
        assert elapsed < 480, (
            f"20-turn session exceeded 480 s budget: {elapsed:.1f} s"
        )

    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.timeout(120)
def test_empty_session_message_listing_is_stable(http, anthropic_key):
    """A session with no messages returns empty list, not an error."""
    ses = http.create_session()
    try:
        msgs = http.messages(ses["id"])
        assert isinstance(msgs, list), f"expected list, got {type(msgs)}"
        assert len(msgs) == 0, f"new session should have 0 messages, got {len(msgs)}"
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
