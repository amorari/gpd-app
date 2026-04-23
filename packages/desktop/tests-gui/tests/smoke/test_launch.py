import pytest


@pytest.mark.smoke
def test_gpd_process_is_running(app_state):
    assert app_state.is_running()


@pytest.mark.smoke
def test_sidecar_is_healthy(http):
    health = http.health()
    assert health.get("healthy") is True
    assert isinstance(health.get("version"), str)


@pytest.mark.smoke
def test_webview_has_painted_dom(mcp):
    """Paint guard: something actually rendered in the webview body."""
    from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip

    probe = DOMProbe(mcp)
    try:
        count = probe.eval_int("document.body.childElementCount")
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e}); paint guard deferred")
    assert count > 0, f"document.body.childElementCount == {count}; nothing painted"
