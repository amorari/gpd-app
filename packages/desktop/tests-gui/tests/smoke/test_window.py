import pytest


@pytest.mark.smoke
def test_main_window_has_expected_title_and_size(mcp):
    """Read window geometry from MCP (list_windows) rather than AX.

    AX's `first window` query requires the app to be frontmost, which would
    steal focus from whatever the developer is doing. MCP returns the same
    data (title + inner/outer size + position) without activating the app.
    """
    windows = mcp.list_windows()
    assert windows, "no windows reported by MCP"
    main = next((w for w in windows if w.get("label") == "main"), windows[0])
    title = main.get("title", "")
    size = main.get("innerSize") or main.get("outerSize") or {}
    w = size.get("width", 0)
    h = size.get("height", 0)
    assert "GPD" in title, f"title missing 'GPD': {title!r}"
    assert w >= 800, f"window width too small: {w}"
    assert h >= 600, f"window height too small: {h}"


@pytest.mark.smoke
def test_main_window_has_painted_dom(mcp):
    """Paint guard: window exists AND body has child elements."""
    from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip

    probe = DOMProbe(mcp)
    try:
        count = probe.eval_int("document.body.childElementCount")
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e}); paint guard deferred")
    assert count > 0, f"document.body.childElementCount == {count}; nothing painted"
