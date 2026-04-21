import glob
import os

import pytest

from gpd_tests.helpers.timings import wait_until


@pytest.mark.restart
def test_restart_app_recovers_within_deadline(app_state, mcp):
    """restart_app must actually terminate the old process and bring a new one up.

    We snapshot the pre-restart PID, call restart_app (which the plugin builds
    may surface as MCPTimeout/empty-response since the socket closes mid-call),
    wait for the old PID to disappear and a new one to appear, then verify a
    fresh MCP connection pings.
    """
    from gpd_tests.drivers.mcp import MCPClient, MCPError, MCPTimeout

    old_pid = app_state.gpd_pid()
    assert old_pid is not None, "GPD must be running before restart test"

    try:
        mcp.restart_app()
    except (MCPError, MCPTimeout):
        # Socket closes mid-call during restart; expected for this plugin build.
        pass

    # Phase 1: wait for old PID to disappear from ps.
    old_gone = wait_until(
        lambda: app_state.gpd_pid() != old_pid,
        timeout_s=15.0,
    )
    assert old_gone, f"old GPD PID {old_pid} did not disappear within 15s"

    # Phase 2: wait for a new GPD process to appear.
    new_appeared = wait_until(
        lambda: app_state.gpd_pid() is not None,
        timeout_s=15.0,
    )
    assert new_appeared, "new GPD process did not appear within 15s after old PID disappeared"

    # Delete stale socket before wait_launched so MCPClient picks up the fresh one.
    for stale in glob.glob("/var/folders/*/*/T/tauri-mcp.sock"):
        try:
            os.unlink(stale)
        except OSError:
            pass

    # New process must be running. wait_launched refreshes _launched_pid
    # so app_state.sidecar_pid() re-binds to the live process tree.
    app_state.wait_launched(timeout_s=15.0)

    # Fresh client must ping successfully (resolves the socket at ctor time).
    MCPClient().ping()

    # AX tree must be re-mounted before subsequent tests run — if this test
    # returns while the menu bar is still being rebuilt, the next
    # AX-dependent test fails with "Invalid index".
    from gpd_tests.drivers.ax import AXClient

    # Menu queries don't require activation — do NOT steal focus here.
    ax_client = AXClient()
    # Accept either "New Conversation" (wave-2 i18n rename) or "New Session".
    assert wait_until(
        lambda: (
            ax_client.menu_item_exists("File", "New Conversation")
            or ax_client.menu_item_exists("File", "New Session")
        ),
        timeout_s=10.0,
    ), 'neither "File > New Conversation" nor "File > New Session" appeared after restart'
