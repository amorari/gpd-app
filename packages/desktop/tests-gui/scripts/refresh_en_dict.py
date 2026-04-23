"""Regenerate the committed English i18n fixture from canonical source files.

Reads directly from:
  - packages/app/src/i18n/en.ts      (main application strings)
  - packages/desktop/src/i18n/en.ts  (desktop-namespace strings)

Parses the TypeScript dict object, merges both dicts (desktop keys win on
collision), then writes the result to the committed fixture at
gpd_tests/fixtures/en.json.

The parser tolerates:
  - both ``"..."`` and ``'...'`` string-literal delimiters for values
  - multi-line dict entries where the ``"key":`` is on one line and the
    value string literal is on the following line (TypeScript/Prettier's
    wrap style when the line is too long)
  - escaped quotes inside values (``\"`` and ``\'``)

Because the source ``.ts`` files are read as UTF-8 text, the only escapes
that need to be materialized inside the captured value are the JS string
escapes themselves: ``\\\\``, ``\\"``, ``\\'``, ``\\n``, ``\\r``, ``\\t``.
We apply those with targeted ``str.replace()`` calls rather than the
``unicode_escape`` codec, which is a Latin-1 codec that corrupts any
multi-byte UTF-8 characters in the source (``…``, ``—``, ``μ``, the
language-name CJK/Cyrillic, etc.).
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

# Matches a key-value pair where the value is a ``"..."`` or ``'...'`` string
# literal. The value character class permits any non-delimiter / non-backslash
# byte plus ``\\.`` escape sequences, so embedded ``\"`` / ``\'`` are tolerated.
# The value may sit on the same line as the key, or (with DOTALL) wrap to the
# next line after the ``":"``; intervening whitespace, including newlines, is
# absorbed by ``\s*``.
KEY_VALUE_RE = re.compile(
    r'"(?P<k>[^"\\]*(?:\\.[^"\\]*)*)"\s*:\s*'
    r'(?P<q>["\'])(?P<v>(?:[^\\]|\\.)*?)(?P=q)',
    re.DOTALL,
)


def _unescape_js_string(raw: str) -> str:
    """Materialize JS string-literal escapes in *raw* without mangling UTF-8.

    ``raw`` is the inside of a ``"..."`` or ``'...'`` literal read from a
    UTF-8 text file — the non-ASCII characters are already correct Python
    ``str`` characters. We only need to resolve the backslash escapes.

    Order matters: ``\\\\`` must be handled first so we don't double-process
    the backslash it leaves behind.
    """
    # Placeholder dance so ``\\\\`` → literal ``\\`` doesn't interfere with
    # the subsequent single-char replacements.
    _SENTINEL = "\x00BS\x00"
    result = raw.replace("\\\\", _SENTINEL)
    result = result.replace('\\"', '"')
    result = result.replace("\\'", "'")
    result = result.replace("\\n", "\n")
    result = result.replace("\\r", "\r")
    result = result.replace("\\t", "\t")
    result = result.replace("\\`", "`")
    result = result.replace("\\/", "/")
    result = result.replace(_SENTINEL, "\\")
    return result


def parse_en_ts(src: str) -> dict[str, str]:
    """Parse a TypeScript i18n dict, returning a ``{key: value}`` mapping.

    Captures both single-line and wrapped key-value entries, and both
    ``"..."`` and ``'...'`` value delimiters. See module docstring for the
    full list of handled cases.
    """
    out: dict[str, str] = {}
    for m in KEY_VALUE_RE.finditer(src):
        key = _unescape_js_string(m.group("k"))
        value = _unescape_js_string(m.group("v"))
        out[key] = value
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
