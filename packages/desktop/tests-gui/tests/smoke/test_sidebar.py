import pytest


@pytest.mark.smoke
def test_file_new_session_menu_item_exists_and_enabled(ax):
    # Upstream wave-1/wave-2 copy sweeps renamed "New Session" to
    # "New Conversation" across all locales. Accept either so the test
    # tolerates either direction of future i18n drift on this item.
    for item in ("New Conversation", "New Session"):
        if ax.menu_item_exists("File", item):
            assert ax.menu_item_enabled("File", item), (
                f'"File > {item}" exists but is disabled'
            )
            return
    pytest.fail('neither "New Conversation" nor "New Session" found under File menu')


@pytest.mark.smoke
def test_sidebar_new_session_selector_is_in_dom(mcp):
    """Best-effort DOM check — skips gracefully if execute_js is down."""
    from gpd_tests.drivers.mcp import MCPError, MCPTimeout
    from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION

    try:
        # SIDEBAR_NEW_SESSION is a CSS selector that contains `"` itself;
        # use Python repr to pick a quote form that survives round-tripping
        # into JS without clashing with the selector's inner quotes.
        js = f"!!document.querySelector({SIDEBAR_NEW_SESSION!r})"
        result = mcp.execute_js(js)
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e}); sidebar check deferred")
    assert result in ("true", True, "True"), f"sidebar selector not in DOM: {result!r}"
