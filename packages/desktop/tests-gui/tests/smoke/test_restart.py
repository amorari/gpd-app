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

    # Old PID must disappear (or change).
    transitioned = wait_until(
        lambda: (app_state.gpd_pid() or 0) != old_pid,
        timeout_s=15.0,
    )
    assert transitioned, f"GPD PID did not change from {old_pid} within 15s"

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
    assert wait_until(
        lambda: ax_client.menu_item_exists("File", "New Session"),
        timeout_s=10.0,
    ), "File > New Session menu not available after restart"
