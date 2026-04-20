import pytest


@pytest.mark.smoke
def test_mcp_ping(mcp):
    mcp.ping()


@pytest.mark.smoke
def test_mcp_list_windows_returns_single_main_window(mcp):
    windows = mcp.list_windows()
    labels = [w.get("label") for w in windows]
    assert "main" in labels, f"expected label 'main' among {labels}"
    assert len(windows) == 1, f"expected exactly one window, got {len(windows)}"
