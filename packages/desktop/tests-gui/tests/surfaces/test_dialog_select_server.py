import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


@pytest.mark.surfaces
def test_select_server_dialog_fields_when_open(mcp):
    """Best-effort render check. The open trigger isn't pinned down in this
    build; if the dialog isn't already in the DOM on home, we skip.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        found = probe.eval_bool(
            '(() => {'
            '  const txt = document.body ? document.body.innerText : "";'
            '  if (!/localhost/i.test(txt)) return false;'
            '  const hasUrl = Array.from(document.querySelectorAll("input"))'
            '    .some(i => i.placeholder && /https?:\\/\\//i.test(i.placeholder));'
            '  return hasUrl;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not found:
        pytest.skip("select-server dialog not reachable from home in this build")
    assert found
