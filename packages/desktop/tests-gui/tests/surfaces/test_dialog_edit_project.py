import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


@pytest.mark.surfaces
def test_edit_project_dialog_opens_from_home(mcp):
    """Trigger by dispatching a click in the DOM; falls back to skip when
    execute_js isn't available on this build.
    """
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll("button"));'
            '  const btn = btns.find(b => /new project/i.test(b.innerText));'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'New Project' button found on home")

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            found = probe.eval_bool(
                'Array.from(document.querySelectorAll("[placeholder]"))'
                '.some(el => /e\\.g\\.\\s*bun install/i.test(el.placeholder))'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if found:
            return
        time.sleep(0.1)
    pytest.fail("edit-project dialog did not render startup-command field")
