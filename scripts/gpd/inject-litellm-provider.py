#!/usr/bin/env python3
"""
Inject the LiteLLM provider configuration into OpenCode's opencode.json.

Run AFTER `gpd install opencode --global` to add the PSI LiteLLM proxy
as the provider. This is idempotent — safe to run multiple times.

Usage:
    python3 inject-litellm-provider.py [--config-dir ~/.config/opencode]
"""

import json
from pathlib import Path

LITELLM_URL = "https://litellm-production-46bb.up.railway.app/v1"

PROVIDER_CONFIG = {
    "gpd": {
        "name": "GPD (PSI)",
        "api": LITELLM_URL,
        "env": ["GPD_API_KEY"],
        "models": {
            "claude-opus-4-6": {
                "name": "Claude Opus 4.6",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 131_072},
            },
            "claude-sonnet-4-6": {
                "name": "Claude Sonnet 4.6",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 65_536},
            },
            "claude-haiku-4-5": {
                "name": "Claude Haiku 4.5",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 200_000, "output": 65_536},
            },
            "gpt-5.4": {
                "name": "GPT-5.4",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_050_000, "output": 131_072},
            },
            "gpt-5.4-mini": {
                "name": "GPT-5.4 mini",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_050_000, "output": 131_072},
            },
            "gpt-5.4-nano": {
                "name": "GPT-5.4 nano",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_050_000, "output": 131_072},
            },
            "gpt-5.4-pro": {
                "name": "GPT-5.4 Pro",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_050_000, "output": 131_072},
            },
            "gpt-5.3-codex": {
                "name": "GPT-5.3 Codex",
                "tool_call": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 32_768},
            },
            "gpt-4.1": {
                "name": "GPT-4.1",
                "tool_call": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 32_768},
            },
            "gpt-4.1-mini": {
                "name": "GPT-4.1 mini",
                "tool_call": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 32_768},
            },
            "o4-mini": {
                "name": "o4-mini (reasoning)",
                "tool_call": True,
                "reasoning": True,
                "temperature": True,
                "limit": {"context": 200_000, "output": 100_000},
            },
            "gemini-3.1-pro-preview": {
                "name": "Gemini 3.1 Pro",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 65_536},
            },
            "gemini-3-flash-preview": {
                "name": "Gemini 3 Flash",
                "tool_call": True,
                "reasoning": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 65_536},
            },
            "gemini-3.1-flash-lite-preview": {
                "name": "Gemini 3.1 Flash-Lite",
                "tool_call": True,
                "attachment": True,
                "temperature": True,
                "limit": {"context": 1_000_000, "output": 65_536},
            },
        },
    }
}


def inject_provider(config_dir: Path) -> None:
    config_path = config_dir / "opencode.json"

    # Read existing config (GPD install should have created it with MCP servers)
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    # Merge provider config (don't overwrite existing providers)
    if "provider" not in config:
        config["provider"] = {}
    config["provider"]["gpd"] = PROVIDER_CONFIG["gpd"]

    # Set default model to Claude Sonnet 4.6
    config["model"] = "gpd/claude-sonnet-4-6"

    # Only show GPD models in the picker
    config["enabled_providers"] = ["gpd"]

    # Write back
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Provider config injected into {config_path}")


def store_api_key(key: str) -> None:
    """Store the API key in OpenCode's auth.json (0600 permissions)."""
    data_dir = Path.home() / ".local" / "share" / "opencode"
    data_dir.mkdir(parents=True, exist_ok=True)
    auth_path = data_dir / "auth.json"

    # Read existing auth (may have other provider keys)
    if auth_path.exists():
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    else:
        auth = {}

    auth["gpd"] = {"type": "api", "key": key}

    auth_path.write_text(json.dumps(auth, indent=2) + "\n", encoding="utf-8")
    auth_path.chmod(0o600)
    print(f"API key stored in {auth_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Inject LiteLLM provider config into OpenCode")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path.home() / ".config" / "gpd",
        help="OpenCode config directory (default: ~/.config/gpd)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="GPD API key to store (optional — can be set later)",
    )
    args = parser.parse_args()

    inject_provider(args.config_dir)

    if args.api_key:
        store_api_key(args.api_key)
    else:
        print("No API key provided. Set GPD_API_KEY env var or run with --api-key.")
