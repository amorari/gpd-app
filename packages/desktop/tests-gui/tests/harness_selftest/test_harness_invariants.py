"""Harness self-tests: if these fail, every other test result is suspect."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.harness_selftest
def test_python_version_meets_floor():
    import sys
    assert sys.version_info >= (3, 12), f"Python too old: {sys.version_info}"


@pytest.mark.harness_selftest
def test_uv_available():
    import shutil
    assert shutil.which("uv"), "uv not in PATH — cannot run any test"


@pytest.mark.harness_selftest
def test_cliclick_available_when_os_input_imported():
    """If os_input has been imported at module scope, cliclick must be available."""
    import shutil
    # Don't import os_input — just check the tool is present for when tests need it.
    present = shutil.which("cliclick") is not None
    if not present:
        pytest.skip("cliclick not available — os_input tests will skip")


@pytest.mark.harness_selftest
def test_osascript_available():
    import shutil
    assert shutil.which("osascript"), "osascript missing — AX tests cannot run"


@pytest.mark.harness_selftest
def test_gpd_app_path_resolves_if_set():
    app_path = os.environ.get("GPD_APP_PATH")
    if not app_path:
        pytest.skip("GPD_APP_PATH not set")
    p = Path(app_path)
    assert p.exists(), f"GPD_APP_PATH points at non-existent: {app_path}"
    assert p.suffix == ".app", f"GPD_APP_PATH is not an .app bundle: {app_path}"


@pytest.mark.harness_selftest
def test_mcp_socket_discoverable_when_gpd_running():
    """If a GPD process is running, a MCP socket should be discoverable."""
    import subprocess
    out = subprocess.run(
        ["pgrep", "-f", ".app/Contents/MacOS/GPD"],
        capture_output=True, text=True, check=False,
    )
    pids = [p for p in out.stdout.split() if p.strip()]
    if not pids:
        pytest.skip("no GPD process running")
    import glob
    socks = glob.glob("/var/folders/*/*/T/tauri-mcp.sock")
    assert socks, "GPD is running but no MCP socket found — plugin may have crashed"


@pytest.mark.harness_selftest
def test_sidecar_available_when_gpd_running():
    """If GPD is running, the opencode-cli sidecar should also be running."""
    import subprocess
    gpd = subprocess.run(["pgrep", "-f", ".app/Contents/MacOS/GPD"],
                        capture_output=True, text=True, check=False)
    if not gpd.stdout.strip():
        pytest.skip("GPD not running")
    sidecar = subprocess.run(["pgrep", "-f", "opencode-cli.*serve"],
                            capture_output=True, text=True, check=False)
    assert sidecar.stdout.strip(), (
        "GPD is running but sidecar isn't — launch sequence may have failed"
    )


@pytest.mark.harness_selftest
def test_en_fixture_is_fresh_enough():
    """The en.json fixture must not be missing entire top-level namespaces."""
    import json
    fixture = Path(__file__).resolve().parent.parent.parent / "gpd_tests" / "fixtures" / "en.json"
    assert fixture.exists(), f"i18n fixture missing: {fixture}"
    data = json.loads(fixture.read_text())
    # A recent fixture should have at least ~800 keys (current target is 1000+).
    assert len(data) >= 800, f"fixture seems sparse: only {len(data)} keys"
    # Key namespaces that MUST exist per current product state.
    required_prefixes = ["welcome.", "home.", "sidebar.", "session.", "dialog.", "error."]
    for prefix in required_prefixes:
        matching = [k for k in data if k.startswith(prefix)]
        assert matching, f"fixture missing all keys under '{prefix}*'"


@pytest.mark.harness_selftest
def test_tauri_commands_fixture_is_fresh():
    """tauri_commands.json must reflect the current source. Regenerate if this fails."""
    repo = Path(__file__).resolve().parents[4]
    script = repo / "packages/desktop/tests-gui/scripts/extract_tauri_commands.py"
    fixture = repo / "packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json"

    result = subprocess.run(
        ["uv", "run", "python", str(script)],
        cwd=repo / "packages/desktop/tests-gui",
        capture_output=True,
        text=True,
        check=True,
    )
    live = json.loads(result.stdout)
    stored = json.loads(fixture.read_text())
    assert live == stored, (
        "tauri_commands.json is stale — "
        "rerun: uv run python scripts/extract_tauri_commands.py > "
        "gpd_tests/fixtures/tauri_commands.json"
    )
