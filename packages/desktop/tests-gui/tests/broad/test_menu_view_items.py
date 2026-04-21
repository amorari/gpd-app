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


@pytest.mark.broad
def test_view_menu_non_empty(ax: AXClient):
    items = ax.items_of("View")
    assert items, "View menu has no items"


@pytest.mark.broad
def test_view_menu_has_at_least_one_typical_group(ax: AXClient):
    items = set(ax.items_of("View"))
    matched = [g for g in TYPICAL_GROUPS if items & set(g)]
    assert matched, (
        f"no expected View concepts found; got {sorted(items)}"
    )
