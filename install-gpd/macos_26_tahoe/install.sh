#!/usr/bin/env bash
# GPD CLI installer for macOS (Tahoe / 26+)
#
# Usage:
#   bash install.sh
#   curl -fsSL <url>/install/macos_26_tahoe/install.sh | bash
#
# Installs: OpenCode CLI, Python 3.11+ (app-local), GPD package, gpd command.
# Everything goes into ~/.gpd/ — no system-wide changes except PATH in ~/.zshrc.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${SCRIPT_DIR}/../common.sh"

if [[ ! -f "$COMMON" ]]; then
    echo "Error: common.sh not found at $COMMON" >&2
    echo "Run this script from the install directory or download the full installer." >&2
    exit 1
fi

source "$COMMON"

# ── macOS-specific setup ──────────────────────────────────────────────────

OS="darwin"
ARCH="$(detect_arch)"

# Detect Rosetta translation: if running x64 under Rosetta on Apple Silicon,
# prefer native arm64 binaries.
if [[ "$ARCH" == "x64" ]]; then
    if sysctl -n sysctl.proc_translated 2>/dev/null | grep -q 1; then
        log "Detected Rosetta translation — using native arm64 binaries"
        ARCH="arm64"
    fi
fi

# macOS ships with curl, but verify unzip is available (it should be).
for cmd in curl unzip tar; do
    if ! command_exists "$cmd"; then
        die "Required tool '$cmd' not found. Install Xcode Command Line Tools: xcode-select --install"
    fi
done

run_install "$OS" "$ARCH"
