"""Phase 3 flow: gpd://session/<id> deep link resolves to the session route."""
from __future__ import annotations

import subprocess
import time

import pytest

from gpd_tests.helpers.navigator import route_session


@pytest.mark.flows
def test_deep_link_session_routes_to_session(http, mcp, scratch_project_dir):
    # Create a session so we have a real id to route to.
    session = http.create_session(directory=str(scratch_project_dir))
    sid = session["id"]

    # Trigger the deep link. `open` returns immediately; routing is async.
    subprocess.run(
        ["open", f"gpd://session/{sid}"],
        capture_output=True,
        check=True,
    )

    expected = route_session(sid)
    deadline = time.monotonic() + 10.0
    last = ""
    while time.monotonic() < deadline:
        try:
            last = mcp.current_url()
        except Exception:
            last = ""
        if last.endswith(f"/session/{sid}"):
            return
        time.sleep(0.2)
    pytest.fail(
        f"deep link did not route to /session/{sid}; current={last!r} "
        f"(expected prefix: {expected})"
    )
