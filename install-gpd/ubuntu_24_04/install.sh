#!/usr/bin/env bash
# GPD CLI installer for Ubuntu 24.04+
#
# Usage:
#   bash install.sh
#   curl -fsSL <url>/install/ubuntu_24_04/install.sh | bash
#
# Installs: OpenCode CLI, Python 3.11+ (app-local), GPD package, gpd command.
# Everything goes into ~/.gpd/ — no system-wide changes except PATH in ~/.bashrc.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/../common.sh"

if [[ ! -f "$COMMON" ]]; then
    echo "Error: common.sh not found at $COMMON" >&2
    echo "Run this script from the install directory or download the full installer." >&2
    exit 1
fi

source "$COMMON"

# ── Ubuntu-specific prerequisites ──────────────────────────────────────────

install_system_deps() {
    local missing=()
    for cmd in curl tar unzip; do
        if ! command_exists "$cmd"; then
            missing+=("$cmd")
        fi
    done

    # python3-venv is needed if system Python is present but venv module is missing
    if command_exists python3 && ! python3 -m venv --help &>/dev/null; then
        missing+=("python3-venv")
    fi

    if (( ${#missing[@]} > 0 )); then
        log "Installing system dependencies: ${missing[*]}"
        if command_exists apt-get; then
            sudo apt-get update -qq
            sudo apt-get install -y -qq "${missing[@]}"
        else
            die "Missing tools (${missing[*]}) and apt-get not available. Install them manually."
        fi
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────

install_system_deps

OS="linux"
ARCH="$(detect_arch)"

run_install "$OS" "$ARCH"
