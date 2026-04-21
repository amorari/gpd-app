"""Contract tests for dependencies.rs commands.

dependencies.rs exposes three commands covering platform-specific dependency
install flows (macOS: Xcode Command Line Tools; Windows: winget; Linux:
read-only hint text). Runs against live GPD debug build.
"""
from __future__ import annotations

import sys

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


# ---------------------------------------------------------------------------
# install_git_macos
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_install_git_macos_platform_gated(mcp):
    """On macOS the command launches or reports-already-installed; on other
    platforms it returns an explicit "only available on macOS" error.

    We don't actually want a real install dialog during CI. Fortunately
    xcode-select --install on a macOS host where CLT is already present
    returns "Xcode Command Line Tools are already installed." — a normal
    Ok variant. On non-macOS hosts we assert the platform gate fires.
    """
    if sys.platform == "darwin":
        result = invoke_via_mcp(mcp, "install_git_macos", {})
        assert isinstance(result, dict)
        assert "launched" in result
        assert "message" in result
        # launched=True regardless of whether CLT were newly installed or
        # already present (the Rust code treats "already installed" as ok).
        assert result["launched"] is True
    else:
        with pytest.raises(IPCError, match="macOS"):
            invoke_via_mcp(mcp, "install_git_macos", {})


# ---------------------------------------------------------------------------
# install_git_windows
# ---------------------------------------------------------------------------


@pytest.mark.ipc
def test_install_git_windows_platform_gated(mcp):
    """On non-Windows hosts install_git_windows returns an explicit "only
    available on Windows" error. We don't exercise the happy path here —
    invoking winget install on CI is slow, uninstallable, and pointless
    for a contract test."""
    if sys.platform == "win32":
        # On Windows winget may or may not be installed; a successful launch
        # is legitimate but not required. Accept either the Ok shape or a
        # well-formed error.
        try:
            result = invoke_via_mcp(mcp, "install_git_windows", {})
            assert isinstance(result, dict)
            assert "launched" in result and "message" in result
        except IPCError:
            pass  # winget missing / UAC-denied are acceptable on a runner
    else:
        with pytest.raises(IPCError, match="Windows"):
            invoke_via_mcp(mcp, "install_git_windows", {})


# ---------------------------------------------------------------------------
# linux_install_hint
# ---------------------------------------------------------------------------


@pytest.mark.ipc
@pytest.mark.parametrize(
    "tool,needle",
    [
        ("git", "git"),
        ("python", "python3"),
        ("latex", "texlive"),
        ("tectonic", "tectonic"),
        ("pdf-tools", "poppler"),
    ],
)
def test_linux_install_hint_returns_known_snippets(mcp, tool, needle):
    """linux_install_hint returns a shell-snippet or URL string per known
    tool id. The Rust match returns the empty string for unknown ids — we
    exercise that sentinel below."""
    result = invoke_via_mcp(mcp, "linux_install_hint", {"tool": tool})
    assert isinstance(result, str)
    assert needle in result


@pytest.mark.ipc
def test_linux_install_hint_unknown_tool_returns_empty(mcp):
    """An unrecognised tool id is not an error — the command returns ""."""
    result = invoke_via_mcp(
        mcp, "linux_install_hint", {"tool": "completely-made-up-tool-xyz"}
    )
    assert result == ""
