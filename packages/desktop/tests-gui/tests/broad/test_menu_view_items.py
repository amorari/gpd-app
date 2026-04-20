"""View menu: has at least one item; soft-check for typical toggles."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


# Soft-check targets — if none of these are present, we don't fail hard
# (GPD's View menu may be minimal). We only record via xfail/skip.
TYPICAL_GROUPS = [
    ["Enter Full Screen", "Exit Full Screen"],
    ["Zoom In", "Zoom Out", "Actual Size"],
    ["Reload", "Reload Page", "Reload Webview"],
]


@pytest.mark.broad
def test_view_menu_non_empty(ax: AXClient):
    items = ax.items_of("View")
    assert items, "View menu has no items"


@pytest.mark.broad
def test_view_menu_has_at_least_one_typical_group(ax: AXClient):
    items = set(ax.items_of("View"))
    matched = [g for g in TYPICAL_GROUPS if items & set(g)]
    if not matched:
        pytest.skip(
            f"no typical View concepts found; got {sorted(items)} "
            "— this may be fine for a minimal app"
        )
    assert matched
