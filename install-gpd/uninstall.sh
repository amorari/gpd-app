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
#   - "gpd" provider entry from opencode's auth.json
#   - GUI config dirs (~/.config/gpd, ~/.config/inc.psi.gpd)
#   - GPD-specific entries inside ~/.config/opencode/ (preserves opencode itself)

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

# auth.json lives under XDG_DATA_HOME (Linux) or ~/Library/Application Support (macOS).
# The installer writes all three on the respective platforms; check all of them
# so we clean up correctly even if XDG_DATA_HOME was set at install time but
# not now (or vice versa).
auth_json_candidates=()
if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    auth_json_candidates+=("$XDG_DATA_HOME/opencode/auth.json")
fi
auth_json_candidates+=("$HOME/.local/share/opencode/auth.json")
auth_json_candidates+=("$HOME/Library/Application Support/opencode/auth.json")

# GUI config directories (full app state — safe to remove entirely).
# Also includes the Tauri WebView data dirs under ~/.local/share and
# ~/.cache where the browser localStorage (incl. "gpd.key.saved" flag),
# cookies, IndexedDB, and cache live. Without these, a fresh install
# would inherit the previous user's key prompt state. macOS paths are
# covered by the macOS uninstaller (uninstall_macos.sh); here we handle
# Linux XDG layout.
gui_config_dirs=(
    "$HOME/.config/gpd"
    "$HOME/.config/inc.psi.gpd"
    "$HOME/.local/share/inc.psi.gpd"
    "$HOME/.cache/inc.psi.gpd"
)

# opencode's global config dir — PRESERVE, but strip GPD-specific entries.
opencode_config_dir="$HOME/.config/opencode"

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

# Check for auth.json files containing a "gpd" provider entry
auth_json_files=()
seen_auth=""
for candidate in "${auth_json_candidates[@]}"; do
    # de-dupe (XDG_DATA_HOME may resolve to the same path)
    case "$seen_auth" in *"|$candidate|"*) continue ;; esac
    seen_auth="$seen_auth|$candidate|"
    if [[ -f "$candidate" ]] && grep -q '"gpd"' "$candidate" 2>/dev/null; then
        auth_json_files+=("$candidate")
        log "Found auth.json at: $candidate"
        found_anything=true
    fi
done

# Check for GUI config directories
gui_dirs_found=()
for d in "${gui_config_dirs[@]}"; do
    if [[ -d "$d" ]]; then
        gui_dirs_found+=("$d")
        log "Found GUI config directory: $d"
        found_anything=true
    fi
done

# Check for GPD-specific artifacts inside opencode's global config
opencode_json_has_gpd=false
opencode_manifest=""
if [[ -f "$opencode_config_dir/opencode.json" ]] && grep -q '"gpd"' "$opencode_config_dir/opencode.json" 2>/dev/null; then
    opencode_json_has_gpd=true
    log "Found GPD entry in: $opencode_config_dir/opencode.json"
    found_anything=true
fi
if [[ -f "$opencode_config_dir/gpd-file-manifest.json" ]]; then
    opencode_manifest="$opencode_config_dir/gpd-file-manifest.json"
    log "Found GPD file manifest: $opencode_manifest"
    found_anything=true
fi

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

# ── Remove "gpd" entry from auth.json (preserve other providers) ──────────

