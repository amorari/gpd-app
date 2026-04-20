"""Regenerate the committed English i18n fixture from canonical source files.

Reads directly from:
  - packages/app/src/i18n/en.ts      (main application strings)
  - packages/desktop/src/i18n/en.ts  (desktop-namespace strings)

Parses the TypeScript dict object with a regex, merges both dicts (desktop
keys win on collision), then writes the result to the committed fixture at
gpd_tests/fixtures/en.json.

Note: Multi-line TypeScript string values (where the value spans two lines
with a line-continuation) are intentionally not captured by the line-by-line
regex. This is acceptable because all keys needed by the test suite are
single-line values.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

# packages/desktop/tests-gui/scripts/refresh_en_dict.py
#   → .parent     = scripts/
#   → .parent.parent = tests-gui/
#   → .parent.parent.parent = desktop/
#   → .parent.parent.parent.parent = packages/
#   → .parent.parent.parent.parent.parent = repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

CANONICAL_APP = _REPO_ROOT / "packages" / "app" / "src" / "i18n" / "en.ts"
CANONICAL_DESKTOP = _REPO_ROOT / "packages" / "desktop" / "src" / "i18n" / "en.ts"
COMMITTED = Path(__file__).resolve().parent.parent / "gpd_tests" / "fixtures" / "en.json"

# Matches:  "some.key": "Some value",
# Groups:   k=key, v=value
KEY_VALUE_RE = re.compile(r'^\s*"(?P<k>[^"]+)":\s*"(?P<v>[^"]*)"\s*,?\s*$')


def parse_en_ts(src: str) -> dict[str, str]:
    """Parse a TypeScript i18n dict, extracting single-line key-value pairs."""
    out: dict[str, str] = {}
    for line in src.splitlines():
        m = KEY_VALUE_RE.match(line)
        if m:
            # Decode JS string escapes (e.g. \\n → newline, \\t → tab).
            out[m.group("k")] = m.group("v").encode().decode("unicode_escape")
    return out


def main() -> int:
    if not CANONICAL_APP.exists():
        print(
            f"canonical source not found: {CANONICAL_APP}",
            file=sys.stderr,
        )
        return 2
    if not CANONICAL_DESKTOP.exists():
        print(
            f"canonical desktop source not found: {CANONICAL_DESKTOP}",
            file=sys.stderr,
        )
        return 2

    app_dict = parse_en_ts(CANONICAL_APP.read_text(encoding="utf-8"))
    desktop_dict = parse_en_ts(CANONICAL_DESKTOP.read_text(encoding="utf-8"))

    # Merge: app keys first, desktop keys override on collision.
    new: dict[str, str] = {**app_dict, **desktop_dict}

    old: dict[str, str] = json.loads(COMMITTED.read_text()) if COMMITTED.exists() else {}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(new) & set(old) if new[k] != old[k])

    if not (added or removed or changed):
        print(f"no change ({len(new)} keys)")
        return 0

    COMMITTED.write_text(
        json.dumps(new, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"updated: +{len(added)} -{len(removed)} ~{len(changed)} (total {len(new)} keys)")
    for k in added[:10]:
        print(f"  + {k}")
    for k in removed[:10]:
        print(f"  - {k}")
    for k in changed[:10]:
        print(f"  ~ {k}")

    try:
        subprocess.run(
            ["git", "diff", "--stat", "--", str(COMMITTED)],
            cwd=str(_REPO_ROOT),
            check=False,
        )
    except FileNotFoundError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
