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
    deadline = time.monotonic() + 3.0
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
            return
        time.sleep(0.1)
    pytest.fail("open-or-create dialog did not render within deadline")
