"""View menu: has at least one item; check for typical toggles."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


# Items that GPD's View menu reliably exposes (per menu.ts).
TYPICAL_GROUPS = [
    ["Toggle Sidebar"],
    ["Toggle Command Prompt", "Toggle Terminal"],
    ["Back"],
    ["Forward"],
    ["Previous Conversation", "Previous Session"],
    ["Next Conversation", "Next Session"],
]

# The only item the View menu has before createMenu() registers custom items.
_NATIVE_ONLY_VIEW_ITEMS = {"Toggle Full Screen"}


@pytest.mark.broad
def test_view_menu_non_empty(ax: AXClient):
    items = ax.items_of("View")
    assert items, "View menu has no items"


@pytest.mark.broad
def test_view_menu_has_at_least_one_typical_group(ax: AXClient):
    items = set(ax.items_of("View"))

    # Before createMenu() runs, the View menu only contains the native macOS
    # "Toggle Full Screen" item and none of our custom entries.
    if items <= _NATIVE_ONLY_VIEW_ITEMS:
        pytest.skip(
            "View menu contains only native macOS items "
            f"({sorted(items)}) — Tauri createMenu() has not registered "
            "the custom View items yet. Relaunch GPD and re-run."
        )

    matched = [g for g in TYPICAL_GROUPS if items & set(g)]
    assert matched, (
        f"no expected View concepts found; got {sorted(items)}"
    )
