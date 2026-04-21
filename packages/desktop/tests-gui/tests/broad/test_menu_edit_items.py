"""Edit menu: standard macOS clipboard items present."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


# Every Cocoa app gets these for free via NSApplication's standard Edit
# menu; they're stable across locales in principle (though the app itself
# may show localized forms — we match a set of candidates per concept).
EXPECTED_GROUPS = [
    ["Undo", "Undo Typing", "Undo Edit"],
    ["Redo"],
    ["Cut"],
    ["Copy"],
    ["Paste"],
    ["Select All", "Select all"],
]


@pytest.mark.broad
def test_edit_menu_has_standard_clipboard_items(ax: AXClient):
    items = set(ax.items_of("Edit"))
    assert items, "Edit menu has no items"
    missing = [g for g in EXPECTED_GROUPS if not (items & set(g))]
    assert not missing, (
        f"Edit menu missing expected concept(s): {missing} "
        f"(found: {sorted(items)})"
    )
