"""LLM-tolerant assertions: shape-level only, no content matching."""
from __future__ import annotations

from typing import Any


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

    A tool-use-only response (no text parts) is considered valid: the model
    may choose to call a tool without emitting any text.
    """
    assert isinstance(response, dict), (
        f"assert_assistant_replied expects a dict, got {type(response).__name__}: {response!r}"
    )
    info = response.get("info") or {}
    role = info.get("role")
    assert role == "assistant", f"expected assistant role, got {role!r}"
    parts = response.get("parts") or []
    assert parts, f"assistant response has no parts: {response!r}"
    # A reply with at least one part is valid — text OR tool-use.
    # If there are text parts, at least one must be non-empty.
    text_parts = [p for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    if text_parts:
        text = "".join(str(p.get("text", "")) for p in text_parts)
        assert text.strip(), f"assistant response has empty text: {response!r}"
