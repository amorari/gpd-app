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
    """Deep paint guard: the SPA has actually rendered meaningful content.

    A blank shell like ``<body><div id="root"></div></body>`` would pass a
    simple ``childElementCount > 0`` check, so this probes for real SPA
    signal via an OR of three independent markers, plus a text-content
    floor to catch empty-shell regressions.
    """
    from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip

    probe = DOMProbe(mcp)
    try:
        # OR of three SPA markers: <nav> exists, #root has children,
        # or the document has a non-trivial number of DOM nodes.
        has_spa_content = probe.eval_bool(
            "!!(document.querySelector('nav')"
            " || (document.querySelector('#root') && document.querySelector('#root').children.length > 0)"
            " || document.querySelectorAll('*').length >= 10)"
        )
        text_len = probe.eval_int(
            "(document.body && document.body.innerText ? document.body.innerText.length : 0)"
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e}); paint guard deferred")
    assert has_spa_content, (
        "no SPA markers found: need <nav>, populated #root, or >=10 DOM nodes"
    )
    assert text_len > 100, (
        f"document.body.innerText length == {text_len}; expected >100 chars of rendered text"
    )
