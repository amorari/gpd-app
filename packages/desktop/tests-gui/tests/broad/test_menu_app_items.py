"""Application menu ("GPD" or "GPD Dev" on debug builds): standard entries."""
from __future__ import annotations

import pytest

from gpd_tests.drivers.ax import AXClient


APP_MENU_CANDIDATES = ("GPD", "GPD Dev")


def _app_menu_name(ax: AXClient) -> str | None:
    top = set(ax.top_level_menus())
    for c in APP_MENU_CANDIDATES:
        if c in top:
            return c
    return None


EXPECTED_GROUPS = [
    # About something
    ["About GPD", "About GPD Dev"],
    # Settings or Preferences (⌘,)
    ["Settings…", "Settings...", "Preferences…", "Preferences..."],
    # Quit
    ["Quit GPD", "Quit GPD Dev"],
]


@pytest.mark.broad
def test_app_menu_present(ax: AXClient):
    name = _app_menu_name(ax)
    assert name is not None, (
        f"no application menu found; expected one of {APP_MENU_CANDIDATES}"
    )


@pytest.mark.broad
def test_app_menu_has_expected_items(ax: AXClient):
    name = _app_menu_name(ax)
    if name is None:
        pytest.skip("no application menu to inspect")
    items = set(ax.items_of(name))
    missing = [g for g in EXPECTED_GROUPS if not (items & set(g))]
    assert not missing, (
        f"{name} menu missing concept(s): {missing} (found: {sorted(items)})"
    )


@pytest.mark.broad
def test_app_menu_quit_is_enabled(ax: AXClient):
    name = _app_menu_name(ax)
    if name is None:
        pytest.skip("no application menu")
    enabled = set(ax.enabled_items_of(name))
    quit_variants = {"Quit GPD", "Quit GPD Dev"}
    assert quit_variants & enabled, (
        f"{name} menu has no enabled Quit; enabled set: {enabled}"
    )
