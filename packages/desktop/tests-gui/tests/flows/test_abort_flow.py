"""Abort mid-generation should stop token flow without hanging."""
from __future__ import annotations
import threading

import pytest

from gpd_tests.helpers.timings import wait_until


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
def test_abort_stops_generation(http, gpd_key):
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
                            "Give an exhaustive, extremely detailed history of "
                            "every major physics discovery from ancient Greece to "
                            "today. Include every scientist, every equation, and "
                            "every experiment. Do not stop until you have covered "
                            "everything — this should be thousands of words."
                        ),
                    }],
                )
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        t = threading.Thread(target=_send, daemon=True)
        t.start()

        def _has_tokens() -> bool:
            try:
                msgs = http.messages(ses["id"])
                return bool(_assistant_text(msgs))
            except Exception:
                return False

        wait_until(_has_tokens, timeout_s=15.0, backoff_factor=1.4)
        http.abort(ses["id"])
        t.join(timeout=15)
        assert not t.is_alive(), "send_message thread did not unwind after abort"

        msgs = http.messages(ses["id"])
        text = _assistant_text(msgs)
        assert len(text) > 0, "no partial output captured before abort"
        # The model was generating a long history essay — if abort worked, the
        # text should be noticeably shorter than a complete response (~10k chars).
        assert len(text) < 8000, (
            f"abort happened too late — got {len(text)} chars (expected < 8000)"
        )
    finally:
        try:
            http.delete_session(ses["id"])
        except Exception:
            pass
