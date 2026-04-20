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


def _app_name() -> str:
    """Derive the macOS application name from GPD_APP_PATH.

    Returns "GPD Dev" for a debug bundle and "GPD" for the release bundle.
    Tauri names the binary inside Contents/MacOS/ identically to the .app stem.
    """
    app_path = os.environ.get("GPD_APP_PATH", "/Applications/GPD.app")
    return Path(app_path).stem


def stop_gpd() -> None:
    name = _app_name()
    subprocess.run(
        ["osascript", "-e", f'tell application "{name}" to quit'],
        capture_output=True,
        text=True,
        check=False,
    )
    pattern = f"{name}.app/Contents/MacOS/{name}"
    for _ in range(100):
        out = subprocess.run(
            ["pgrep", "-f", pattern],
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
    name = _app_name()
    subprocess.run(["open", "-g", "-a", app_path], check=False)

    # Verify the main process came up.
    binary_pattern = f"{name}.app/Contents/MacOS/{name}"
    launched = False
    for _ in range(50):
        out = subprocess.run(
            ["pgrep", "-f", binary_pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout.strip():
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
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True,
            text=True,
            check=False,
        )
        if out.stdout.strip():
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
