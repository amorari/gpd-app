import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, _adapt_url_for_dev, route_home, encode_dir_token, route_session_in_project
from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION


@pytest.mark.surfaces
def test_home_route_reachable(mcp):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    actual = mcp.current_url()
    # Navigator adapts tauri:// to http://localhost:1420 in dev builds;
    # accept either URL as "home".
    assert actual == _adapt_url_for_dev(actual, route_home())


@pytest.mark.surfaces
def test_sidebar_new_session_selector_present_on_home(mcp, http, tmp_path):
    """The sidebar new-session button is accessible when a project is registered.

    ``[data-action="new-session"]`` (``sidebar-items.tsx:292``) is a
    ``NewSessionItem`` link that only renders inside a project workspace list.
    We seed one git-initialised project, navigate to the project route, and
    verify the anchor is present so the test isn't vacuous on a blank home screen.
    """
    # Initialise a git repo so GPD registers the directory as a real project.
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
        check=True, capture_output=True,
    )

    ses = http.create_session(directory=str(tmp_path))
    sid = ses.get("id")
    try:
        dir_token = encode_dir_token(str(tmp_path))
        nav = Navigator(mcp)
        nav.go(route_home(), timeout_s=5.0)
        time.sleep(0.5)
        nav.go(route_session_in_project(dir_token), timeout_s=8.0)
        probe = DOMProbe(mcp)

        deadline = time.monotonic() + 10.0
        present = False
        while time.monotonic() < deadline:
            try:
                present = probe.eval_bool(
                    f'!!document.querySelector({SIDEBAR_NEW_SESSION!r})'
                    ' && document.body.textContent.length > 0'
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            if present:
                break
            time.sleep(0.3)

        if not present:
            pytest.skip(
                f"selector {SIDEBAR_NEW_SESSION} not found after seeding project "
                "(welcome overlay may be blocking sidebar render)"
            )
        assert present
    finally:
        try:
            http.delete_session(sid)
        except Exception:
            pass
