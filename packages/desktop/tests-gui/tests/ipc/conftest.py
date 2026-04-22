"""IPC suite fixtures — webview warmup guard."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module", autouse=True)
def _warmup_webview(app_state):
    """Ensure the JS bridge is stable before IPC tests start.

    ipc tests call invoke_via_mcp immediately after the mcp ping. If the
    bridge is in a transient state (e.g. recovering from a page reload
    triggered by a preceding flows test), execute_js will time out and the
    first IPC call fails.

    Critically: do NOT navigate here. Navigator.go("tauri://localhost/")
    causes a full WKWebView reload. Each reload creates a transient window
    where the execute-js listener in setupPluginListeners() has not yet
    registered, and any execute_js call during that window returns
    "Timeout waiting for JS execution" — which propagates as MCPError and
    fails IPC tests. Waiting for 2 consecutive successes is sufficient to
    confirm the bridge is active without causing an extra reload.

    Best-effort: if the bridge is truly dead, individual tests will fail
    loudly with their own diagnostic message.
    """
    from gpd_tests.drivers.mcp import MCPClient, MCPError, MCPTimeout
    from gpd_tests.helpers.ipc import invoke_via_mcp
    from gpd_tests.helpers.timings import wait_until

    try:
        client = MCPClient()
        client.ping()
        # Wait for 2 consecutive execute_js successes without navigating.
        consecutive = [0]

        def _bridge_ready() -> bool:
            try:
                client.execute_js("null")
                consecutive[0] += 1
                return consecutive[0] >= 2
            except Exception:
                consecutive[0] = 0
                return False

        wait_until(_bridge_ready, timeout_s=30.0, poll_s=1.0)
        # Prime the Tauri IPC bridge with a cheap no-arg call so the first
        # real invoke in this module doesn't hit the MCP socket timeout while
        # the bridge finishes its cold-start work (store init, file I/O, etc).
        invoke_via_mcp(client, "get_display_backend", {}, deadline_s=10.0)
    except (MCPError, MCPTimeout, Exception):
        pass
