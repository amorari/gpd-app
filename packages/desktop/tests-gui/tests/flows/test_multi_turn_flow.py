"""3-turn conversation. Turn 1 sets a fact; turn 3 recalls it across turn 2's distraction."""
from __future__ import annotations
import pytest


@pytest.mark.flows
@pytest.mark.real_backend
def test_three_turn_context_retention(http, gpd_key):
    ses = http.create_session()
    try:
        # Turn 1: plant fact
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "My favorite color is octarine. Remember this exact word."}],
        )
        # Turn 2: distraction
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "What is 2+2?"}],
        )
        # Turn 3: recall
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "What is my favorite color?"}],
        )

        msgs = http.messages(ses["id"])
        assistant_msgs = [m for m in msgs if m["info"]["role"] == "assistant"]
        assert len(assistant_msgs) >= 3, f"expected 3 assistant turns, got {len(assistant_msgs)}"
        last = assistant_msgs[-1]
        text = "".join(p.get("text", "") for p in last["parts"] if p.get("type") == "text")
        assert "octarine" in text.lower(), (
            f"third-turn recall failed; assistant said: {text!r}"
        )
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
