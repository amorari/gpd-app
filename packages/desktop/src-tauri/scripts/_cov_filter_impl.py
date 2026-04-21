#!/usr/bin/env python3
"""Implementation helper for rust_coverage_filter.sh.

Parses a cargo-llvm-cov JSON export and filters the function list down to those
whose mangled name matches a given Tauri-command name.

Split out into its own module so the matching logic can be unit-tested without
invoking ``cargo llvm-cov`` (which is expensive and requires a Rust toolchain
plus llvm tools).

Usage:
    _cov_filter_impl.py <command_name> <llvm-cov-json-path> <0|1 for json mode>

Exit codes:
    0 : matches found and printed
    2 : bad CLI args
    3 : no matches for command name
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any


def name_matches(fn_name: str, cmd: str) -> bool:
    """Heuristic: does ``fn_name`` (a mangled Rust function name) refer to ``cmd``.

    cargo-llvm-cov emits function names in one of two formats:

    (a) Legacy/demangled style, e.g.
        ``opencode_lib::project_fs::check_project_accessible::h<hash>``
        ``opencode_lib::project_fs::check_project_accessible``
        ``opencode_lib::__cmd__check_project_accessible``

    (b) Rust v0 mangled style (what we see on this Homebrew-Rust 1.95 box),
        e.g. ``_RNvNtCs8EFNFryo1kC_12opencode_lib10project_fs24check_project_accessible``.
        In v0 mangling, each path component is encoded as ``<len><name>`` with no
        separators, so the literal substring we need to find is ``<len(cmd)><cmd>``
        at a position that isn't itself continuing a longer name.

    We match when any of these hold:
    - the path equals ``<cmd>``
    - the segment ``::<cmd>::`` appears (demangled path)
    - the path ends with ``::<cmd>`` (demangled path)
    - the path contains ``__cmd__<cmd>`` (Tauri dispatcher wrapper)
    - (v0) ``<N><cmd>`` appears where ``N == len(cmd)``, not preceded by another
      digit (which would make it part of a longer length prefix) and not followed
      by a word char (so ``check_project`` doesn't false-match
      ``check_project_accessible``).
    """
    if not fn_name or not cmd:
        return False
    if fn_name == cmd:
        return True
    if f"::{cmd}::" in fn_name:
        return True
    if fn_name.endswith(f"::{cmd}"):
        return True
    if f"__cmd__{cmd}" in fn_name:
        return True
    # Rust v0 mangled form: look for the length-prefixed component
    # encoding. ``(?<!\d)`` rejects longer length prefixes that would make
    # this string the tail of a different component; ``(?!\w)`` rejects
    # names where cmd is only a prefix of the real component.
    v0_pat = re.compile(r"(?<!\d)" + str(len(cmd)) + re.escape(cmd) + r"(?!\w)")
    if v0_pat.search(fn_name):
        return True
    return False


def _lines_from_regions(regions: list) -> tuple[int, int]:
    """Derive (covered_lines, total_lines) from llvm-cov's per-function
    ``regions`` array.

    Each region entry is a list:
      [line_start, col_start, line_end, col_end, execution_count,
       file_id, expanded_file_id, kind]

    We only consider regions in the primary file (``file_id == 0``) and
    regions of kind 0 (Code) — kind 2 is SkippedRegion and kind 1 is
    ExpansionRegion. A line is "covered" if ANY region touching it has
    execution_count > 0.
    """
    if not regions:
        return (0, 0)
    covered: set[int] = set()
    all_lines: set[int] = set()
    for r in regions:
        # Be defensive: some entries may be shorter or have extra fields.
        if not r or len(r) < 5:
            continue
        line_start = int(r[0])
        line_end = int(r[2])
        count = int(r[4])
        file_id = int(r[5]) if len(r) > 5 else 0
        kind = int(r[7]) if len(r) > 7 else 0
        if file_id != 0:
            continue
        if kind == 2:  # SkippedRegion
            continue
        for ln in range(line_start, line_end + 1):
            all_lines.add(ln)
            if count > 0:
                covered.add(ln)
    return (len(covered), len(all_lines))


def extract_matches(data: dict[str, Any], cmd: str) -> list[dict[str, Any]]:
    """Walk a cargo-llvm-cov JSON export and collect per-function entries
    whose mangled name matches ``cmd``.

    cargo-llvm-cov's JSON export (v0) doesn't populate per-function
    ``summary``; it only ships the raw ``regions`` array. We therefore
    derive line totals/covered ourselves in ``_lines_from_regions``. If
    a future format does include ``summary.lines``, we prefer it.
    """
    matches: list[dict[str, Any]] = []
    for segment in data.get("data", []) or []:
        for fn in segment.get("functions", []) or []:
            name = fn.get("name", "") or ""
            if not name_matches(name, cmd):
                continue
            filenames = fn.get("filenames") or ["?"]
            summary = fn.get("summary") or {}
            lines = summary.get("lines") if isinstance(summary, dict) else None
            if lines and isinstance(lines, dict) and int(lines.get("count", 0) or 0):
                covered = int(lines.get("covered", 0) or 0)
                total = int(lines.get("count", 0) or 0)
            else:
                covered, total = _lines_from_regions(fn.get("regions") or [])
            pct = (100.0 * covered / total) if total else 0.0
            matches.append(
                {
                    "function": name,
                    "file": filenames[0],
                    "lines_covered": covered,
                    "lines_total": total,
                    "coverage_pct": pct,
                }
            )
    return matches


def render_text(cmd: str, matches: list[dict[str, Any]]) -> str:
    """Human-readable multi-line summary for terminal output."""
    lines = []
    for m in matches:
        lines.append(m["function"])
        lines.append(f"  file: {m['file']}")
        pct = m["coverage_pct"]
        lines.append(
            f"  lines: {m['lines_covered']}/{m['lines_total']} ({pct:.1f}%)"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def render_json(cmd: str, matches: list[dict[str, Any]]) -> str:
    """Stable JSON shape consumed by other scripts."""
    return json.dumps({"command": cmd, "matches": matches}, indent=2)


def run(cmd: str, json_path: str, json_mode: bool) -> int:
    with open(json_path) as f:
        data = json.load(f)
    matches = extract_matches(data, cmd)
    if not matches:
        sys.stderr.write(f"No functions matched command name {cmd!r}\n")
        return 3
    out = render_json(cmd, matches) if json_mode else render_text(cmd, matches)
    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        sys.stderr.write(
            "usage: _cov_filter_impl.py <command_name> <json_path> <0|1>\n"
        )
        return 2
    cmd, path, mode_s = argv[1], argv[2], argv[3]
    try:
        mode = int(mode_s)
    except ValueError:
        sys.stderr.write(f"bad json-mode flag: {mode_s!r}\n")
        return 2
    return run(cmd, path, bool(mode))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
