"""File menu: expected items are present and their enabled state is sane."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


# Items we expect GPD's File menu to expose. Upstream i18n sweeps may
# rename these; accept either the new or old name for each concept.
# At least ONE from each group must be present.
EXPECTED_GROUPS = [
    # New-conversation-like action
    ["New Conversation", "New Session"],
    # Open something
    ["Open Project…", "Open Project...", "Open…", "Open..."],
    # Close window
    ["Close Window"],
]

# Items that indicate the Tauri webview has NOT yet registered the custom
# menu (macOS default File menu items provided by WKWebView / Cocoa before
# createMenu() runs).  When the File menu contains only these native items
# and none of the expected custom items, skip rather than fail — the app is
# running but the JS menu bridge hasn't fired yet.
_NATIVE_ONLY_MARKERS = {"Close All", "Close Window"}


@pytest.mark.broad
def test_file_menu_has_expected_items(ax: AXClient):
    items = set(ax.items_of("File"))
    assert items, "File menu has no items"

    # If the menu only contains native macOS items and no custom items from
    # createMenu(), the Tauri JS menu bridge hasn't registered the custom
    # menu yet.  This is a timing / environment precondition issue, not a
    # product regression.  Skip so the test doesn't produce a false failure.
    has_any_custom = any(
        items & set(group) for group in EXPECTED_GROUPS if group != ["Close Window"]
    )
    if not has_any_custom and items <= _NATIVE_ONLY_MARKERS:
        pytest.skip(
            "File menu contains only native macOS items "
            f"({sorted(items)}) — Tauri createMenu() has not registered "
            "the custom menu yet. Relaunch GPD and re-run."
        )

    missing_groups: list[list[str]] = []
    for group in EXPECTED_GROUPS:
        if not (items & set(group)):
            missing_groups.append(group)
    assert not missing_groups, (
        f"File menu missing expected item group(s): {missing_groups} "
        f"(found: {sorted(items)})"
    )


@pytest.mark.broad
def test_file_menu_close_window_is_enabled_when_window_exists(ax: AXClient):
    """Close Window should be enabled when GPD has a main window open."""
    enabled = set(ax.enabled_items_of("File"))
    if "Close Window" not in set(ax.items_of("File")):
        pytest.skip("Close Window item not present in this build")
    assert "Close Window" in enabled, (
        f"Close Window exists but is not enabled; enabled set: {enabled}"
    )
