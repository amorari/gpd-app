"""Discover the tauri-plugin-mcp auth token, if any.

Search order:
  1. Env var GPD_MCP_AUTH_TOKEN
  2. File ~/Library/Application Support/inc.psi.gpd/mcp-auth.token
  3. Recent log lines in ~/Library/Logs/inc.psi.gpd/ mentioning "auth" and a 20+ char token

Print the token on stdout (or empty line + exit 0 if none found).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOME = Path(os.environ["HOME"])

_TOKEN_PATHS = [
    HOME / "Library/Application Support/inc.psi.gpd/mcp-auth.token",
]

_LOG_DIR = HOME / "Library/Logs/inc.psi.gpd"
_TOKEN_RE = re.compile(r"token[=: ]\s*([A-Za-z0-9_\-]{20,})")


def discover() -> str:
    env = os.environ.get("GPD_MCP_AUTH_TOKEN")
    if env:
        return env.strip()
    for p in _TOKEN_PATHS:
        if p.exists():
            return p.read_text().strip()
    if _LOG_DIR.exists():
        logs = sorted(
            _LOG_DIR.glob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for log in logs[:3]:
            try:
                text = log.read_text(errors="replace")
            except OSError:
                continue
            m = _TOKEN_RE.search(text)
            if m:
                return m.group(1)
    return ""


def main() -> int:
    print(discover())
    return 0


if __name__ == "__main__":
    sys.exit(main())
