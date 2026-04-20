"""LLM-tolerant assertions: shape-level only, no content matching."""
from __future__ import annotations

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


def assert_assistant_replied(response: dict[str, Any]) -> None:
    """Raise AssertionError if `response` is not a well-formed assistant reply.

    Checks shape only — does NOT assert on content. Safe against any LLM
    variance.
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
