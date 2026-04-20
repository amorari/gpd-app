"""Tiered state reset for GPD test runs."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ["HOME"])

_TIER_1 = [
    HOME / ".local/share/opencode/opencode.db",
    HOME / ".local/share/opencode/opencode.db-wal",
    HOME / ".local/share/opencode/opencode.db-shm",
]

_TIER_2_EXTRAS = [
    HOME / "Library/Application Support/inc.psi.gpd",
    HOME / "Library/WebKit/inc.psi.gpd",
    HOME / "Library/Caches/inc.psi.gpd",
    HOME / "Library/Logs/inc.psi.gpd",
    HOME / ".local/share/opencode/auth.json",
]

_TIER_3_EXTRAS = [
    HOME / ".config/gpd/.gpd-initialized",
]


def paths_for_tier(tier: int) -> list[Path]:
    if tier <= 0:
        return []
    paths = list(_TIER_1)
    if tier >= 2:
        paths.extend(_TIER_2_EXTRAS)
    if tier >= 3:
        paths.extend(_TIER_3_EXTRAS)
    return paths


def stop_gpd() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "GPD" to quit'],
        capture_output=True,
        text=True,
        check=False,
    )
    for _ in range(100):
        out = subprocess.run(
            ["pgrep", "-f", "GPD.app/Contents/MacOS/GPD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if not out.stdout.strip():
            return
        time.sleep(0.1)


def start_gpd() -> None:
    # -g = background, so resets don't steal focus from the developer.
    # Honor GPD_APP_PATH for in-tree dev builds.
    app_path = os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")
    subprocess.run(["open", "-g", "-a", app_path], check=False)


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
