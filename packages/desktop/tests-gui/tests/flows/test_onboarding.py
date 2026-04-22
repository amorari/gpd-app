"""Phase 3 flow: first-run welcome → paste API key → reach home.

Gating (post G6.1):
  - ``@pytest.mark.real_backend`` — skipped unless ``GPD_TEST_ANTHROPIC_KEY``
    is set (via the ``gpd_key`` fixture); the flow writes the key to
    auth.json so a real (non-stub) key is required.
  - ``@pytest.mark.fresh_app`` — alias for ``@pytest.mark.tier(2)``; before
    this test runs, ``conftest.pytest_runtest_setup`` calls
    ``scripts.reset.run(tier=2, ...)`` which STOPS GPD, deletes the tier-2
    paths (``~/Library/{Application Support,WebKit,Caches,Logs}/<bundle>``
    and ``$XDG_DATA_HOME/opencode/auth.json``, plus tier-1 sqlite files),
    then restarts GPD. This IS destructive but it is idempotent and scoped
    to harness-owned state — no path outside the GPD app-support tree,
    opencode data dir, or XDG config is touched. The prior
    ``PYTEST_RUN_DESTRUCTIVE_FLOWS=1`` gate (removed in G6.1) made this
    test effectively dead in CI and in typical dev flows; the
    ``fresh_app`` marker alone is sufficient opt-in.
  - ``clean_onboarding_state`` fixture — additionally backs up and removes
    the onboarding sentinel (``~/.config/gpd/.gpd-initialized``) and
    auth.json around the test, restoring originals on teardown. This
    covers tier-3 sentinel removal that the ``fresh_app`` tier-2 reset
    leaves alone.
"""
from __future__ import annotations

import pytest

from gpd_tests.pages.onboarding import Onboarding, sentinel_path


@pytest.mark.flows
@pytest.mark.real_backend
@pytest.mark.fresh_app
def test_first_run_paste_key_reach_home(
    mcp, gpd_key, clean_onboarding_state, app_state
):
    # Precondition: fresh_app + clean_onboarding_state ensure GPD restarted
    # with sentinel absent and auth.json removed.
    sentinel = sentinel_path()
    assert not sentinel.exists(), (
        "tier-2 reset did not remove the sentinel — "
        "scripts/reset.py may have drifted from the spec"
    )

    onboarding = Onboarding(mcp)
    assert onboarding.welcome_visible(), (
        "welcome screen not visible after fresh_app reset; "
        "tier-2 may not be forcing first-run"
    )

    onboarding.enter_api_key(gpd_key)
    onboarding.wait_for_home(timeout_s=30.0)

    # Post-condition: sentinel present, auth.json populated.
    assert sentinel_path().exists(), "sentinel not created after onboarding"
    assert clean_onboarding_state.exists(), "auth.json not created after onboarding"
