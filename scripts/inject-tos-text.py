"""Inject infra/legal/TOS-v<VERSION>.md into packages/app/src/components/tos-content.tsx.

Replaces the TOS_TEXT template literal, bumps CURRENT_TOS_VERSION, recomputes
TOS_TEXT_SHA256. PRIVACY_TEXT is left untouched — handled by a separate run
once PSI legal clears the Privacy Policy draft.

Usage:
    python3 scripts/inject-tos-text.py <version>
e.g. python3 scripts/inject-tos-text.py 1.0

Contract:
  * Reads infra/legal/TOS-v<version>.md verbatim.
  * Escapes only template-literal-hostile chars: backslash, backtick, ${.
  * Checks that the source contains no bare backticks (CI regex in
    scripts/check-tos-hashes.py uses `[^`]+` — bare backticks break it).
  * SHA256 is over the escaped string exactly as it appears between
    backticks in the .tsx file — matches CI's hash.
  * Leaves the [PLACEHOLDER — DO NOT SHIP] banner in the PRIVACY_TEXT and
    in the top-of-file JSDoc until Privacy delivery.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys


REPO = pathlib.Path(__file__).resolve().parent.parent
TSX = REPO / "packages/app/src/components/tos-content.tsx"


def escape_for_template_literal(raw: str) -> str:
    # Order matters: backslash first so subsequent escapes don't get doubled.
    return raw.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <version>  # e.g. 1.0", file=sys.stderr)
        return 2
    version = argv[1]
    md_path = REPO / f"infra/legal/TOS-v{version}.md"
    if not md_path.exists():
        print(f"ERROR: {md_path} not found", file=sys.stderr)
        return 2

    raw = md_path.read_text(encoding="utf-8").rstrip() + "\n"
    if "`" in raw:
        print(
            "ERROR: source contains a backtick. CI regex in "
            "scripts/check-tos-hashes.py uses [^`]+ and will stop at the "
            "first backtick. Either remove it or update the CI regex to "
            "handle escaped backticks.",
            file=sys.stderr,
        )
        return 1

    escaped = escape_for_template_literal(raw)
    sha256 = hashlib.sha256(escaped.encode("utf-8")).hexdigest()

    src = TSX.read_text(encoding="utf-8")

    # 1. Replace TOS_TEXT template literal body.
    tos_pattern = re.compile(
        r"export const TOS_TEXT = `[^`]*`",
        flags=re.DOTALL,
    )
    new_tos_literal = f"export const TOS_TEXT = `{escaped}`"
    if not tos_pattern.search(src):
        print("ERROR: TOS_TEXT template literal not found in tos-content.tsx", file=sys.stderr)
        return 1
    src = tos_pattern.sub(new_tos_literal, src, count=1)

    # 2. Bump CURRENT_TOS_VERSION.
    ver_pattern = re.compile(r'export const CURRENT_TOS_VERSION = "[^"]*"')
    new_ver_literal = f'export const CURRENT_TOS_VERSION = "{version}"'
    if not ver_pattern.search(src):
        print("ERROR: CURRENT_TOS_VERSION declaration not found", file=sys.stderr)
        return 1
    src = ver_pattern.sub(new_ver_literal, src, count=1)

    # 3. Update TOS_TEXT_SHA256.
    sha_pattern = re.compile(
        r'export const TOS_TEXT_SHA256 =\s*\n?\s*"[0-9a-f]{64}"'
    )
    new_sha_literal = f'export const TOS_TEXT_SHA256 =\n  "{sha256}"'
    if not sha_pattern.search(src):
        print("ERROR: TOS_TEXT_SHA256 declaration not found", file=sys.stderr)
        return 1
    src = sha_pattern.sub(new_sha_literal, src, count=1)

    TSX.write_text(src, encoding="utf-8")

    print(f"injected {md_path.name} ({len(raw)} chars) into {TSX.relative_to(REPO)}")
    print(f"  CURRENT_TOS_VERSION  = {version}")
    print(f"  TOS_TEXT_SHA256      = {sha256}")
    print()
    print(
        "NOTE: PRIVACY_TEXT still [PLACEHOLDER]. Release CI (tos-guard job) "
        "will reject builds until Privacy Policy is injected via the "
        "companion script once legal clears the draft."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
