"""Abort mid-generation should stop token flow without hanging."""
from __future__ import annotations
import threading
import time

import pytest


def _assistant_text(msgs: list[dict]) -> str:
    """Concat text parts across all assistant messages."""
    out: list[str] = []
    for m in msgs:
        if m.get("info", {}).get("role") != "assistant":
            continue
        for p in m.get("parts", []):
            if p.get("type") == "text":
                out.append(p.get("text", ""))
    return "".join(out)


@pytest.mark.flows
@pytest.mark.real_backend
def test_abort_stops_generation(http, anthropic_key):
    ses = http.create_session()
    try:
        errors: list[Exception] = []

        def _send():
            try:
                http.send_message(
                    ses["id"],
                    parts=[{
                        "type": "text",
                        "text": (
                            "Count slowly from 1 to 1000, one number per line. "
                            "Do not summarize. Just the numbers."
                        ),
                    }],
                    model_id="claude-4-7",
                    provider_id="anthropic",
                    agent="default",
                )
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
        time.sleep(2.5)  # let tokens start flowing
        http.abort(ses["id"])
        t.join(timeout=15)
        assert not t.is_alive(), "send_message thread did not unwind after abort"

        msgs = http.messages(ses["id"])
        text = _assistant_text(msgs)
        assert len(text) > 0, "no partial output captured before abort"
        assert "1000" not in text, "abort happened too late — model reached 1000"
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
