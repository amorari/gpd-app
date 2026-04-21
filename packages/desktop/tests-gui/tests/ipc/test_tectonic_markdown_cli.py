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
    """install_tectonic returns a string path on success. We don't force a
    real network download here; on CI/dev machines the binary is usually
    already cached in ~/.config/gpd/.capabilities/tectonic/bin/tectonic,
    in which case the command is a cheap no-op. If it's not cached AND the
    network is unavailable, the command returns a well-formed error string
    — both outcomes are acceptable from the contract's perspective.
    """
    try:
        result = invoke_via_mcp(mcp, "install_tectonic", {})
    except IPCError as e:
        # Accept: no-network / no-matching-asset / extraction failure.
        # Reject: arg deserialization error (would mean the command signature
        # changed and our catalog is stale).
        msg = str(e).lower()
        assert "tectonic" in msg or "github" in msg or "download" in msg or "network" in msg or "manual" in msg, (
            f"unexpected error shape: {e!r}"
        )
        return
    assert isinstance(result, str)
    assert "tectonic" in result.lower()


# ---------------------------------------------------------------------------
# install_cli (cli.rs)
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_install_cli_platform_gated(mcp):
    """install_cli is unix-only — it refuses on Windows with a plain error.
    On macOS/Linux it may succeed (returns install path) or fail with a
    specific error (e.g. sidecar missing in a dev build); both are
    acceptable contract outcomes — we don't want CI to actually reshuffle
    the user's ~/.opencode/bin."""
    if sys.platform == "win32":
        with pytest.raises(IPCError, match="macOS|Linux|supported"):
            invoke_via_mcp(mcp, "install_cli", {})
    else:
        try:
            result = invoke_via_mcp(mcp, "install_cli", {})
            assert isinstance(result, str)
            assert result  # non-empty path
        except IPCError as e:
            # Acceptable failure modes on dev machines: sidecar binary not
            # bundled, install script missing, permission denied writing
            # to ~/.opencode/bin. Reject only schema-level failures.
            msg = str(e).lower()
            assert any(
                hint in msg
                for hint in (
                    "sidecar",
                    "install",
                    "script",
                    "permission",
                    "path",
                    "bin",
                    "failed",
                )
            ), f"unexpected error shape from install_cli: {e!r}"
