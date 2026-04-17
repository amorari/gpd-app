#!/usr/bin/env bash
# GPD installer for Ubuntu 24.04+
#
# Usage:
#   bash install.sh
#   curl -fsSL <url>/install/ubuntu_24_04/install.sh | bash
#
# Installs: GPD desktop app (.deb), Python 3.11+ (app-local), GPD package, gpd command.
# The .deb installs system-wide to /usr/bin/; everything else goes into ~/.gpd/.

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

    # python3-venv is needed if system Python is present but venv creation fails.
    # Note: "python3 -m venv --help" can exit 0 even when ensurepip is missing,
    # so we test actual venv creation instead.
    if command_exists python3; then
        local test_venv
        test_venv="$(mktemp -d)"
        if ! python3 -m venv "$test_venv" &>/dev/null; then
            local pyver
            pyver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
            missing+=("python${pyver}-venv")
        fi
        rm -rf "$test_venv"
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

# ── Override: install GPD .deb instead of standalone CLI binary ────────────

install_opencode() {
    local os="$1" arch="$2"
    local dest="$GPD_BIN_DIR/opencode"

    if [[ -x "/usr/bin/opencode-cli" ]] && [[ -x "/usr/bin/GPD" ]]; then
        success "GPD desktop app already installed"
        ln -sf /usr/bin/opencode-cli "$dest" 2>/dev/null || true
        return 0
    fi

    local api_url="https://api.github.com/repos/${OPENCODE_ORG}/${OPENCODE_REPO}/releases/latest"
    local deb_url=""
    deb_url="$(curl -fsSL "$api_url" 2>/dev/null \
        | grep -oE '"browser_download_url":\s*"[^"]*_amd64\.deb"' \
        | grep -oE 'https://[^"]+' \
        | head -1)" || true

    log "Checking for GPD desktop .deb release..."
    if [[ -n "$deb_url" ]] && url_exists "$deb_url"; then
        local tmp_dir
        tmp_dir="$(mktemp -d)"
        local deb_file="$tmp_dir/gpd.deb"

        download "$deb_url" "$deb_file"
        log "Installing GPD desktop app..."
        sudo dpkg -i "$deb_file" 2>&1 || sudo apt-get install -f -y -qq 2>&1
        rm -rf "$tmp_dir"

        if [[ -x "/usr/bin/opencode-cli" ]]; then
            ln -sf /usr/bin/opencode-cli "$dest"
            success "GPD desktop app installed (CLI: /usr/bin/opencode-cli, GUI: /usr/bin/GPD)"
        else
            die "GPD .deb installed but opencode-cli not found at /usr/bin/opencode-cli"
        fi
    else
        warn "GPD .deb not found, falling back to standalone CLI binary"
        # Fall back to the upstream CLI binary download from common.sh
        local asset
        asset="$(opencode_asset_name "$os" "$arch")"
        local fallback_url="https://github.com/${OPENCODE_FALLBACK_ORG}/${OPENCODE_FALLBACK_REPO}/releases/latest/download/${asset}"

        if ! url_exists "$fallback_url"; then
            die "Could not find OpenCode CLI binary for ${os}/${arch}. Check network connectivity."
        fi

        local tmp_dir
        tmp_dir="$(mktemp -d)"
        local archive="$tmp_dir/$asset"
        download "$fallback_url" "$archive"

        log "Extracting OpenCode CLI..."
        tar -xzf "$archive" -C "$tmp_dir"
        local binary
        binary="$(find "$tmp_dir" -name 'opencode' -type f -not -path "$archive" | head -1)"

        if [[ -z "$binary" ]]; then
            rm -rf "$tmp_dir"
            die "Could not find opencode binary in downloaded archive"
        fi

        mv "$binary" "$dest"
        chmod +x "$dest"
        rm -rf "$tmp_dir"
        success "OpenCode CLI installed to $dest (standalone, no desktop app)"
    fi
}

# ── Main ───────────────────────────────────────────────────────────────────

install_system_deps

OS="linux"
ARCH="$(detect_arch)"

run_install "$OS" "$ARCH"
