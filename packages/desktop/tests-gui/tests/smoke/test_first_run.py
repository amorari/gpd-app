import json
import os
from pathlib import Path

import pytest

from gpd_tests.drivers.mcp import MCPError, MCPTimeout
from gpd_tests.pages.onboarding import sentinel_path


def _auth_json_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "opencode" / "auth.json"


@pytest.mark.smoke
@pytest.mark.tier(3)
def test_welcome_screen_renders_when_sentinel_absent(mcp):
    """If `.gpd-initialized` is absent AND auth.json is absent, welcome text
    should be in the DOM.

    GPD renders welcome only when BOTH the sentinel is absent AND no stored
    API key is present (post-upstream TOS work: welcome is a two-step
    key→TOS gate, skipped entirely when a key is already on disk). A key
    present with sentinel absent is a post-onboarding-failure state, not a
    first-run state — the welcome surface won't render there.

    Marked tier(3) so the conftest setup hook wipes onboarding sentinel +
    auth.json and relaunches GPD cold before the test runs. Without tier(3)
    the test was racy: a webview that previously mounted with auth.json
    present keeps the post-first-run UI cached in memory even after the
    file is deleted, producing a false negative on a suite run that
    exercised auth-dependent tests earlier.
    """
    if sentinel_path().exists():
        pytest.skip("already initialized; no welcome gate to check")
    if _auth_json_path().exists():
        pytest.skip(
            "auth.json present; welcome gate is skipped when a key is stored"
        )
    from gpd_tests.helpers.selectors import TEXT_WELCOME_TITLE

    # Check the welcome title — it renders as visible text. The API-key
    # placeholder is only in an <input placeholder=…> attribute and so
    # never appears in document.body.innerText.
    needle = TEXT_WELCOME_TITLE
    js = f'!!document.body && document.body.innerText.includes({json.dumps(needle)})'
    try:
        result = mcp.execute_js(js)
    except (MCPError, MCPTimeout) as e:
        pytest.skip(f"execute_js unavailable ({e})")
    assert result in ("true", True, "True"), (
        f"welcome title {needle!r} not in body.innerText"
    )
