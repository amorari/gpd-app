"""After SIGKILLing the opencode-cli sidecar, GPD must respawn it and service resumes."""
from __future__ import annotations
import os
import signal
import subprocess
import time

import pytest


@pytest.mark.lifecycle
def test_sidecar_respawns_after_sigkill(http, app_state):
    pre = http.health()
    assert pre.get("healthy") is True, f"sidecar unhealthy before kill: {pre!r}"

    out = subprocess.run(
        ["pgrep", "-f", "opencode-cli.*serve"],
        capture_output=True, text=True, check=False,
    )
    pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    assert pids, "no opencode-cli running — preconditions broken"
    old_pid = pids[0]

    os.kill(old_pid, signal.SIGKILL)

    deadline = time.monotonic() + 30.0
    new_pid: int | None = None
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True, text=True, check=False,
        )
        pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        candidates = [p for p in pids if p != old_pid]
        if candidates:
            new_pid = candidates[0]
            break
        time.sleep(0.5)
    assert new_pid is not None, "sidecar did not respawn within 30s"

    # The http fixture is session-scoped and cached — trigger rediscovery by
    # calling health() and catching/retrying once if the cached port/cred is stale.
    # If the fixture can't rediscover at all, this assertion fails loudly and
    # that's a real finding to escalate.
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
