import pytest


@pytest.fixture
def prepared_project_path(tmp_path_factory) -> str:
    p = tmp_path_factory.mktemp("gpd_smoke_sidebar")
    p = p.resolve()
    (p / "README.md").write_text("# test project\n")
    return str(p)


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
def test_sidebar_new_session_selector_is_in_dom(mcp, prepared_project_path):
    """Best-effort DOM check — skips gracefully if execute_js is down.

    Navigates to a project session route first so that the sidebar renders
    the per-project NewSessionItem (which carries data-action="new-session").
    The titlebar also emits this attribute when a project is active, so
    either element satisfies the selector.
    """
    from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
    from gpd_tests.helpers.navigator import (
        Navigator,
        encode_dir_token,
        route_session_in_project,
    )
    from gpd_tests.helpers.selectors import SIDEBAR_NEW_SESSION

    Navigator(mcp).go(
        route_session_in_project(encode_dir_token(prepared_project_path)),
        timeout_s=5.0,
    )
    probe = DOMProbe(mcp)
    js = f"!!document.querySelector({SIDEBAR_NEW_SESSION!r})"
    try:
        result = probe.eval_bool(js)
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e}); sidebar check deferred")
    assert result, f"sidebar selector not in DOM: {result!r}"
