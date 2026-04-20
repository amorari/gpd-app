import pytest


@pytest.mark.smoke
def test_file_new_session_menu_item_exists_and_enabled(ax):
    assert ax.menu_item_exists("File", "New Session")
    assert ax.menu_item_enabled("File", "New Session")


@pytest.mark.smoke
def test_sidebar_new_session_selector_is_in_dom(mcp):
    """Best-effort DOM check — skips gracefully if execute_js is down."""
    from gpd_tests.drivers.mcp import MCPError, MCPTimeout
    from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION

    try:
        result = mcp.execute_js(
            f'!!document.querySelector("{SIDEBAR_NEW_SESSION}")'
        )
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e}); sidebar check deferred")
    assert result in ("true", True, "True"), f"sidebar selector not in DOM: {result!r}"
