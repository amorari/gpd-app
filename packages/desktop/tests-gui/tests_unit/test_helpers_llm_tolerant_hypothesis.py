"""Property-based tests for `gpd_tests.helpers.llm_tolerant` (Task G7.2).

Hypothesis strategy notes
-------------------------
We model a session message as the product-helpers in `llm_tolerant.py` expects:

    {
        "info": {"role": <role>, ...optional keys...},
        "parts": [ {"type": <part-type>, "text"?: <str>, ...}, ... ],
        "error"?: <str>,
    }

Strategy decisions:

* `role` is drawn from the sampled set {"user", "assistant", "system", "tool"}
  — the four roles the product currently routes through. We deliberately do
  *not* include arbitrary strings because the helpers are only contracted
  against these roles.
* `parts` are drawn from a small catalog of well-formed part dicts
  (text, tool-use, tool-result, image, unknown). The `text` value uses
  `st.text()` — unicode, any length — to exercise the concatenation loop.
* Both `info` and each part may carry extra keys drawn from
  `st.dictionaries(...)` to ensure helpers ignore unrelated fields.
* `error` is optionally present to trigger the error-envelope path.
* Example count is capped at 50 via `settings(max_examples=50)` per spec.

Two properties are asserted:

1. `assistant_text` never raises and always returns `str` on any response
   drawn from the strategy — including ones with no parts, non-text parts,
   or non-dict parts.
2. The generated fixture survives a `json.dumps` / `json.loads` round-trip
   (i.e., the strategy only emits JSON-serialisable data), and the helper
   output is identical before and after the trip. This is the "well-formed"
   contract the harness depends on when it pipes messages through the MCP
   socket.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from gpd_tests.helpers.llm_tolerant import assistant_text

# -- Strategies ---------------------------------------------------------------

_ROLES = ("user", "assistant", "system", "tool")
_PART_TYPES = ("text", "tool-use", "tool-result", "image", "unknown")

# Extra-key values restricted to JSON-safe scalars so the whole payload
# round-trips through `json.dumps` without `TypeError`.
_json_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=32),
)

_extra_fields = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(min_codepoint=33, max_codepoint=126),
        min_size=1,
        max_size=8,
    ),
    values=_json_scalar,
    max_size=3,
)


@st.composite
def _part(draw: st.DrawFn) -> dict[str, Any]:
    """A single `parts[i]` element: a dict with `type` and optional `text`."""
    ptype = draw(st.sampled_from(_PART_TYPES))
    part: dict[str, Any] = {"type": ptype}
    if ptype == "text":
        # text parts always carry a `text` field; sometimes empty string
        part["text"] = draw(st.text(max_size=64))
    elif ptype == "tool-use":
        part["toolUseId"] = draw(st.text(min_size=1, max_size=16))
        part["toolName"] = draw(st.sampled_from(("bash", "read", "write")))
        part["input"] = {}
    elif ptype == "tool-result":
        part["toolUseId"] = draw(st.text(min_size=1, max_size=16))
        part["output"] = draw(st.text(max_size=32))
    # Merge in additional unrelated keys to ensure helpers ignore them.
    part.update(draw(_extra_fields))
    return part


@st.composite
def _message(draw: st.DrawFn) -> dict[str, Any]:
    """A session message shaped like the GPD session API returns."""
    info: dict[str, Any] = {"role": draw(st.sampled_from(_ROLES))}
    info.update(draw(_extra_fields))

    parts_list: list[Any] = draw(st.lists(_part(), max_size=6))
    # Occasionally sprinkle in a non-dict part — the helper must tolerate it.
    if draw(st.booleans()):
        parts_list.append(draw(st.one_of(st.none(), st.text(max_size=8), st.integers())))

    msg: dict[str, Any] = {"info": info, "parts": parts_list}
    # Optional top-level error envelope.
    if draw(st.booleans()):
        msg["error"] = draw(st.text(max_size=32))
    return msg


_HYP_SETTINGS = settings(
    max_examples=50,
    # The composite strategy does enough work that hypothesis' default
    # too-slow health check can flake on loaded CI runners; disable it.
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)


# -- Properties ---------------------------------------------------------------


@pytest.mark.unit
@_HYP_SETTINGS
@given(msg=_message())
def test_assistant_text_never_raises_and_returns_str(msg: dict[str, Any]) -> None:
    """Property: `assistant_text` is total over well-formed messages."""
    result = assistant_text(msg)
    assert isinstance(result, str)
    # And the result only contains text drawn from text-typed parts.
    expected_chars = "".join(
        str(p.get("text", ""))
        for p in msg["parts"]
        if isinstance(p, dict) and p.get("type") == "text"
    )
    assert result == expected_chars


@pytest.mark.unit
@_HYP_SETTINGS
@given(msg=_message())
def test_message_roundtrips_through_json(msg: dict[str, Any]) -> None:
    """Property: the generated message is JSON-safe and helper output is stable."""
    encoded = json.dumps(msg)
    decoded = json.loads(encoded)
    assert isinstance(decoded, dict)
    # assistant_text must produce the same string pre- and post- round-trip,
    # which also proves helper output is JSON-serialisation-invariant.
    assert assistant_text(msg) == assistant_text(decoded)
