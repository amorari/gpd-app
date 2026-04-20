from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.navigator import (
    Navigator,
    encode_dir_token,
    route_home,
    route_project,
    route_session,
)


@pytest.mark.unit
def test_encode_dir_token_matches_base64url_no_padding():
    assert encode_dir_token("/Users/amorari/workspace/gpd-tests") == (
        "L1VzZXJzL2Ftb3Jhcmkvd29ya3NwYWNlL2dwZC10ZXN0cw"
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
    mcp.navigate.assert_called_once_with("tauri://localhost/")


@pytest.mark.unit
def test_navigator_go_raises_timeout_if_url_never_matches():
    mcp = MagicMock()
    mcp.current_url.return_value = "tauri://localhost/loading"
    nav = Navigator(mcp)
    with pytest.raises(TimeoutError):
        nav.go("tauri://localhost/", timeout_s=0.1, poll_s=0.02)
