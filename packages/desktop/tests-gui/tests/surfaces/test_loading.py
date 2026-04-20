import time

import pytest

from gpd_tests.helpers.navigator import Navigator, route_home, route_loading


@pytest.mark.surfaces
def test_loading_redirects_to_home_within_deadline(mcp, http):
    nav = Navigator(mcp)
    nav.go(route_loading(), timeout_s=5.0, poll_s=0.1)
    # Don't assert we reach /loading — some builds redirect immediately.
    # Instead: wait until URL is home route.
    deadline = time.monotonic() + 10.0
    url = ""
    while time.monotonic() < deadline:
        url = mcp.current_url()
        if url == route_home():
            return
        time.sleep(0.1)
    pytest.fail(f"loading did not transition to home within 10s; last url={url!r}")
