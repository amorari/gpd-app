#!/usr/bin/env python3
"""Triage a failing test per the four-gate protocol."""
from __future__ import annotations
import argparse
import os
import subprocess
import sys


def run_pytest_once(nodeid: str, app_path: str | None = None) -> bool:
    env = os.environ.copy()
    if app_path:
        env["GPD_APP_PATH"] = app_path
    r = subprocess.run(
        ["uv", "run", "pytest", nodeid, "-q", "--no-header", "-x"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    return r.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("nodeid")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--reference", default="/Applications/GPD.app",
                       help="Path to reference release build")
    args = parser.parse_args()

    # Gate 1: run N times against current build
    current_pass = sum(1 for _ in range(args.iterations)
                      if run_pytest_once(args.nodeid))
    print(f"Current build: {current_pass}/{args.iterations} passed")

    pct = current_pass / args.iterations
    if 0.2 < pct < 0.8:
        print("LABEL: FLAKY")
        sys.exit(0)
    if pct == 1.0:
        print("LABEL: PASSING")
        sys.exit(0)

    # Gate 3: if reference exists, run against it
    ref_pass = None
    if os.path.isdir(args.reference):
        ref_pass = sum(1 for _ in range(args.iterations)
                      if run_pytest_once(args.nodeid, app_path=args.reference))
        print(f"Reference build: {ref_pass}/{args.iterations} passed")

    if ref_pass is not None:
        if ref_pass > current_pass:
            print("LABEL: REGRESSION_ON_BRANCH")
            print("  Action: git bisect to find the commit that introduced the regression")
        elif ref_pass <= current_pass:
            print("LABEL: HARNESS_BUG or PRODUCT_DRIFT (needs Gate 2: manual)")
            print("  Action: perform the test's action by hand; check en.ts / product source for drift")
    else:
        print("LABEL: NEEDS_MANUAL")
        print(f"  Action: no reference build at {args.reference}; perform Gate 2 manually")


if __name__ == "__main__":
    main()
