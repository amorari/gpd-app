"""Triage Gate 4: given a failing test + time window, surface product-code
commits that landed in the window. Helps tell "harness bug" from "product regression".

Usage:
  python scripts/triage_gate4.py <since_iso_date>
  python scripts/triage_gate4.py 2026-04-20
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def find_related_commits(
    since: str,
    paths: list[str] | None = None,
    repo_root: str | None = None,
) -> list[dict[str, Any]]:
    cmd = ["git", "log", f"--since={since}", "--pretty=format:%H\t%s"]
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    r = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    results = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        results.append({"sha": sha, "subject": subject})
    return results


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: triage_gate4.py <since_iso_date>", file=sys.stderr)
        return 2
    commits = find_related_commits(
        since=sys.argv[1],
        paths=[
            "packages/desktop/src-tauri/",
            "packages/desktop/src/",
        ],
    )
    if not commits:
        print(f"No product-code commits since {sys.argv[1]}.")
        return 0
    print(f"Product-code commits since {sys.argv[1]} ({len(commits)}):")
    for c in commits:
        print(f"  {c['sha'][:8]}  {c['subject']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
