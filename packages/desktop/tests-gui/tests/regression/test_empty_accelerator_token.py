"""Phase 4 regression: launching GPD does not log the 'Found empty token
while parsing accelerator' parser error.

This error showed up in the binary's strings (confirmed via `strings` on the
compiled GPD app). If a future accelerator string loses its Cmd/Ctrl/etc.
modifier, Tauri's accelerator parser will emit this message on startup. The
regression test asserts it's absent in the most recent log.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


NEEDLE = "Found empty token while parsing accelerator"


def _candidate_log_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Library/Logs/inc.psi.gpd.dev",
        home / "Library/Logs/inc.psi.gpd",
    ]


def _most_recent_log() -> Path | None:
    candidates: list[Path] = []
    for d in _candidate_log_dirs():
        if d.is_dir():
            candidates.extend(d.glob("opencode-desktop_*.log"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


@pytest.mark.regression
def test_no_empty_accelerator_token_on_fresh_launch(app_state):
    # app_state fixture ensures GPD is launched + MCP socket reached before
    # this test runs. That guarantees the startup log has been written.
    log = _most_recent_log()
    if log is None:
        pytest.skip(
            f"no GPD log file found under {[str(d) for d in _candidate_log_dirs()]} "
            "— GPD may write logs elsewhere on this platform"
        )
    text = log.read_text(encoding="utf-8", errors="replace")
    assert NEEDLE not in text, (
        f"regression: GPD log {log} contains '{NEEDLE}'. "
        "Check the recent accelerator/menu registrations for an empty "
        "modifier chain (e.g. `accelerator: ''` or `key: ''` without Cmd/Ctrl)."
    )
