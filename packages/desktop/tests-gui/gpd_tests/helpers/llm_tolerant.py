"""LLM-tolerant assertions: shape-level only, no content matching."""
from __future__ import annotations

import time
from typing import Any

_MAX_REPR = 500


def assistant_text(response: dict[str, Any]) -> str:
    """Concatenate all text parts of an assistant response."""
    parts = response.get("parts") or []
    return "".join(
        str(p.get("text", ""))
        for p in parts
        if isinstance(p, dict) and p.get("type") == "text"
    )


def wait_for_assistant_text(
    http, session_id: str, *, timeout_s: float = 30.0, poll_s: float = 0.5
) -> str:
    """Poll /session/:id/message until the latest assistant turn has
    non-empty text, or raise TimeoutError.

    send_message returns once the sidecar has accepted the POST; the
    assistant's reply streams asynchronously. Tests that read messages
    immediately after send_message race the stream and see empty text.
    Wrapping the read in this helper gives the stream time to settle.

    Returns the concatenated assistant text across all assistant turns.
    """
    deadline = time.monotonic() + timeout_s
    last_text = ""
    while time.monotonic() < deadline:
        try:
            msgs = http.messages(session_id)
        except Exception:
            time.sleep(poll_s)
            continue
        assistant_msgs = [
            m for m in msgs if (m.get("info") or {}).get("role") == "assistant"
        ]
        if assistant_msgs:
            last_text = "".join(assistant_text(m) for m in assistant_msgs)
            if last_text.strip():
                return last_text
        time.sleep(poll_s)
    raise TimeoutError(
        f"assistant text never became non-empty within {timeout_s}s "
        f"for session {session_id} (last_text={last_text!r})"
    )


def assert_assistant_replied(response: dict[str, Any]) -> None:
    """Raise AssertionError if `response` is not a well-formed assistant reply.

    Checks shape only — does NOT assert on content. Safe against any LLM
    variance.

    A tool-use-only response (no text parts) is considered valid: the model
    may choose to call a tool without emitting any text.
    """
    if not isinstance(response, dict):
        raise AssertionError(
            f"expected dict response, got {type(response)}"
        )

    info = response.get("info") or {}

    # Surface any error key before checking role.
    error = response.get("error") or info.get("error")
    if error:
        raise AssertionError(
            f"response contains error: {error!r} — full response: "
            f"{repr(response)[:_MAX_REPR]}"
        )

    role = info.get("role")
    assert role == "assistant", (
        f"expected assistant role, got {role!r} — "
        f"{repr(response)[:_MAX_REPR]}"
    )

    parts = response.get("parts") or []
    text = assistant_text(response)
    has_tool_use = any(
        isinstance(p, dict) and p.get("type") == "tool-use" for p in parts
    )
    assert text.strip() or has_tool_use, (
        f"assistant response has empty text and no tool-use parts: "
        f"{repr(response)[:_MAX_REPR]}"
    )
