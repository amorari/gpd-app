"""Fixtures scoped to Phase 3 flow tests."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def scratch_project_dir(tmp_path_factory) -> Path:
    """A fresh directory for session-scoped work. Not cleaned up between tests.

    Using pytest's tmp_path_factory so pytest handles the top-level lifecycle
    (auto-cleaned after N test runs). Each test gets its own subdir so the
    sidecar's `directory` filter scopes `GET /session?directory=...` cleanly.
    """
    root = tmp_path_factory.mktemp(f"gpd-flow-{uuid.uuid4().hex[:8]}")
    return root.resolve()


@pytest.fixture
def anthropic_key() -> str:
    """Return the test-mode Anthropic key; skip if absent.

    Tests marked @pytest.mark.real_backend depend on this. Non-real-backend
    flows must not request this fixture.
    """
    key = os.environ.get("GPD_TEST_ANTHROPIC_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip(
            "GPD_TEST_ANTHROPIC_KEY not set; skipping real-backend flow"
        )
    return key


@pytest.fixture
def auth_json_path() -> Path:
    """Path to opencode-cli's stored auth file.

    Tests that mutate this file MUST use @pytest.mark.fresh_app so the app is
    stopped before the write and restarted after.
    """
    return Path.home() / ".local/share/opencode/auth.json"


@pytest.fixture
def clean_onboarding_state(auth_json_path):
    """Back up and remove auth.json + onboarding sentinel; restore on teardown.

    Used by @pytest.mark.fresh_app onboarding tests — the tier-2 reset alone
    does NOT remove the sentinel (that's tier-3 territory), so this fixture
    handles it symmetrically with auth.json.
    """
    import shutil
    from pathlib import Path

    sentinel_path = Path.home() / ".config/gpd/.gpd-initialized"

    auth_backup: Path | None = None
    sentinel_backup: Path | None = None

    if auth_json_path.exists():
        auth_backup = auth_json_path.with_suffix(".json.bak-phase3")
        shutil.copy2(auth_json_path, auth_backup)
        auth_json_path.unlink()
    if sentinel_path.exists():
        sentinel_backup = sentinel_path.with_suffix(
            sentinel_path.suffix + ".bak-phase3"
        )
        shutil.copy2(sentinel_path, sentinel_backup)
        sentinel_path.unlink()

    try:
        yield auth_json_path
    finally:
        if auth_backup and auth_backup.exists():
            shutil.copy2(auth_backup, auth_json_path)
            auth_backup.unlink()
        elif auth_json_path.exists():
            auth_json_path.unlink()
        if sentinel_backup and sentinel_backup.exists():
            shutil.copy2(sentinel_backup, sentinel_path)
            sentinel_backup.unlink()
        elif sentinel_path.exists():
            sentinel_path.unlink()
