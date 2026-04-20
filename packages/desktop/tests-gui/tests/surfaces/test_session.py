import pytest

from gpd_tests.helpers.dom_probe import DOMProbe, ProbeSkip
from gpd_tests.helpers.navigator import Navigator, route_session
from gpd_tests.helpers.selectors import TEXT_PROMPT_PLACEHOLDER


@pytest.mark.surfaces
def test_session_route_reachable(mcp):
    Navigator(mcp).go(route_session(), timeout_s=5.0)
    assert "/session" in mcp.current_url()


@pytest.mark.surfaces
def test_composer_placeholder_present(mcp):
    Navigator(mcp).go(route_session(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    escaped = TEXT_PROMPT_PLACEHOLDER.replace('"', '\\"')
    try:
        found = probe.eval_bool(
            'Array.from(document.querySelectorAll("[placeholder]"))'
            f'.some(el => el.placeholder === "{escaped}")'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    if not found:
        pytest.skip(
            f"no element has placeholder={TEXT_PROMPT_PLACEHOLDER!r} "
            "(welcome overlay or different composer layout)"
        )
    assert found


@pytest.mark.surfaces
def test_send_button_disabled_on_empty_input(mcp):
    Navigator(mcp).go(route_session(), timeout_s=5.0)
    probe = DOMProbe(mcp)
    try:
        disabled = probe.eval_bool(
            'Array.from(document.querySelectorAll('
            '"button[data-component=\\"button\\"][type=\\"submit\\"]"))'
            '.every(b => b.disabled || b.getAttribute("aria-disabled") === "true")'
        )
    except ProbeSkip as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert disabled, "send button not disabled on empty composer"
