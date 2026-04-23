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


def _ps_pids(pattern: str) -> list[str]:
    """Return PIDs whose command line matches pattern (handles spaces in paths)."""
    out = subprocess.run(
        ["ps", "-ax", "-o", "pid=,command="],
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
from scripts._bundle import bundle_id as _bundle_id

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
    """Return tier-2 extra paths, using the bundle ID derived from GPD_APP_PATH.

    Previously hardcoded to inc.psi.gpd, which made the tier-2 reset a no-op
    on debug builds (inc.psi.gpd.dev). Now derived dynamically.
    """
    bid = _bundle_id()
    return [
        HOME / "Library/Application Support" / bid,
        HOME / "Library/WebKit" / bid,
        HOME / "Library/Caches" / bid,
        HOME / "Library/Logs" / bid,
        _XDG_DATA_HOME / "opencode/auth.json",
    ]


def _tier_3_extras() -> list[Path]:
    """Return tier-3 extra paths, respecting XDG_CONFIG_HOME."""
    return [
        _XDG_CONFIG_HOME / "gpd/.gpd-initialized",
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
    import os as _os
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


def stop_gpd() -> None:
    name = _app_name()
    # Bound osascript: a native modal (NSOpenPanel, etc.) blocks the quit
    # event forever. pytest-timeout cannot interrupt a blocking subprocess,
    # so leaving this unbounded deadlocks the whole suite. On timeout the
    # SIGKILL fallback below cleans up.
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
    # macOS pgrep -f silently fails on paths with spaces; use _ps_pids instead.
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
