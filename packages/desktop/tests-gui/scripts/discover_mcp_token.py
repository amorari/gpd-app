"""Discover the tauri-plugin-mcp auth token, if any.

Search order:
  1. Env var GPD_MCP_AUTH_TOKEN
  2. File ~/Library/Application Support/<bundle-id>/mcp-auth.token
  3. Recent log lines in ~/Library/Logs/<bundle-id>/ mentioning "auth" and a
     20+ char token (see note below)

Print the token on stdout (or empty line + exit 0 if none found).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from scripts._bundle import bundle_id as _bundle_id

HOME = Path.home()


def _token_paths() -> list[Path]:
    bid = _bundle_id()
    return [
        HOME / "Library/Application Support" / bid / "mcp-auth.token",
    ]


def _log_dir() -> Path:
    return HOME / "Library/Logs" / _bundle_id()


_TOKEN_RE = re.compile(r"token[=: ]\s*([A-Za-z0-9_\-]{20,})")


def discover() -> str:
    env = os.environ.get("GPD_MCP_AUTH_TOKEN")
    if env:
        return env.strip()
    for p in _token_paths():
        if p.exists():
            return p.read_text().strip()
    return _discover_from_logs()


# deprecated: plugin is unauthenticated by default — the tauri-plugin-mcp
# currently writes no token to the log files. This fallback is dead code in
# production but is preserved in case a future config re-enables token auth.
def _discover_from_logs() -> str:
    """Scan recent log files for an auth token.

    NOTE: As of the current plugin version, this function will never find a
    token because the plugin does not log authentication tokens. It is kept
    here for forward compatibility in case a future configuration enables
    token-based auth and the plugin starts logging tokens again.
    """
    log_dir = _log_dir()
    if log_dir.exists():
        logs = sorted(
            log_dir.glob("*.log"),
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
