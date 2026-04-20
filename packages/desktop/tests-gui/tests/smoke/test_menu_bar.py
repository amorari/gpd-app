import pytest


EXPECTED_MENUS = {"GPD", "File", "Edit", "View", "Help"}


@pytest.mark.smoke
def test_top_level_menus_match_expected_set(ax):
    menus = set(ax.top_level_menus())
    missing = EXPECTED_MENUS - menus
    assert not missing, f"missing top-level menus: {missing} (got {menus})"