remove_gpd_from_auth_json() {
    local file="$1"

    if command -v python3 &>/dev/null; then
        # Use python to drop just the "gpd" key; delete the file entirely if
        # nothing else remains. Exit codes:
        #   0  removed gpd entry, file still has other providers
        #   1  removed gpd entry, file was empty afterwards (deleted)
        #   2  no gpd entry present, nothing to do
        #   3  JSON parse error — caller should fall back
        python3 - "$file" <<'PY'
import json, os, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(3)
if not isinstance(data, dict) or "gpd" not in data:
    sys.exit(2)
del data["gpd"]
if not data:
    os.remove(path)
    sys.exit(1)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
os.chmod(path, 0o600)
sys.exit(0)
PY
        local rc=$?
        case "$rc" in
            0) success "Removed 'gpd' entry from $file (other providers preserved)" ;;
            1) success "Removed $file (only contained 'gpd' entry)" ;;
            2) skip "No 'gpd' entry in $file" ;;
            3)
                warn "Could not parse $file as JSON — removing it entirely"
                rm -f "$file"
                ;;
        esac
    else
        # No python3 available. We detected a "gpd" entry, but we can't safely
        # edit JSON with pure bash. If the file contains other provider keys,
        # warn before removing. Otherwise just remove it.
        local other_providers
        # crude: count top-level quoted keys other than "gpd"
        other_providers=$(grep -oE '"[A-Za-z0-9_-]+"[[:space:]]*:' "$file" 2>/dev/null \
            | grep -v '^"gpd"' | head -1 || true)
        if [[ -n "$other_providers" ]]; then
            warn "python3 not available and $file has other providers — removing whole file anyway"
            warn "  You may need to re-authenticate other providers in opencode"
        fi
        rm -f "$file"
        success "Removed $file"
    fi
}

if (( ${#auth_json_files[@]} > 0 )); then
    for f in "${auth_json_files[@]}"; do
        remove_gpd_from_auth_json "$f"
    done
else
    skip "No auth.json with 'gpd' entry to clean up"
fi

# ── Remove GUI config directories ─────────────────────────────────────────

if (( ${#gui_dirs_found[@]} > 0 )); then
    for d in "${gui_dirs_found[@]}"; do
        rm -rf "$d"
        success "Removed GUI config directory: $d"
    done
else
    skip "No GUI config directories to remove"
fi

# ── Clean GPD bits from opencode's global config (preserve the dir) ───────

clean_opencode_json() {
    local file="$1"

    if command -v python3 &>/dev/null; then
        python3 - "$file" <<'PY'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    sys.exit(3)
if not isinstance(data, dict):
    sys.exit(2)
changed = False
# Drop the "gpd" provider entry
provider = data.get("provider")
if isinstance(provider, dict) and "gpd" in provider:
    del provider["gpd"]
    changed = True
    if not provider:
        del data["provider"]
# Clear default model if it points at gpd/*
model = data.get("model")
if isinstance(model, str) and model.startswith("gpd/"):
    del data["model"]
    changed = True
# Remove "gpd" from enabled_providers (or drop the key if empty)
enabled = data.get("enabled_providers")
if isinstance(enabled, list) and "gpd" in enabled:
    data["enabled_providers"] = [p for p in enabled if p != "gpd"]
    changed = True
    if not data["enabled_providers"]:
        del data["enabled_providers"]
if not changed:
    sys.exit(2)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
sys.exit(0)
PY
        local rc=$?
        case "$rc" in
            0) success "Cleaned GPD entries from $file (opencode config preserved)" ;;
            2) skip "No GPD entries to clean from $file" ;;
            3) warn "Could not parse $file as JSON — leaving it alone" ;;
        esac
    else
        warn "python3 not available — cannot safely edit $file"
        warn "  Please manually remove \"gpd\" entries from $file"
    fi
}

if [[ "$opencode_json_has_gpd" == true ]]; then
    clean_opencode_json "$opencode_config_dir/opencode.json"
else
    skip "No GPD entries in opencode's global config"
fi

if [[ -n "$opencode_manifest" ]]; then
    rm -f "$opencode_manifest"
    success "Removed $opencode_manifest"
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
printf " ${BOLD}Note:${RESET} the following system packages were ${BOLD}not${RESET} removed,\n"
printf " since other applications on your machine may depend on them:\n"
printf "   ${DIM}- LaTeX tools: texlive-latex-base, texlive-binaries, latexmk${RESET}\n"
printf "   ${DIM}- git${RESET}\n"
printf " If you want to remove LaTeX, run:\n"
printf "   ${BOLD}sudo apt remove texlive-latex-base texlive-binaries latexmk${RESET}\n"
printf "\n"
