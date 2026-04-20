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
    return root


@pytest.fixture
def anthropic_key() -> str:
    """Return the test-mode Anthropic key; skip if absent.

    Tests marked @pytest.mark.real_backend depend on this. Non-real-backend
    flows must not request this fixture.
    """
    key = os.environ.get("GPD_TEST_ANTHROPIC_KEY")
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

    Only files that this fixture creates/removes are cleaned up in teardown.
    """
    from gpd_tests.pages.onboarding import sentinel_path

    _sentinel_path = sentinel_path()

    auth_backup: Path | None = None
    sentinel_backup: Path | None = None
    created_auth = False
    created_sentinel = False

    if auth_json_path.exists():
        auth_backup = auth_json_path.with_suffix(".json.bak-phase3")
        if auth_backup.exists():
            raise RuntimeError(
                f"Backup file already exists: {auth_backup}. "
                "A previous test session may not have cleaned up properly."
            )
        shutil.copy2(auth_json_path, auth_backup)
        auth_json_path.unlink()
        created_auth = True
    if _sentinel_path.exists():
        sentinel_backup = _sentinel_path.with_suffix(
            _sentinel_path.suffix + ".bak-phase3"
        )
        if sentinel_backup.exists():
            raise RuntimeError(
                f"Backup file already exists: {sentinel_backup}. "
                "A previous test session may not have cleaned up properly."
            )
        shutil.copy2(_sentinel_path, sentinel_backup)
        _sentinel_path.unlink()
        created_sentinel = True

    try:
        yield auth_json_path
    finally:
        if created_auth:
            if auth_backup and auth_backup.exists():
                shutil.copy2(auth_backup, auth_json_path)
                auth_backup.unlink()
            elif auth_json_path.exists():
                auth_json_path.unlink()
        if created_sentinel:
            if sentinel_backup and sentinel_backup.exists():
                shutil.copy2(sentinel_backup, _sentinel_path)
                sentinel_backup.unlink()
            elif _sentinel_path.exists():
                _sentinel_path.unlink()


# Backwards-compatible alias. Prefer `clean_onboarding_state` in new tests.
clean_auth_json = clean_onboarding_state
