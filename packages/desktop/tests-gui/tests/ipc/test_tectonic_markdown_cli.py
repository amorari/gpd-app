"""Contract tests for tectonic.rs, markdown.rs, and cli.rs commands.

Three commands covered (one per file):
  - install_tectonic (tectonic.rs)
  - parse_markdown_command (markdown.rs)
  - install_cli (cli.rs)

Runs against live GPD debug build.
"""
from __future__ import annotations

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
