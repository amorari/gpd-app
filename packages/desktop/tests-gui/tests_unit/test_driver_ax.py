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
