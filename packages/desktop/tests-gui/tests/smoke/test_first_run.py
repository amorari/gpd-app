import json

import pytest

from gpd_tests.drivers.mcp import MCPError, MCPTimeout
from gpd_tests.pages.onboarding import sentinel_path


@pytest.mark.smoke
def test_welcome_screen_renders_when_sentinel_absent(mcp):
    """If `.gpd-initialized` is absent, the welcome text should be in the DOM.

    This test does NOT delete the sentinel (that would force first-run for all
    subsequent tests); it only checks the current state. The dedicated
    first-run flow test in Phase 3 will actively force the state.
    """
    if sentinel_path().exists():
        pytest.skip("already initialized; no welcome gate to check")
    from gpd_tests.helpers.selectors import TEXT_WELCOME_API_KEY_PROMPT

    needle = TEXT_WELCOME_API_KEY_PROMPT
    js = f'!!document.body && document.body.innerText.includes({json.dumps(needle)})'
    try:
        result = mcp.execute_js(js)
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert result in ("true", True, "True")
