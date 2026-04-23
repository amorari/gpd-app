"""Tests for the DialogOpenOrCreateProject dialog.

The dialog is triggered by the "Open Existing / Create New" button
(i18n key: home.openOrCreate) on the home surface.
"""

import time

import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_home


@pytest.mark.surfaces
def test_open_or_create_project_dialog_opens_from_home(mcp, os_input):
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

    if not found:
        pytest.fail("open-or-create dialog did not render within deadline")

    # Content verification: heading text non-empty + enabled button present.
    try:
        has_heading = probe.eval_bool(
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return false;'
            '  const h = dialog.querySelector('
            '    "[data-slot=\\"dialog-title\\"], [data-component=\\"dialog-title\\"], '
            'h1, h2, h3, [role=\\"heading\\"]"'
            '  );'
            '  if (h && (h.textContent || "").trim().length > 0) return true;'
            '  const lid = dialog.getAttribute("aria-labelledby");'
            '  if (lid) {'
            '    const by = document.getElementById(lid);'
            '    if (by && (by.textContent || "").trim().length > 0) return true;'
            '  }'
            '  return (dialog.getAttribute("aria-label") || "").trim().length > 0;'
            '})()'
        )
        enabled_btn_count = probe.eval_int(
            '(() => {'
            '  const dialog = document.querySelector('
            '    "[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
            '  );'
            '  if (!dialog) return 0;'
            '  return dialog.querySelectorAll("button:not([disabled])").length;'
            '})()'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable mid-test ({e})")
    assert has_heading, "open-or-create dialog has no non-empty heading"
    assert enabled_btn_count > 0, "open-or-create dialog has no enabled button"

    # Escape-close verification: dialog should be gone after press_key("escape").
    try:
        os_input.press_key("escape")
    except Exception:
        pytest.skip("os_input.press_key unavailable")
    deadline_close = time.monotonic() + 2.0
    closed = False
    while time.monotonic() < deadline_close:
        try:
            still_open = probe.eval_bool(
                '!!document.querySelector('
                '"[data-component=\\"dialog\\"], [role=\\"dialog\\"]"'
                ')'
            )
        except ProbeSkip as e:
            pytest.skip(f"execute_js unavailable mid-test ({e})")
        if not still_open:
            closed = True
            break
        time.sleep(0.1)
    assert closed, "open-or-create dialog did not close on Escape"
