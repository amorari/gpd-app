import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home
from gpd_tests.helpers.selectors import TEXT_SIDEBAR_SETTINGS


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_settings_opens_via_cmd_comma_and_closes_on_escape(mcp, ax, os_input):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    ax.activate()
    # ⌘, — keystroke with cmd-down.
    subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "," using command down',
        ],
        check=True,
    )
    probe = DOMProbe(mcp)
    deadline = time.monotonic() + 5.0
    needle = TEXT_SIDEBAR_SETTINGS.replace('"', '\\"')
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                f'document.body && document.body.innerText.includes("{needle}")'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)
    if not opened:
        pytest.fail("settings dialog never appeared")
    # Close via ESC.
    os_input.press_key("escape")
    time.sleep(0.3)
    try:
        still_open = probe.eval_bool(
            f'document.body && document.body.innerText.includes("{needle}")'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert not still_open, "settings dialog did not close on ESC"
