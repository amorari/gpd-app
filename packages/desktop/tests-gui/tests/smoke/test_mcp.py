import pytest


@pytest.mark.smoke
def test_mcp_ping(mcp):
    mcp.ping()


@pytest.mark.smoke
def test_mcp_list_windows_returns_single_main_window(mcp):
    windows = mcp.list_windows()
    assert any(w.get("label") == "main" for w in windows), (
        f"expected a window with label 'main' among {windows}"
    )
