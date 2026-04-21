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
@pytest.mark.xfail(
    strict=False,
    reason=(
        "No always-present DOM anchor for the sidebar 'new session' trigger in a "
        "fresh/empty workspace: the existing [data-action=\"workspace-new-session\"] "
        "button inside sidebar-workspace is a hover-revealed child that only "
        "renders once the workspace list contains an entry. Turning this into a "
        "stable smoke assertion needs a product-side change — tagging the always-"
        "present titlebar new-session button with data-action=\"new-session\". "
        "Patch prepared at /tmp/gpd-app-data-action-new-session.patch (F4); will "
        "be submitted as a separate PR to gpd-app."
    ),
)
def test_sidebar_new_session_selector_is_in_dom(mcp):
    """Best-effort DOM check — skips gracefully if execute_js is down."""
    from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
    from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION

    probe = DOMProbe(mcp)
    js = f"!!document.querySelector({SIDEBAR_NEW_SESSION!r})"
    try:
        result = probe.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e}); sidebar check deferred")
    assert result, f"sidebar selector not in DOM: {result!r}"
