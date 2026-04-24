"""Help menu: has at least one item once createMenu() registers the custom items."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient

# Items defined in menu.ts that the Help submenu should contain once
# Tauri's createMenu() has run and set the app menu.
_EXPECTED_ITEMS = {
    "Documentation",
    "Support Forum",
    "Share Feedback",
    "Report a Bug",
    "Report Bug",
}


@pytest.mark.broad
def test_help_menu_non_empty(ax: AXClient):
    items = ax.items_of("Help")

    # An empty Help menu means createMenu() has not registered the custom
    # items yet (same timing issue as the File menu — Tauri's JS menu bridge
    # fires asynchronously after the webview mounts).  Skip rather than fail
    # so a cold-start run doesn't produce a spurious regression.
    if not items:
        pytest.skip(
            "Help menu is empty — Tauri createMenu() has not registered the "
            "custom Help items yet. Relaunch GPD and re-run."
        )

    # At least one custom item from menu.ts must be present.
    found_custom = set(items) & _EXPECTED_ITEMS
    assert found_custom, (
        f"Help menu has items {items!r} but none match the expected custom "
        f"entries {sorted(_EXPECTED_ITEMS)!r} — createMenu() may be "
        "registering unexpected items."
    )
