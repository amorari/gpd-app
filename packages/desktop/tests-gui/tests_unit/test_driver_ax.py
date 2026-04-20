"""Unit tests for AXClient menu-introspection helpers. Mocks osascript."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from gpd_tests.drivers.ax import AXClient


@pytest.mark.unit
def test_top_level_menus_parses_osascript_output():
    sample = "GPD|File|Edit|View|Help"
    with patch("gpd_tests.drivers.ax._osascript", return_value=sample):
        menus = AXClient().top_level_menus()
    assert menus == ["GPD", "File", "Edit", "View", "Help"]


@pytest.mark.unit
def test_menu_item_exists_builds_correct_applescript():
    called: list[str] = []

    def fake(script: str) -> str:
        called.append(script)
        return "true"

    with patch("gpd_tests.drivers.ax._osascript", side_effect=fake):
        exists = AXClient().menu_item_exists("File", "New Session")
    assert exists is True
    assert any('menu bar item "File"' in s for s in called)
    assert any('menu item "New Session"' in s for s in called)


@pytest.mark.unit
def test_main_window_geometry_parses_delimited():
    # First call: count-of-windows probe. Subsequent: geometry CSV. Activate
    # is also an _osascript call — sequence: activate, count, geometry.
    with patch(
        "gpd_tests.drivers.ax._osascript",
        side_effect=["", "1", "88|||32|||1408|||1139|||GPD"],
    ):
        geom = AXClient().main_window()
    assert geom == {"x": 88, "y": 32, "w": 1408, "h": 1139, "title": "GPD"}


@pytest.mark.unit
def test_main_window_preserves_title_with_commas():
    """Title containing commas must not break the parser."""
    with patch(
        "gpd_tests.drivers.ax._osascript",
        side_effect=["", "1", "0|||0|||100|||200|||My, Project"],
    ):
        geom = AXClient().main_window()
    assert geom["title"] == "My, Project"


@pytest.mark.unit
def test_items_of_returns_split_menu_items():
    # osascript returns "Item1|Item2|Item3" with pipe delimiter.
    with patch(
        "gpd_tests.drivers.ax._osascript",
        return_value="New Conversation|Open Project...|missing value|Close Window",
    ):
        items = AXClient().items_of("File")
    # "missing value" entries (AppleScript separators in some locales)
    # are filtered out by the implementation.
    assert items == ["New Conversation", "Open Project...", "Close Window"]


@pytest.mark.unit
def test_items_of_returns_empty_when_no_menu():
    with patch("gpd_tests.drivers.ax._osascript", return_value=""):
        assert AXClient().items_of("File") == []


@pytest.mark.unit
def test_enabled_items_of_filters_disabled():
    script_responses = {
        "name of every menu item": "Save|Revert|Quit",
        "enabled of every menu item": "true|false|true",
    }

    def fake_osascript(script: str, **_kwargs):
        for needle, response in script_responses.items():
            if needle in script:
                return response
        raise RuntimeError(f"unexpected script: {script}")

    with patch("gpd_tests.drivers.ax._osascript", side_effect=fake_osascript):
        enabled = AXClient().enabled_items_of("File")
    assert enabled == ["Save", "Quit"]
