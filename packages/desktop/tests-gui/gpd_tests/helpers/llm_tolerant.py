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
    """
    info = response.get("info") or {}
    role = info.get("role")
    assert role == "assistant", f"expected assistant role, got {role!r}"
    text = assistant_text(response)
    assert text.strip(), f"assistant response has empty text: {response!r}"
