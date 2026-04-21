"""Tests for the DialogOpenOrCreateProject dialog.

The dialog is triggered by the "Open Existing / Create New" button
(i18n key: home.openOrCreate) on the home surface.
"""

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


@pytest.mark.surfaces
def test_open_or_create_project_dialog_opens_from_home(mcp):
    """Click the 'Open Existing / Create New' button and verify the dialog."""
    Navigator(mcp).go(route_home(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        clicked = probe.eval_bool(
            '(() => {'
            '  const btns = Array.from(document.querySelectorAll("button"));'
            '  const btn = btns.find('
            '    b => /open.*create|create.*project|new project/i.test(b.innerText)'
            '  );'
            '  if (!btn) return false;'
            '  btn.click();'
            '  return true;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not clicked:
        pytest.skip("no 'Open Existing / Create New' (or similar) button found on home")

    # Wait for the dialog — look for the combined-picker title or subtitle which
    # are unique to DialogOpenOrCreateProject (home.combinedPicker.title /
    # home.combinedPicker.subtitle in en.ts).
    #
    # IMPORTANT: the button click may open a native NSOpenPanel (file picker)
    # which blocks GPD's event loop. The finally block below sends Escape to
    # dismiss any open native dialog before the next test starts, regardless
    # of how this test exits (pass, fail, or skip).
    found = False
    deadline = time.monotonic() + 3.0
    try:
        while time.monotonic() < deadline:
            try:
                found = probe.eval_bool(
                    '(() => {'
                    '  const txt = document.body ? document.body.innerText : "";'
                    '  return ('
                    '    /open or create/i.test(txt) ||'
                    '    /open existing folder/i.test(txt) ||'
                    '    /create new folder/i.test(txt)'
                    '  );'
                    '})()'
                )
            except ProbeSkip as e:
                pytest.skip(f"execute_js unavailable ({e})")
            if found:
                break
            time.sleep(0.1)
    finally:
        # Dismiss any open native dialog so GPD's event loop is unblocked for
        # the next test. This is a no-op when no dialog is open.
        import subprocess as _sp
        import time as _t
        _sp.run(
            ["osascript", "-e",
             "tell application \"System Events\" to key code 53"],
            capture_output=True, check=False, timeout=5.0,
        )
        _t.sleep(0.3)

    if not found:
        pytest.fail("open-or-create dialog did not render within deadline")
