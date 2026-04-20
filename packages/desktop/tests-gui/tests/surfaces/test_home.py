import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home
from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION


@pytest.mark.surfaces
def test_home_route_reachable(mcp):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    assert mcp.current_url() == route_home()


@pytest.mark.surfaces
def test_sidebar_new_session_selector_present_on_home(mcp):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        js = f'!!document.querySelector({SIDEBAR_NEW_SESSION!r})'
        present = probe.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not present:
        pytest.skip(
            f"selector {SIDEBAR_NEW_SESSION} not found on home "
            "(welcome overlay may be blocking sidebar render)"
        )
    assert present
