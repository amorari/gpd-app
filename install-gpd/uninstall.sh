#!/usr/bin/env bash
# GPD — Get Physics Done: uninstaller
#
# Usage:
#   bash uninstall.sh
#   bash uninstall.sh --yes    # skip confirmation prompt
#
# Removes everything created by the GPD installer:
#   - ~/.gpd/ directory (bin, config, python, venv)
#   - PATH entries from shell rc files
#   - GPD_API_KEY exports from login profiles
#   - GPD .deb package (Ubuntu, if installed)

set -euo pipefail

# ── Colors & logging ──────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

log()     { printf " ${CYAN}i${RESET} %s\n" "$*"; }
success() { printf " ${GREEN}+${RESET} %s\n" "$*"; }
warn()    { printf " ${YELLOW}!${RESET} %s\n" "$*"; }
skip()    { printf " ${DIM}-${RESET} %s\n" "$*"; }

# ── Arguments ─────────────────────────────────────────────────────────────

auto_yes=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        -y|--yes) auto_yes=true; shift ;;
        -h|--help)
            printf "Usage: uninstall.sh [--yes]\n"
            printf "  --yes, -y   Skip confirmation prompt\n"
            exit 0
            ;;
        *) shift ;;
    esac
done

# ── Configuration ─────────────────────────────────────────────────────────

GPD_HOME="${GPD_HOME:-$HOME/.gpd}"
GPD_BIN_DIR="$GPD_HOME/bin"

# ── Discovery: show what will be removed ──────────────────────────────────

printf "\n"
printf "${BOLD} GPD Uninstaller${RESET}\n"
printf "\n"

found_anything=false

if [[ -d "$GPD_HOME" ]]; then
    log "Found GPD directory: $GPD_HOME"
    found_anything=true
fi

# Check for .deb package (Ubuntu/Debian)
deb_package=""
if command -v dpkg &>/dev/null; then
    if dpkg -l gpd 2>/dev/null | grep -q "^ii"; then
        deb_package="gpd"
        log "Found GPD .deb package: $deb_package"
        found_anything=true
    fi
fi

# Check shell rc files for PATH entries
rc_files_with_path=()
for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.config/fish/config.fish"; do
    if [[ -f "$rc" ]] && grep -q "$GPD_BIN_DIR" "$rc" 2>/dev/null; then
        rc_files_with_path+=("$rc")
        log "Found PATH entry in: $rc"
        found_anything=true
    fi
done

# Check login profiles for GPD_API_KEY
profiles_with_key=()
for profile in "$HOME/.profile" "$HOME/.zprofile" "${ZDOTDIR:-$HOME}/.zprofile"; do
    # Avoid duplicates
    [[ " ${profiles_with_key[*]:-} " == *" $profile "* ]] && continue
    if [[ -f "$profile" ]] && grep -q "GPD_API_KEY" "$profile" 2>/dev/null; then
        profiles_with_key+=("$profile")
        log "Found GPD_API_KEY export in: $profile"
        found_anything=true
    fi
done

if [[ "$found_anything" == false ]]; then
    printf " ${DIM}Nothing to remove — GPD does not appear to be installed.${RESET}\n\n"
    exit 0
fi

# ── Confirmation ──────────────────────────────────────────────────────────

printf "\n"
if [[ "$auto_yes" == false ]]; then
    printf " ${BOLD}Remove GPD and all its files?${RESET} [y/N] "
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        printf " Cancelled.\n\n"
        exit 0
    fi
fi

printf "\n"

# ── Remove .deb package ──────────────────────────────────────────────────

if [[ -n "$deb_package" ]]; then
    log "Removing GPD .deb package..."
    if sudo dpkg --remove "$deb_package" 2>/dev/null; then
        success "Removed .deb package: $deb_package"
    else
        warn "Failed to remove .deb package (may need manual: sudo dpkg --remove $deb_package)"
    fi
else
    skip "No .deb package installed"
fi

# ── Remove PATH entries from shell rc files ───────────────────────────────

remove_lines_from_file() {
    local file="$1"
    local pattern="$2"
    local comment_pattern="${3:-}"

    if [[ ! -f "$file" ]]; then
        return
    fi

    local tmp
    tmp="$(mktemp)"

    # Remove matching lines and the "# GPD CLI" comment line above them
    if [[ -n "$comment_pattern" ]]; then
        grep -v -F "$pattern" "$file" | grep -v -F "$comment_pattern" > "$tmp" || true
    else
        grep -v -F "$pattern" "$file" > "$tmp" || true
    fi

    # Only write back if content actually changed
    if ! diff -q "$file" "$tmp" &>/dev/null; then
        mv "$tmp" "$file"
        return 0
    else
        rm -f "$tmp"
        return 1
    fi
}

if (( ${#rc_files_with_path[@]} > 0 )); then
    for rc in "${rc_files_with_path[@]}"; do
        if remove_lines_from_file "$rc" "$GPD_BIN_DIR" "# GPD CLI"; then
            success "Removed PATH entry from $rc"
        fi
    done
else
    skip "No PATH entries to remove"
fi

# ── Remove GPD_API_KEY exports from login profiles ────────────────────────

if (( ${#profiles_with_key[@]} > 0 )); then
    for profile in "${profiles_with_key[@]}"; do
        if remove_lines_from_file "$profile" "GPD_API_KEY" "# GPD API key"; then
            success "Removed GPD_API_KEY from $profile"
        fi
    done
else
    skip "No GPD_API_KEY exports to remove"
fi

# ── Remove GPD directory ─────────────────────────────────────────────────

if [[ -d "$GPD_HOME" ]]; then
    rm -rf "$GPD_HOME"
    success "Removed $GPD_HOME"
else
    skip "$GPD_HOME already removed"
fi

# ── Done ──────────────────────────────────────────────────────────────────

printf "\n"
printf " ${GREEN}${BOLD}GPD has been uninstalled.${RESET}\n"
printf " ${DIM}Open a new terminal to clear any cached PATH entries.${RESET}\n"
printf "\n"
