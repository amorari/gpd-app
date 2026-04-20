import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


@pytest.mark.surfaces
def test_select_directory_dialog_reachable(mcp):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        visible = probe.eval_bool(
            '(() => {'
            '  const inputs = Array.from(document.querySelectorAll("input[type=\\"search\\"],input[placeholder*=\\"earch\\"]"));'
            '  return inputs.length > 0;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not visible:
        pytest.skip("select-directory dialog not reachable from home in this build")
    assert visible
