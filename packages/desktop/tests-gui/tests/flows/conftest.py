"""Fixtures scoped to Phase 3 flow tests."""
from __future__ import annotations

import os
import shutil
import tempfile
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
def clean_auth_json(auth_json_path):
    """Back up auth.json, yield, restore. Use with fresh_app tests only."""
    backup_path: Path | None = None
    if auth_json_path.exists():
        backup_path = auth_json_path.with_suffix(".json.bak-phase3")
        shutil.copy2(auth_json_path, backup_path)
        auth_json_path.unlink()
    yield auth_json_path
    if backup_path and backup_path.exists():
        shutil.copy2(backup_path, auth_json_path)
        backup_path.unlink()
    elif auth_json_path.exists():
        auth_json_path.unlink()
