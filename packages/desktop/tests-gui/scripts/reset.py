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


def stop_gpd() -> None:
    name = _app_name()
    subprocess.run(
        ["osascript", "-e", f'tell application "{name}" to quit'],
        capture_output=True,
        text=True,
        check=False,
    )
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
    # -g = background, so resets don't steal focus from the developer.
    # Honor GPD_APP_PATH for in-tree dev builds.
    app_path = os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")
    name = _app_name()
    result = subprocess.run(
        ["open", "-g", "-a", app_path],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"'open -g -a {app_path}' failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )

    # macOS pgrep -f silently fails on paths with spaces; use _ps_pids.
    # Match on MacOS/ directory prefix — debug binary is "GPD", not "GPD Dev".
    binary_pattern = re.escape(f"{name}.app/Contents/MacOS/")
    launched = False
    for _ in range(50):
        if _ps_pids(binary_pattern):
            launched = True
            break
        time.sleep(0.2)
    if not launched:
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
