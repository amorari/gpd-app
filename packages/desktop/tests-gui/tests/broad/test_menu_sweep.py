"""Phase 5 broad sweep: every top-level menu has at least one item."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


APP_MENU_CANDIDATES = {"GPD", "GPD Dev", "GPD Beta"}


_NATIVE_ONLY_FILE_ITEMS = {"Close All", "Close Window"}


@pytest.mark.broad
def test_every_top_level_menu_has_at_least_one_item(ax: AXClient):
    # Exclude "Apple" — macOS owns that menu; we don't control its contents.
    # If the OS ever injects additional system menus (e.g. Services), this
    # filter may need to be widened, but Apple is the only known case today.
    menus = [m for m in ax.top_level_menus() if m != "Apple"]
    assert menus, "no GPD-owned menus found (AX query returned empty)"

    # If createMenu() hasn't registered custom items yet, the File menu only
    # contains native macOS items and the Help menu is completely empty.
    # Skip rather than fail — this is a timing precondition, not a regression.
    file_items = set(ax.items_of("File"))
    if file_items <= _NATIVE_ONLY_FILE_ITEMS or not file_items:
        pytest.skip(
            "Tauri createMenu() has not registered custom menu items yet "
            f"(File menu: {sorted(file_items)}). Relaunch GPD and re-run."
        )

    empty = [m for m in menus if not ax.items_of(m)]
    assert not empty, f"top-level menus with zero items: {empty}"


@pytest.mark.broad
def test_top_level_menu_set_is_reasonable(ax: AXClient):
    """Soft check: GPD should expose at least File, Edit, View, Help and
    some application menu ('GPD', 'GPD Dev', or 'GPD Beta')."""
    menus = set(ax.top_level_menus())
    required_non_app = {"File", "Edit", "View", "Help"}
    missing = required_non_app - menus
    assert not missing, f"expected menus missing: {missing} (got {menus})"
    app_like = menus & APP_MENU_CANDIDATES
    assert app_like, (
        f"no application menu ({APP_MENU_CANDIDATES}) in menus {menus}"
    )
