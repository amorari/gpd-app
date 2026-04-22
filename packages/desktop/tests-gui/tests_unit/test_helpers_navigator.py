from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.navigator import (
    Navigator,
    _adapt_url_for_dev,
    encode_dir_token,
    route_home,
    route_project,
    route_session,
)


@pytest.mark.unit
def test_encode_dir_token_matches_base64url_no_padding():
    assert encode_dir_token("/home/testuser/proj") == (
        "L2hvbWUvdGVzdHVzZXIvcHJvag"
    )


@pytest.mark.unit
def test_route_helpers_build_expected_urls():
    assert route_home() == "tauri://localhost/"
    assert route_project("/tmp/p") == "tauri://localhost/L3RtcC9w"
    assert route_session() == "tauri://localhost/session"
    assert route_session("abc") == "tauri://localhost/session/abc"


@pytest.mark.unit
def test_navigator_go_calls_mcp_and_waits_for_url():
    mcp = MagicMock()
    mcp.current_url.side_effect = [
        "tauri://localhost/loading",
        "tauri://localhost/loading",
        "tauri://localhost/",
    ]
    nav = Navigator(mcp)
    nav.go(route_home(), timeout_s=1.0, poll_s=0.01)
    # Same-origin (tauri://localhost) → SPA navigation via execute_js, not navigate.
    mcp.execute_js.assert_called_once()
    js_arg = mcp.execute_js.call_args[0][0]
    assert "pushState" in js_arg
    mcp.navigate.assert_not_called()


@pytest.mark.unit
def test_navigator_go_raises_timeout_if_url_never_matches():
    mcp = MagicMock()
    mcp.current_url.return_value = "tauri://localhost/loading"
    nav = Navigator(mcp)
    with pytest.raises(TimeoutError):
        nav.go("tauri://localhost/", timeout_s=0.1, poll_s=0.02)


@pytest.mark.unit
def test_adapt_url_for_dev_translates_tauri_to_devurl():
    """tauri://localhost URL is adapted to http://localhost:1420 when on dev server."""
    assert _adapt_url_for_dev("http://localhost:1420/", "tauri://localhost/") == (
        "http://localhost:1420/"
    )
    assert _adapt_url_for_dev(
        "http://localhost:1420/some-path", "tauri://localhost/session/abc"
    ) == "http://localhost:1420/session/abc"


@pytest.mark.unit
def test_adapt_url_for_dev_noop_when_not_on_devurl():
    """tauri:// URL is NOT adapted when current URL is on tauri:// scheme."""
    assert _adapt_url_for_dev("tauri://localhost/", "tauri://localhost/") == (
        "tauri://localhost/"
    )
    assert _adapt_url_for_dev("", "tauri://localhost/") == "tauri://localhost/"


@pytest.mark.unit
def test_adapt_url_for_dev_noop_for_non_tauri_target():
    """Non-tauri targets are never adapted."""
    assert _adapt_url_for_dev("http://localhost:1420/", "http://other/") == "http://other/"


@pytest.mark.unit
def test_navigator_go_adapts_to_dev_url_when_on_devserver():
    """Navigator.go adapts tauri:// to http://localhost:1420 when on dev server."""
    mcp = MagicMock()
    mcp.current_url.side_effect = [
        "http://localhost:1420/",   # first call: detect current URL for adaptation
        "http://localhost:1420/",   # loop: matches adapted nav_url
    ]
    nav = Navigator(mcp)
    nav.go(route_home(), timeout_s=1.0, poll_s=0.01)
    # URL was adapted to http://localhost:1420/ and same-origin → SPA navigation.
    mcp.execute_js.assert_called_once()
    js_arg = mcp.execute_js.call_args[0][0]
    assert "pushState" in js_arg
    mcp.navigate.assert_not_called()


@pytest.mark.unit
def test_navigator_go_falls_back_to_navigate_when_execute_js_unavailable():
    """Navigator.go falls back to mcp.navigate when execute_js raises AttributeError."""
    mcp = MagicMock()
    mcp.execute_js.side_effect = AttributeError("no execute_js")
    mcp.current_url.side_effect = [
        "tauri://localhost/loading",
        "tauri://localhost/",
    ]
    nav = Navigator(mcp)
    nav.go(route_home(), timeout_s=1.0, poll_s=0.01)
    mcp.navigate.assert_called_once_with("tauri://localhost/")
