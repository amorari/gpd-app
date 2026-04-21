"""Extract every #[tauri::command] from src-tauri/src/*.rs into a catalog.

Output schema:
  [{"name": str, "file": str, "line": int, "signature": str, "async": bool}]

Usage: python scripts/extract_tauri_commands.py > gpd_tests/fixtures/tauri_commands.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def extract(rs_file: Path) -> list[dict]:
    text = rs_file.read_text()
    results = []
    pattern = re.compile(
        r"#\[tauri::command\][^\n]*\n"
        r"(?:\s*#\[[^\]]+\][^\n]*\n)*"
        r"(?P<sig>\s*(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)[^{]*)\{",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        sig = m.group("sig").strip()
        name = m.group("name")
        line = text[: m.start()].count("\n") + 1
        results.append(
            {
                "name": name,
                "file": rs_file.name,
                "line": line,
                "signature": sig,
                "async": "async fn" in sig,
            }
        )
    return results


def main() -> int:
    src_dir = Path(__file__).resolve().parents[2] / "src-tauri" / "src"
    all_commands = []
    for rs in sorted(src_dir.glob("*.rs")):
        all_commands.extend(extract(rs))
    json.dump(all_commands, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
