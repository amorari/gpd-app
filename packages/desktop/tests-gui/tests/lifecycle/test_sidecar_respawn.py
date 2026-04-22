"""After SIGKILLing the opencode-cli sidecar, GPD must respawn it and service resumes."""
from __future__ import annotations
import os
import re
import signal
import subprocess
import time

import pytest


def _ps_pgrep(pattern: str) -> list[int]:
    """Find PIDs matching *pattern* using ps; avoids pgrep -f space-path bug on macOS."""
    out = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
        capture_output=True, text=True, check=False,
    )
    pids = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        pid_str, command = parts
        if pid_str.isdigit() and re.search(pattern, command):
            pids.append(int(pid_str))
    return pids


def _get_ppid(pid: int) -> int | None:
    """Return the parent PID of *pid*, or None if the process no longer exists."""
    out = subprocess.run(
        ["ps", "-o", "ppid=", "-p", str(pid)],
        capture_output=True, text=True, check=False,
    )
    raw = out.stdout.strip()
    return int(raw) if raw.isdigit() else None


def _live_gpd_pids() -> set[int]:
    """Return the set of live GPD main-binary PIDs."""
    from gpd_tests.pages.app_state import _PGREP_PATTERN, _pgrep
    return set(_pgrep(_PGREP_PATTERN))


def _is_fresh_sidecar(pid: int, gpd_pids: set[int]) -> bool:
    """Return True if *pid*'s PPID is one of the live GPD processes.

    Orphaned sidecars (left over from a previous GPD instance that exited
    without cleaning up) have PPID=1 (reparented to init).  The watchdog-
    spawned sidecar's PPID is the current GPD process.  Filtering by PPID
    prevents the test from picking up a stale orphan as the "new" sidecar.
    """
    ppid = _get_ppid(pid)
    return ppid is not None and ppid in gpd_pids


@pytest.mark.lifecycle
def test_sidecar_respawns_after_sigkill(http, app_state):
    pre = http.health()
    assert pre.get("healthy") is True, f"sidecar unhealthy before kill: {pre!r}"

    pids = _ps_pgrep(r"opencode-cli.*serve")
    assert pids, "no opencode-cli running — preconditions broken"
    old_pid = pids[0]

    gpd_pids = _live_gpd_pids()
    os.kill(old_pid, signal.SIGKILL)

    new_pid: int | None = None
    try:
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            # Only consider sidecars that are children of a live GPD process.
            # Orphaned sidecars (PPID=1, left over from a previous quit that
            # did not clean up) would otherwise be mistaken for the newly
            # watchdog-spawned sidecar and cause discover_sidecar_port to fail.
            candidates = [
                p for p in _ps_pgrep(r"opencode-cli.*serve")
                if p != old_pid and _is_fresh_sidecar(p, gpd_pids)
            ]
            if candidates:
                new_pid = candidates[0]
                break
            time.sleep(0.5)
        assert new_pid is not None, "sidecar did not respawn within 30s"

        # The respawned sidecar has a new port + new basic-auth creds — the
        # HTTPClient instance still points at the dead one. Rediscover against
        # the new pid (F9). Then poll /global/health briefly to tolerate the
        # gap between TCP-listen and the HTTP handler being wired up.
        http.rediscover(new_pid)
        deadline2 = time.monotonic() + 15.0
        post = None
        while time.monotonic() < deadline2:
            try:
                post = http.health()
                if post.get("healthy") is True:
                    break
            except Exception:
                time.sleep(0.5)
                continue
            time.sleep(0.5)
        assert post and post.get("healthy") is True, f"sidecar unhealthy after respawn: {post!r}"
    finally:
        # Guarantee the app (and its sidecar) are healthy before subsequent
        # tests run.  If the sidecar was respawned successfully the kill+relaunch
        # path below is a no-op (app is still running).  If the assertion above
        # fired, the sidecar may be dead; we restart the whole app so that the
        # session-scoped `app_state` fixture leaves downstream tests in a clean
        # state.
        sidecar_alive = bool(_ps_pgrep(r"opencode-cli.*serve"))
        if not sidecar_alive:
            try:
                app_state.quit()
            except Exception:
                app_state.kill_stale()
            app_state.launch()
            app_state.wait_launched()
