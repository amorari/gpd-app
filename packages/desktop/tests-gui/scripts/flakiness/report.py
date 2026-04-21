"""Aggregate JUnit XML files into a flakiness report.

Categories:
  stable: passed in all runs
  flaky:  passed in at least one AND failed/errored in at least one
  broken: failed/errored in every run it appeared in

Output: dict with four keys (stable, flaky, broken, total_runs).
When run as a script, formats as markdown to stdout.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


def aggregate(junit_dir: Path) -> dict[str, Any]:
    passed: dict[str, int] = defaultdict(int)
    failed: dict[str, int] = defaultdict(int)
    total_runs = 0

    for xml_file in sorted(Path(junit_dir).glob("*.xml")):
        total_runs += 1
        tree = ET.parse(xml_file)
        for tc in tree.iter("testcase"):
            tid = f"{tc.get('classname')}::{tc.get('name')}"
            is_failure = (
                tc.find("failure") is not None
                or tc.find("error") is not None
            )
            if is_failure:
                failed[tid] += 1
            else:
                passed[tid] += 1

    all_ids = set(passed) | set(failed)
    stable = sorted(tid for tid in all_ids if failed[tid] == 0)
    broken = sorted(tid for tid in all_ids if passed[tid] == 0)
    flaky_ids = sorted(
        tid for tid in all_ids
        if passed[tid] > 0 and failed[tid] > 0
    )
    flaky = [
        {
            "id": tid,
            "pass_count": passed[tid],
            "fail_count": failed[tid],
            "total_runs": total_runs,
        }
        for tid in flaky_ids
    ]
    return {
        "stable": stable,
        "flaky": flaky,
        "broken": broken,
        "total_runs": total_runs,
    }


def to_markdown(agg: dict[str, Any]) -> str:
    lines = [f"# Flakiness report ({agg['total_runs']} runs)"]
    if agg["flaky"]:
        lines.extend(["", "## FLAKY"])
        for f in agg["flaky"]:
            lines.append(
                f"- `{f['id']}` \u2014 {f['pass_count']}/{f['total_runs']} passed"
            )
    if agg["broken"]:
        lines.extend(["", "## BROKEN"])
        for tid in agg["broken"]:
            lines.append(f"- `{tid}` \u2014 failed all runs")
    if not agg["flaky"] and not agg["broken"]:
        lines.extend(["", "_All tests stable._"])
    lines.extend(["", f"Stable: {len(agg['stable'])}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: report.py <junit_dir>", file=sys.stderr)
        return 2
    agg = aggregate(Path(sys.argv[1]))
    sys.stdout.write(to_markdown(agg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
