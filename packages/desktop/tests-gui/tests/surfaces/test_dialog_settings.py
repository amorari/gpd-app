import subprocess
import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


# The "General" tab label is specific to the settings dialog — it won't be
# found on any other surface — so it serves as a reliable presence signal.
_SETTINGS_GENERAL_TAB = "General"


@pytest.mark.surfaces
@pytest.mark.steals_focus
def test_settings_opens_via_cmd_comma_and_closes_on_escape(mcp, ax, os_input):
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    # Bring GPD to the foreground using the configured app_name, not a
    # hard-coded application name.
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
    # Look for the "General" settings tab — this is unique to the settings
    # dialog and won't false-positive on the sidebar's Settings icon label.
    needle = _SETTINGS_GENERAL_TAB.replace('"', '\\"')
    opened = False
    while time.monotonic() < deadline:
        try:
            opened = probe.eval_bool(
                '(() => {'
                '  const tabs = Array.from(document.querySelectorAll('
                '    "[role=\\"tab\\"], [data-component=\\"tabs-trigger\\"]"'
                '  ));'
                f'  return tabs.some(t => t.textContent.trim() === "{needle}");'
                '})()'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable ({e})")
        if opened:
            break
        time.sleep(0.1)
    if not opened:
        pytest.fail("settings dialog never appeared (General tab not found)")
    # Close via ESC.
    os_input.press_key("escape")
    time.sleep(0.3)
    try:
        still_open = probe.eval_bool(
            '(() => {'
            '  const tabs = Array.from(document.querySelectorAll('
            '    "[role=\\"tab\\"], [data-component=\\"tabs-trigger\\"]"'
            '  ));'
            f'  return tabs.some(t => t.textContent.trim() === "{needle}");'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert not still_open, "settings dialog did not close on ESC"
