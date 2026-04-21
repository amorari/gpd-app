"""IPC suite fixtures — webview warmup guard."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def _warmup_webview(app_state):
    """Navigate to home once per module so the JS bridge is active.

    ipc tests call invoke_via_mcp immediately after the mcp ping, without
    any prior DOM navigation. If the webview is throttled (macOS backgrounds
    it between pytest invocations) or left in a degraded state by the
    preceding surfaces run, the first execute_js call hits the 10 s socket
    timeout before the 20 s invoke deadline. Navigating to home warms the
    bridge and brings the webview to foreground.

    Best-effort: if the bridge is truly dead, individual tests will fail
    loudly with their own diagnostic message rather than a cold-start timeout.
    """
    from gpd_tests.drivers.mcp import MCPClient, MCPError, MCPTimeout
    from gpd_tests.helpers.navigator import Navigator, route_home

    try:
        client = MCPClient()
        client.ping()
        Navigator(client).go(route_home(), timeout_s=8.0)
    except (MCPError, MCPTimeout, Exception):
        pass
