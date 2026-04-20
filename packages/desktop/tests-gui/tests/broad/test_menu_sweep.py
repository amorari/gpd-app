"""Phase 5 broad sweep: every top-level menu has at least one item."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


@pytest.mark.broad
def test_every_top_level_menu_has_at_least_one_item(ax: AXClient):
    menus = [m for m in ax.top_level_menus() if m != "Apple"]
    assert menus, "no GPD-owned menus found (AX query returned empty)"
    empty = [m for m in menus if not ax.items_of(m)]
    assert not empty, f"top-level menus with zero items: {empty}"


@pytest.mark.broad
def test_top_level_menu_set_is_reasonable(ax: AXClient):
    """Soft check: GPD should expose at least File, Edit, View, Help and
    some application menu ('GPD' or 'GPD Dev')."""
    menus = set(ax.top_level_menus())
    required_non_app = {"File", "Edit", "View", "Help"}
    missing = required_non_app - menus
    assert not missing, f"expected menus missing: {missing} (got {menus})"
    app_like = menus & {"GPD", "GPD Dev"}
    assert app_like, (
        f"no application menu ('GPD' or 'GPD Dev') in menus {menus}"
    )
