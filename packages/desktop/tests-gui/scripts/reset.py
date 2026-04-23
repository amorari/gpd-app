"""Tiered state reset for GPD test runs."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from scripts._bundle import app_name as _app_name
from scripts._bundle import bundle_id as _bundle_id


def _ps_pids(pattern: str) -> list[str]:
    """Return PIDs whose command line matches pattern (handles spaces in paths).

    Uses -ww to disable argv truncation so long venv paths + module names
    don't silently drop off the right edge and produce false negatives
    when matching ``python -m gpd.mcp.servers.<name>``.
    """
    out = subprocess.run(
        ["ps", "-ax", "-ww", "-o", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    pids = []
    for line in out.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and re.search(pattern, parts[1]):
            pids.append(parts[0].strip())
    return pids


def _ppid_of(pid: str) -> str | None:
    """Return parent PID of `pid` as a string, or None if lookup fails."""
    try:
        out = subprocess.run(
            ["ps", "-o", "ppid=", "-p", pid],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    raw = out.stdout.strip()
    return raw if raw.isdigit() else None


def _proc_state(pid: str) -> str | None:
    """Return the single-char ps state for `pid`, or None on failure."""
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", pid],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    s = out.stdout.strip()
    return s[:1] if s else None


def _proc_alive(pid: str) -> bool:
    try:
        os.kill(int(pid), 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    # On macOS `kill(pid, 0)` succeeds for zombies; treat them as dead so
    # the SIGTERM budget isn't wasted waiting for an already-reaped child.
    return _proc_state(pid) != "Z"


def _proc_matches(pid: str, pattern: str) -> bool:
    """Return True iff `pid`'s current argv still matches `pattern`.

    PID-reuse guard for the SIGTERM→SIGKILL escalation window.
    """
    try:
        out = subprocess.run(
            ["ps", "-ww", "-o", "command=", "-p", pid],
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return False
    cmd = out.stdout.strip()
    if not cmd:
        return False
    return bool(re.search(pattern, cmd))


def _kill_snapshot(
    pids: list[str],
    *,
    term_timeout_s: float = 2.0,
    verify_pattern: str | None = None,
) -> None:
    """SIGTERM `pids`, wait `term_timeout_s`, SIGKILL survivors.

    Operates on a frozen PID list — never re-queries by pattern — so a
    freshly-spawned replacement process cannot be signaled by accident.
    When `verify_pattern` is set, each survivor is re-checked against it
    before SIGKILL to defeat PID-reuse during the escalation window.
    """
    if not pids:
        return
    subprocess.run(["kill", "-TERM", *pids], check=False)
    step = 0.1
    elapsed = 0.0
    while elapsed < term_timeout_s:
        if not any(_proc_alive(p) for p in pids):
            return
        time.sleep(step)
        elapsed += step
    survivors = [p for p in pids if _proc_alive(p)]
    if verify_pattern is not None:
        survivors = [p for p in survivors if _proc_matches(p, verify_pattern)]
    if survivors:
        subprocess.run(["kill", "-KILL", *survivors], check=False)


HOME = Path.home()

# XDG_DATA_HOME respects the XDG Base Directory Specification.
_XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
# XDG_CONFIG_HOME respects the XDG Base Directory Specification.
_XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))

_TIER_1 = [
    _XDG_DATA_HOME / "opencode/opencode.db",
    _XDG_DATA_HOME / "opencode/opencode.db-wal",
    _XDG_DATA_HOME / "opencode/opencode.db-shm",
]


def _tier_2_extras() -> list[Path]:
    """Return tier-2 extra paths — app state caches + webkit.

    Bundle ID derived from GPD_APP_PATH (debug builds use inc.psi.gpd.dev;
    hardcoded values made tier-2 a no-op on debug builds).

    auth.json lives in tier-3, not tier-2. Fresh_app tests want a clean
    sqlite / cache / webkit state; they do NOT want to nuke the user's
    credential. Only the onboarding test — which explicitly drives
    first-run UX — should wipe the credential, and that test opts into
    tier-3. Moving auth.json to tier-3 removes the need for a
    session-snapshot + restore dance in conftest.py.
    """
    bid = _bundle_id()
    return [
        HOME / "Library/Application Support" / bid,
        HOME / "Library/WebKit" / bid,
        HOME / "Library/Caches" / bid,
        HOME / "Library/Logs" / bid,
    ]


def _tier_3_extras() -> list[Path]:
    """Return tier-3 extra paths — onboarding sentinel + credential."""
    return [
        _XDG_CONFIG_HOME / "gpd/.gpd-initialized",
        _XDG_DATA_HOME / "opencode/auth.json",
    ]


def paths_for_tier(tier: int) -> list[Path]:
    if tier <= 0:
        return []
    paths = list(_TIER_1)
    if tier >= 2:
        paths.extend(_tier_2_extras())
    if tier >= 3:
        paths.extend(_tier_3_extras())
    return paths


def _launch_binary(app_path: str, name: str) -> None:
    """Launch the GPD binary directly as a detached process.

    Used as a fallback when ``open -g -a`` succeeds exit-code-wise but fails
    to produce a visible process (common in subprocess/CI environments without
    a full macOS GUI session).
    """
    # The Tauri main binary is always "GPD" regardless of the .app bundle name.
    # Debug: "GPD Dev.app/Contents/MacOS/GPD"
    # Release: "GPD.app/Contents/MacOS/GPD"
    binary = Path(app_path) / "Contents" / "MacOS" / "GPD"
    if not binary.exists():
        # Fallback: any non-sidecar file in MacOS/
        binary_dir = Path(app_path) / "Contents" / "MacOS"
        candidates = [
            f for f in binary_dir.iterdir()
            if f.is_file() and f.name != "opencode-cli"
        ]
        if not candidates:
            raise RuntimeError(
                f"No binary found in {binary_dir}; cannot launch GPD"
            )
        binary = candidates[0]
    subprocess.Popen(
        [str(binary)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# Anchored on `-m gpd.mcp.servers` so it cannot match pytest invocations
# whose argv incidentally contains `gpd.mcp.servers`. `python\S*` tolerates
# `python`, `python3`, `python3.11`, or a full venv path + interpreter.
# Keep in sync with gpd_tests/pages/app_state.py::_MCP_SERVERS_PATTERN.
_MCP_SERVERS_PATTERN = r"python\S*\s+-m\s+gpd\.mcp\.servers"


def _mcp_children_of(parent_pids: set[str]) -> list[str]:
    """Snapshot PIDs of MCP-server procs whose PPID is in `parent_pids`.

    PPID-scoped so a live same-user GPD instance (another workspace /
    /Applications/GPD.app) does not have its MCP children killed, and a
    freshly-spawned replacement sidecar's children cannot be signaled by
    a stale pattern-match loop.
    """
    if not parent_pids:
        return []
    out: list[str] = []
    for pid in _ps_pids(_MCP_SERVERS_PATTERN):
        parent = _ppid_of(pid)
        if parent is not None and parent in parent_pids:
            out.append(pid)
    return out


def _mcp_launchd_orphans() -> list[str]:
    """Return MCP-server PIDs reparented to launchd (PPID=1).

    Covers the late-spawn race: a fresh MCP child spawned between the
    pre-quit snapshot and sidecar death missed the snapshot and is now a
    launchd orphan. A parallel live GPD's MCP children still have their
    live sidecar as PPID (not 1), so this filter remains clean for the
    live case.

    NOTE: assumes a single concurrent GPD test session. Parallel pytest
    runs are already rejected at configure time (xdist → UsageError), and
    a crashed dev GPD leaving launchd orphans would in practice also want
    those cleaned up. If parallel sessions ever become supported, switch
    to a per-run PID tag.
    """
    out: list[str] = []
    for pid in _ps_pids(_MCP_SERVERS_PATTERN):
        if _ppid_of(pid) == "1":
            out.append(pid)
    return out


def stop_gpd() -> None:
    name = _app_name()
    # Snapshot the sidecar + its MCP-server children BEFORE quitting GPD.
    # Once the sidecar dies the PPID linkage is lost (children reparent to
    # launchd), so the only way to scope the kill is to freeze the PID set
    # while the sidecar is still alive.
    sidecar_pids = set(_ps_pids("opencode-cli.*serve"))
    mcp_snapshot = _mcp_children_of(sidecar_pids)

    def _reap_mcp() -> None:
        """Merge pre-quit snapshot + post-quit launchd orphans, then kill."""
        kill_list = list({*mcp_snapshot, *_mcp_launchd_orphans()})
        _kill_snapshot(kill_list, verify_pattern=_MCP_SERVERS_PATTERN)

    try:
        # Bound osascript: a native modal (NSOpenPanel, etc.) blocks the quit
        # event forever. pytest-timeout cannot interrupt a blocking
        # subprocess, so leaving this unbounded deadlocks the whole suite.
        # On timeout the SIGKILL fallback below cleans up.
        try:
            subprocess.run(
                ["osascript", "-e", f'tell application "{name}" to quit'],
                capture_output=True,
                text=True,
                check=False,
                timeout=8.0,
            )
        except subprocess.TimeoutExpired:
            pass
        # macOS pgrep -f silently fails on paths with spaces; use
        # _ps_pids instead.
        pattern = re.escape(f"{name}.app/Contents/MacOS/")
        # Poll up to 10 s for graceful exit.
        for _ in range(100):
            if not _ps_pids(pattern):
                return
            time.sleep(0.1)

        # Graceful quit timed out — SIGKILL remaining PIDs.
        pids = _ps_pids(pattern)
        if pids:
            subprocess.run(["kill", "-KILL", *pids], check=False)

        # Poll up to 3 more seconds for the SIGKILL to take effect.
        for _ in range(30):
            if not _ps_pids(pattern):
                return
            time.sleep(0.1)

        raise RuntimeError(
            f"GPD process still alive after SIGKILL (pattern: {pattern!r}). "
            "Manual intervention required."
        )
    finally:
        # Always reap MCP children — including the RuntimeError path, so a
        # stuck GPD never leaves its Python MCP children behind.
        _reap_mcp()


def start_gpd() -> None:
    from scripts._bundle import _auto_detect_app_path
    app_path = _auto_detect_app_path()
    name = _app_name()
    binary_pattern = re.escape(f"{name}.app/Contents/MacOS/")

    # Launch via binary directly — open -a can silently succeed exit-code-wise
    # while lagging behind, causing a second GPD instance to appear later and
    # confusing PPID-based sidecar detection.
    _launch_binary(app_path, name)

    # Confirm the process is present.
    confirmed = False
    for _ in range(30):
        if _ps_pids(binary_pattern):
            confirmed = True
            break
        time.sleep(0.2)
    if not confirmed:
        raise RuntimeError(
            f"GPD process did not appear after launch "
            f"(pattern: {binary_pattern!r})"
        )

    # Wait up to 15 s for the opencode-cli sidecar to appear.
    sidecar_appeared = False
    for _ in range(150):
        if _ps_pids("opencode-cli.*serve"):
            sidecar_appeared = True
            break
        time.sleep(0.1)
    if not sidecar_appeared:
        raise RuntimeError(
            "opencode-cli sidecar did not appear within 15 s after GPD launch. "
            "The app may have started in a degraded state."
        )


def run(
    *,
    tier: int,
    dry_run: bool,
    stop_app: bool = True,
    start_app: bool = True,
) -> list[Path]:
    if stop_app:
        stop_gpd()
    removed: list[Path] = []
    for p in paths_for_tier(tier):
        if not p.exists():
            continue
        if dry_run:
            print(f"[dry-run] would remove: {p}")
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        removed.append(p)
        print(f"removed: {p}")
    if start_app and not dry_run:
        start_gpd()
    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tiered GPD state reset")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2, 3], required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-restart", action="store_true", help="Do not stop/start GPD"
    )
    args = parser.parse_args(argv)
    run(
        tier=args.tier,
        dry_run=args.dry_run,
        stop_app=not args.no_restart,
        start_app=not args.no_restart,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
