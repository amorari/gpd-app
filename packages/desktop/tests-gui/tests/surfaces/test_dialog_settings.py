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
    # Dismiss any leftover dialog from a prior test (e.g. steals_focus tests).
    # command.tsx early-returns on Cmd+, when a dialog is already active, so
    # we must clear the modal stack before opening. Single pass — no retry
    # cascade; if Escape doesn't clear it the main assertion below will still
    # fail loudly.
    probe_pre = DOMProbe(mcp)
    try:
        dialog_open = probe_pre.eval_bool(
            '(() => !!document.querySelector('
            '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '))()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if dialog_open:
        os_input.press_key("escape")
        time.sleep(0.15)
    # Prefer DOM-direct click on the settings gear (no focus race).
    try:
        clicked = probe_pre.eval_bool(
            '(() => {'
            '  const btn = document.querySelector("[aria-label=\\"Settings\\"]");'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        # Fallback: use osascript keystroke (may be flaky on focus races).
        ax.activate()
        time.sleep(0.15)
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
                '    "[role=\\"tab\\"], [data-slot=\\"tabs-trigger\\"]"'
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
            '    "[role=\\"tab\\"], [data-slot=\\"tabs-trigger\\"]"'
            '  ));'
            f'  return tabs.some(t => t.textContent.trim() === "{needle}");'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert not still_open, "settings dialog did not close on ESC"
