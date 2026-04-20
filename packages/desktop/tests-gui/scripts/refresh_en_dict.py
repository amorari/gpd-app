"""Re-extract the English i18n dictionary from the installed GPD bundle.

Strategy: the dict lives inside a brotli-compressed JS chunk in the main
binary. Extraction is complex; for now we provide a stub that reads from
`/tmp/gpd-extract/en.json` (the location the initial recon wrote to) and
diffs against the committed copy. Full extraction from a fresh bundle is
a follow-up (out of scope for Phase 1).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

COMMITTED = Path(__file__).parent.parent / "gpd_tests/fixtures/en.json"
SOURCE = Path("/tmp/gpd-extract/en.json")


def main() -> int:
    if not SOURCE.exists():
        print(
            f"source not found: {SOURCE}\n"
            "Re-run the initial recon extraction first — see spec appendix A.",
            file=sys.stderr,
        )
        return 2
    new = json.loads(SOURCE.read_text())
    old = json.loads(COMMITTED.read_text()) if COMMITTED.exists() else {}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(new) & set(old) if new[k] != old[k])
    if not (added or removed or changed):
        print("no change")
        return 0
    COMMITTED.write_text(
        json.dumps(new, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    print(f"updated: +{len(added)} -{len(removed)} ~{len(changed)}")
    for k in added[:10]:
        print(f"  + {k}")
    for k in removed[:10]:
        print(f"  - {k}")
    for k in changed[:10]:
        print(f"  ~ {k}")
    try:
        subprocess.run(
            ["git", "diff", "--stat", "--", str(COMMITTED)],
            cwd=COMMITTED.parent.parent.parent,
            check=False,
        )
    except FileNotFoundError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
