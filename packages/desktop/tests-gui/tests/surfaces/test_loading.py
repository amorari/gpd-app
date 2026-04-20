import time

import pytest

from gpd_tests.helpers.navigator import route_home, route_loading


@pytest.mark.surfaces
def test_loading_redirects_to_home_within_deadline(mcp):
    # Fire-and-forget navigate — don't use Navigator.go() because it waits for
    # an exact URL match and /loading is not a real SPA route (the app
    # redirects it immediately to /).
    mcp.navigate(route_loading())
    deadline = time.monotonic() + 10.0
    url = ""
    while time.monotonic() < deadline:
        url = mcp.current_url()
        if url.endswith("/"):
            return
        time.sleep(0.1)
    pytest.fail(f"loading did not transition to home within 10s; last url={url!r}")
