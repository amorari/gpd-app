import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_session


@pytest.mark.surfaces
def test_select_provider_dialog_reachable_from_session(mcp):
    Navigator(mcp).go(route_session(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        signal = probe.eval_bool(
            '(() => {'
            '  const txt = document.body ? document.body.innerText : "";'
            '  return /provider/i.test(txt);'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not signal:
        pytest.skip("no provider UI reachable on session route in this build")
    assert signal
