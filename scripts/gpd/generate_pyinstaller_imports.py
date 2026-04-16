#!/usr/bin/env python3
"""
Generate PyInstaller --hidden-import flags from GPD's builtin server registry.

Usage:
    python generate_pyinstaller_imports.py >> pyinstaller_args.txt
    pyinstaller $(cat pyinstaller_args.txt) sidecar_main.py

This ensures the PyInstaller build automatically includes all MCP server
modules without manual maintenance. When a new server is added to
_BUILTIN_SERVERS, this script picks it up on the next build.
"""

import sys
sys.path.insert(0, "src")

from gpd.mcp.builtin_servers import _BUILTIN_SERVERS

# Core framework imports that PyInstaller may not trace
CORE_IMPORTS = [
    "mcp",
    "mcp.server",
    "mcp.server.fastmcp",
    "pydantic",
    "yaml",
    "jinja2",
    "typer",
    "rich",
]

for imp in CORE_IMPORTS:
    print(f"--hidden-import={imp}")

for name, entry in _BUILTIN_SERVERS.items():
    args = entry.get("args", [])
    if len(args) >= 2 and args[0] == "-m":
        print(f"--hidden-import={args[1]}")

# Also include the integrations
print("--hidden-import=gpd.mcp.integrations.wolfram_bridge")
