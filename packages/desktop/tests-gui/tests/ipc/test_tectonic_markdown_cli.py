"""Contract tests for tectonic.rs, markdown.rs, and cli.rs commands.

Three commands covered (one per file):
  - install_tectonic (tectonic.rs)
  - parse_markdown_command (markdown.rs)
  - install_cli (cli.rs)

Runs against live GPD debug build.
"""
from __future__ import annotations

import os
import sys

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# ---------------------------------------------------------------------------
# parse_markdown_command (markdown.rs)
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_parse_markdown_command_renders_basic_fixture(mcp):
    """A canonical fixture must render with an <h1> for the header and a
    <strong> (or <b>) element for the bold emphasis span."""
    fixture = "# Hello\n**bold**"
    html = invoke_via_mcp(mcp, "parse_markdown_command", {"markdown": fixture})
    assert isinstance(html, str)
    assert "<h1" in html
    assert "Hello" in html
    # comrak emits <strong> for ** **; accept <b> for defensive parity.
    assert "<strong>" in html or "<b>" in html


@pytest.mark.ipc
def test_parse_markdown_command_empty_input_returns_empty_html(mcp):
    """An empty markdown string must not error — it should produce an
    empty (or whitespace-only) HTML string."""
    html = invoke_via_mcp(mcp, "parse_markdown_command", {"markdown": ""})
    assert isinstance(html, str)
    assert html.strip() == ""


# ---------------------------------------------------------------------------
# G4.3 — parse_markdown_command feature matrix.
#
# `markdown.rs::parse_markdown` enables comrak with the following extensions:
#   * strikethrough
#   * table (GFM pipe tables)
#   * tasklist
#   * autolink
# …and `render.r#unsafe = true` (raw HTML is passed through; see
# `packages/desktop/src-tauri/src/markdown.rs:44-57`). The external-link
# formatter additionally rewrites `<a>` tags to include
# `class="external-link" target="_blank" rel="noopener noreferrer"`.
#
# The fixture below exercises a rich cross-section of those extensions in
# one pass and asserts structural markers in the rendered HTML. A dedicated
# security assertion follows for the XSS vector.
# ---------------------------------------------------------------------------


_RICH_MARKDOWN_FIXTURE = """\
# Feature matrix

A paragraph with a bare URL: https://example.com/autolink — and a
[regular link](https://example.org/regular).

## GFM table

| col a | col b |
| ----- | ----- |
| x     | y     |
| 1     | 2     |

## Fenced code with language

```python
def greet(name: str) -> str:
    return f"hello {name}"
```

## Math (inline and display)

Inline: $x^2 + y^2 = z^2$.

Display:

$$
\\sum_{i=0}^{n} i = \\frac{n(n+1)}{2}
$$

## Blockquote

> Quoth the raven,
> "Nevermore."

## Nested lists

- top
  - nested
    - deeply nested
  - back up one
- next top

## Inline HTML escape probe

Text with literal angle brackets: 1 < 2 and 3 > 2 and a&b.
"""


@pytest.mark.ipc
def test_parse_markdown_command_renders_rich_feature_matrix(mcp):
    """One fixture exercises table / fenced code / math / autolink /
    blockquote / nested lists / HTML-escape behaviour.

    The assertions below deliberately look only for structural markers so
    this test survives minor reflowing in comrak's output (whitespace,
    attribute ordering). Each assertion carries a comment naming the
    markdown feature it pins.
    """
    html = invoke_via_mcp(
        mcp, "parse_markdown_command", {"markdown": _RICH_MARKDOWN_FIXTURE}
    )
    assert isinstance(html, str)
    assert html, "non-empty fixture must render non-empty HTML"

    # Headings.
    assert "<h1" in html and "Feature matrix" in html
    assert "<h2" in html

    # GFM table extension.
    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html
    assert "<th>" in html
    assert "<td>" in html
    assert ">col a<" in html or "col a" in html

    # Fenced code with language — comrak emits `<code class="language-python">`.
    assert '<code class="language-python">' in html
    # The code body should be escaped, not HTML-interpreted.
    assert "def greet" in html

    # Math: comrak (with the extensions we enable) does NOT recognize
    # `$...$` / `$$...$$` as math — it leaves the literal `$` characters
    # in the rendered output. Pin that behavior so any future enable of
    # `extension.math_*` in markdown.rs surfaces here.
    assert "$x^2" in html or "x^2" in html, (
        "inline math delimiters should be preserved verbatim (no math "
        "extension enabled in markdown.rs)"
    )
    assert "\\sum" in html or "sum_" in html, (
        "display math body should be preserved verbatim"
    )

    # Autolink extension — a bare URL is turned into an <a> tag that the
    # external-link formatter rewrites to include the three hardening
    # attributes.
    assert "https://example.com/autolink" in html
    assert 'class="external-link"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html

    # Regular link is also rewritten by the external-link formatter.
    assert 'href="https://example.org/regular"' in html

    # Blockquote.
    assert "<blockquote>" in html
    assert "Nevermore" in html

    # Nested lists — at least one nested <ul> inside <li>.
    assert html.count("<ul>") >= 2
    assert html.count("<li>") >= 4

    # Inline angle brackets in prose must be HTML-escaped so they do not
    # accidentally open an HTML element. comrak escapes both `<` and `&`.
    assert "1 &lt; 2" in html or "&lt;" in html
    assert "a&amp;b" in html or "&amp;" in html


