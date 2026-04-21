"""Unit tests for ``scripts/refresh_en_dict.py``.

Covers the two wave-2 bugfixes:

* W2-R22 — ``unicode_escape`` corrupts UTF-8 (mojibake on ``…``, ``μ``,
  language-name CJK/Cyrillic). Round-trip assertion confirms the un-escape
  helper preserves UTF-8.
* W2-R23 — regex missed single-quoted and line-wrapped values. The
  tokenizer/regex captures both shapes and also handles embedded escaped
  quotes.
"""
from __future__ import annotations

import pytest

import scripts.refresh_en_dict as refresh


@pytest.mark.unit
def test_unescape_preserves_utf8_roundtrip():
    """A UTF-8 string with no JS escapes should round-trip unchanged.

    The old ``value.encode().decode("unicode_escape")`` turned ``"Français …"``
    into ``"FranÃ§ais â€¦"`` because ``unicode_escape`` is a Latin-1 codec.
    The new helper must leave non-escape content alone.
    """
    raw = "Français … — μ+μ- 中文"
    assert refresh._unescape_js_string(raw) == raw


@pytest.mark.unit
def test_unescape_materializes_js_escapes():
    """JS escape sequences should be turned into their runtime characters."""
    raw = r"line1\nline2\ttab\\back\"quote\'apos"
    assert (
        refresh._unescape_js_string(raw)
        == "line1\nline2\ttab\\back\"quote'apos"
    )


@pytest.mark.unit
def test_unescape_backslash_order():
    """``\\\\n`` in TS source is a literal backslash + ``n`` — not a newline.

    The order-sensitive replace logic must translate ``\\\\`` (double
    backslash → single backslash) first, so the residual ``\\`` doesn't
    combine with the following ``n`` into a newline.
    """
    # r"\\n" is three Python characters: '\', '\', 'n' — matching the three
    # characters that appear inside a TS string literal written as "\\n".
    raw = r"\\n"
    out = refresh._unescape_js_string(raw)
    assert out == "\\n"  # two chars: backslash, letter 'n'
    assert "\n" not in out


@pytest.mark.unit
def test_parse_double_quoted_single_line():
    src = 'export const dict = {\n  "a.b": "hello",\n}\n'
    assert refresh.parse_en_ts(src) == {"a.b": "hello"}


@pytest.mark.unit
def test_parse_single_quoted_value():
    """Single-quoted values are needed whenever the string contains ``"``."""
    src = (
        "export const dict = {\n"
        "  \"prompt.placeholder\": 'Ask anything... \"{{example}}\"',\n"
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out == {"prompt.placeholder": 'Ask anything... "{{example}}"'}


@pytest.mark.unit
def test_parse_single_quoted_with_escaped_apostrophe():
    src = (
        "export const dict = {\n"
        "  \"context.note\": 'what\\'s in memory',\n"
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out == {"context.note": "what's in memory"}


@pytest.mark.unit
def test_parse_multiline_wrapped_value():
    """Prettier wraps long lines by putting the value on a new line."""
    src = (
        "export const dict = {\n"
        '  "provider.connect.apiKey.description":\n'
        '    "Enter your {{provider}} access key to connect your account.",\n'
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out == {
        "provider.connect.apiKey.description": (
            "Enter your {{provider}} access key to connect your account."
        )
    }


@pytest.mark.unit
def test_parse_mixed_single_line_and_wrapped_and_quoted():
    """All three shapes coexist in the real source. Capture them together."""
    src = (
        "export const dict = {\n"
        '  "a": "one",\n'
        "  \"b\": 'two',\n"
        '  "c":\n'
        '    "three",\n'
        "  \"d\":\n"
        "    'four',\n"
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out == {"a": "one", "b": "two", "c": "three", "d": "four"}


@pytest.mark.unit
def test_parse_preserves_utf8_from_source():
    """End-to-end: UTF-8 chars survive from source text into parsed values."""
    src = (
        "export const dict = {\n"
        '  "language.fr": "Français",\n'
        '  "language.es": "Español",\n'
        '  "prompt.physics": "Compute e+e- → μ+μ-",\n'
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out["language.fr"] == "Français"
    assert out["language.es"] == "Español"
    assert out["prompt.physics"] == "Compute e+e- → μ+μ-"


@pytest.mark.unit
def test_parse_handles_embedded_newline_escape():
    """``\\n`` in the source should materialize as a real newline."""
    src = (
        "export const dict = {\n"
        '  "cli.msg": "Installed to {{path}}\\n\\nRestart.",\n'
        "}\n"
    )
    out = refresh.parse_en_ts(src)
    assert out == {"cli.msg": "Installed to {{path}}\n\nRestart."}
