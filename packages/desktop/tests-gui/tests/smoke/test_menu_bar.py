import pytest


NON_APP_MENUS = {"File", "Edit", "View", "Help"}
APP_MENU_CANDIDATES = {"GPD", "GPD Dev", "GPD Beta"}


@pytest.mark.smoke
def test_top_level_menus_match_expected_set(ax):
    menus = set(ax.top_level_menus())
    # First menu bar item is the application menu — "GPD" for release,
    # "GPD Dev" for `cargo tauri build --debug` (CFBundleName diverges).
    missing_non_app = NON_APP_MENUS - menus
    assert not missing_non_app, (
        f"missing top-level menus: {missing_non_app} (got {menus})"
    )
    assert menus & APP_MENU_CANDIDATES, (
        f"expected one of {APP_MENU_CANDIDATES} as app menu; got {menus}"
    )