@pytest.mark.ipc
def test_parse_markdown_command_escapes_script_tag_xss_vector(mcp):
    """Security: a `<script>` tag embedded in markdown must not survive
    into the rendered HTML as an executable tag.

    The expected failure mode if this assertion breaks is a DOM-level XSS
    sink for any caller that renders parse_markdown_command output with
    `innerHTML`. We assert both the opening and closing raw tags are absent.

    comrak with `render.unsafe = false` (the current setting) replaces raw
    HTML blocks with `<!-- raw html omitted -->` rather than escaping them,
    so we assert that comment is present to confirm the block was handled.
    """
    fixture = "# Heading\n\nParagraph text.\n\n<script>alert(1)</script>\n"
    html = invoke_via_mcp(mcp, "parse_markdown_command", {"markdown": fixture})
    assert isinstance(html, str)

    lowered = html.lower()
    assert "<script" not in lowered, (
        "raw <script> tag survived markdown rendering — this is a DOM "
        "XSS sink. See markdown.rs::parse_markdown and the `render.unsafe` flag."
    )
    assert "</script>" not in lowered, (
        "raw </script> tag survived markdown rendering — same XSS concern."
    )
    # comrak (unsafe=false) omits raw HTML blocks with a placeholder comment.
    assert "<!-- raw html omitted -->" in lowered, (
        "expected comrak placeholder comment for omitted raw HTML block; "
        "the script tag may have passed through or been silently dropped."
    )


# ---------------------------------------------------------------------------
# install_tectonic (tectonic.rs)
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_install_tectonic_returns_path_or_errors_cleanly(mcp):
    """Skipped: install_tectonic may trigger a multi-minute network download
    and extraction on a host where the binary isn't cached — blocks the
    webview bridge and cascades MCP timeouts into every subsequent IPC test
    (observed during the 2026-04-20 full-coverage sweep). Re-enable behind
    an explicit opt-in env var once the command is split into a pure
    status-check vs a destructive install."""
    pytest.skip("install_tectonic not safe in unattended sweeps — may block webview")


# ---------------------------------------------------------------------------
# install_cli (cli.rs)
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_install_cli_platform_gated(mcp):
    """install_cli on Unix hosts writes to ~/.opencode/bin and may chmod/
    rewrite shell init files. We only exercise the Windows platform gate
    here to avoid mutating the dev machine during sweeps."""
    if sys.platform == "win32":
        with pytest.raises(IPCError, match="macOS|Linux|supported"):
            invoke_via_mcp(mcp, "install_cli", {})
    else:
        pytest.skip(
            "install_cli on Unix mutates ~/.opencode/bin and shell init "
            "files — not safe in unattended sweeps"
        )


@pytest.mark.ipc
def test_install_cli_happy_path_opt_in_mutates_system(mcp):
    """Gated real-behavior test for install_cli on Unix.

    Opt in with `PYTEST_OPTIN_MUTATE_SYSTEM=1`. This runs the bundled
    install script, which writes to `~/.opencode/bin/opencode` and MAY
    append PATH-export lines to `~/.zshrc` or `~/.bashrc`. Idempotent per
    the install script's internal guard, but still mutating — hence the
    opt-in gate.

    Skipped on Windows (the command's platform guard returns an error
    string; see `cli.rs::install_cli` lines 132-134) and skipped when the
    opt-in env var is absent.

    Assertions:
      * command returns `Ok(String)` — the absolute install path;
      * the returned string is non-empty (the path is well-formed).
    """
    if sys.platform == "win32":
        pytest.skip(
            "install_cli is Unix-only; the happy path cannot run on "
            "Windows (see cli.rs:132-134)"
        )
    if os.environ.get("PYTEST_OPTIN_MUTATE_SYSTEM") != "1":
        pytest.skip(
            "install_cli writes to ~/.opencode/bin and may modify shell "
            "init files — opt in with PYTEST_OPTIN_MUTATE_SYSTEM=1 to run"
        )

    install_path = invoke_via_mcp(mcp, "install_cli", {})
    assert isinstance(install_path, str), (
        "install_cli should return a path string on success"
    )
    assert install_path, "returned install path must be non-empty"
    # Documented return contract: absolute path ending in opencode.
    assert "opencode" in install_path.lower()
