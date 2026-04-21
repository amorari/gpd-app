#!/usr/bin/env python3
"""
Unified sidecar entry point for PyInstaller-bundled GPD MCP servers.

Usage:
    gpd-sidecar serve-mcp gpd-conventions     # Run a specific MCP server (stdio)
    gpd-sidecar list-servers --json            # Emit opencode.json MCP config
    gpd-sidecar install opencode --global      # Normal GPD CLI install
    gpd-sidecar --version                      # Print version

This file dispatches to the right GPD module based on the subcommand.
The PyInstaller binary bundles the entire GPD package, so all servers
and the CLI are available from one binary.
"""

import importlib
import json
import sys


def _get_sidecar_path() -> str:
    """Return the path to this binary (for generating MCP configs)."""
    import os
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(__file__)


def cmd_serve_mcp(server_name: str) -> None:
    """Run a specific MCP server via stdio transport."""
    from gpd.mcp.builtin_servers import _BUILTIN_SERVERS

    if server_name not in _BUILTIN_SERVERS:
        available = ", ".join(sorted(_BUILTIN_SERVERS.keys()))
        print(f"Unknown server: {server_name}", file=sys.stderr)
        print(f"Available: {available}", file=sys.stderr)
        sys.exit(1)

    entry = _BUILTIN_SERVERS[server_name]
    args = entry.get("args", [])
    if len(args) >= 2 and args[0] == "-m":
        module_path = args[1]
    else:
        print(f"Server {server_name} has no module path", file=sys.stderr)
        sys.exit(1)

    # Strip our args so the server sees a clean argv
    sys.argv = [sys.argv[0]]

    mod = importlib.import_module(module_path)
    mod.main()


def cmd_list_servers(as_json: bool = True) -> None:
    """Emit the MCP server config for opencode.json."""
    from gpd.mcp.builtin_servers import _BUILTIN_SERVERS

    sidecar = _get_sidecar_path()
    servers = {}

    for name, entry in _BUILTIN_SERVERS.items():
        # Check if optional deps are available
        module_check = entry.get("module_check")
        if module_check:
            try:
                importlib.import_module(module_check)
            except ImportError:
                continue

        servers[name] = {
            "type": "local",
            "command": [sidecar, "serve-mcp", name],
            "enabled": True,
        }

        env = entry.get("env")
        if env:
            servers[name]["environment"] = env

    if as_json:
        print(json.dumps(servers, indent=2))
    else:
        for name in sorted(servers):
            print(f"  {name}")


def main() -> None:
    if len(sys.argv) < 2:
        # Fall through to GPD CLI
        from gpd.cli import entrypoint
        entrypoint()
        return

    cmd = sys.argv[1]

    if cmd == "serve-mcp":
        if len(sys.argv) < 3:
            print("Usage: gpd-sidecar serve-mcp <server-name>", file=sys.stderr)
            sys.exit(1)
        cmd_serve_mcp(sys.argv[2])

    elif cmd == "list-servers":
        as_json = "--json" in sys.argv
        cmd_list_servers(as_json=as_json)

    elif cmd in ("--version", "-v"):
        from gpd.core.version import __version__
        print(__version__)

    else:
        # Everything else goes to the normal GPD CLI
        from gpd.cli import entrypoint
        entrypoint()


if __name__ == "__main__":
    main()
