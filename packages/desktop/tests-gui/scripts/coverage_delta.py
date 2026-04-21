"""Diff two coverage.xml files and report newly-covered / newly-uncovered lines.

Input: coverage.py XML reports (schema with <class filename=...><lines><line number=... hits=.../></lines></class>).

Usage:
  coverage_delta.py <before.xml> <after.xml> [--markdown]
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _parse(path: Path) -> dict[str, dict[int, bool]]:
    """Returns {filename: {line_number: hit_bool}}."""
    tree = ET.parse(path)
    out: dict[str, dict[int, bool]] = {}
    for cls in tree.iter("class"):
        fname = cls.get("filename") or cls.get("name") or "?"
        hits: dict[int, bool] = {}
        for ln in cls.iter("line"):
            try:
                n = int(ln.get("number") or "0")
                h = int(ln.get("hits") or "0") > 0
            except (TypeError, ValueError):
                continue
            hits[n] = h
        out[fname] = hits
    return out


def diff_coverage(before: Path, after: Path) -> dict[str, dict[str, list[int]]]:
    a = _parse(before)
    b = _parse(after)
    all_files = set(a) | set(b)
    result: dict[str, dict[str, list[int]]] = {}
    for f in sorted(all_files):
        a_hits = a.get(f, {})
        b_hits = b.get(f, {})
        newly_covered: list[int] = []
        newly_uncovered: list[int] = []
        for n in sorted(set(a_hits) | set(b_hits)):
            a_hit = a_hits.get(n, False)
            b_hit = b_hits.get(n, False)
            if b_hit and not a_hit:
                newly_covered.append(n)
            elif a_hit and not b_hit:
                newly_uncovered.append(n)
        result[f] = {"newly_covered": newly_covered, "newly_uncovered": newly_uncovered}
    return result


def to_markdown(diff: dict[str, dict[str, list[int]]]) -> str:
    lines = ["# Coverage delta", ""]
    changed = [
        (f, d) for f, d in diff.items()
        if d["newly_covered"] or d["newly_uncovered"]
    ]
    if not changed:
        lines.append("_No coverage changes._")
        return "\n".join(lines) + "\n"
    for f, d in changed:
        lines.append(f"## {f}")
        if d["newly_covered"]:
            lines.append(f"- **Newly covered:** {len(d['newly_covered'])} lines — {d['newly_covered'][:20]}{'…' if len(d['newly_covered']) > 20 else ''}")
        if d["newly_uncovered"]:
            lines.append(f"- **Newly uncovered:** {len(d['newly_uncovered'])} lines — {d['newly_uncovered'][:20]}{'…' if len(d['newly_uncovered']) > 20 else ''}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: coverage_delta.py <before.xml> <after.xml> [--markdown]", file=sys.stderr)
        return 2
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    mode = sys.argv[3] if len(sys.argv) >= 4 else ""
    diff = diff_coverage(before, after)
    if mode == "--markdown":
        sys.stdout.write(to_markdown(diff))
    else:
        total_newly_covered = sum(len(d["newly_covered"]) for d in diff.values())
        total_newly_uncovered = sum(len(d["newly_uncovered"]) for d in diff.values())
        print(f"newly_covered_lines: {total_newly_covered}")
        print(f"newly_uncovered_lines: {total_newly_uncovered}")
        for f, d in diff.items():
            if d["newly_covered"] or d["newly_uncovered"]:
                print(f"  {f}: +{len(d['newly_covered'])} / -{len(d['newly_uncovered'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
