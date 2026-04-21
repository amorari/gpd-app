#!/usr/bin/env bash
# GPD — Get Physics Done: macOS uninstaller
#
# Usage:
#   bash uninstall_macos.sh
#   bash uninstall_macos.sh --yes    # skip confirmation prompt
#
# Removes everything created by the GPD installer on macOS:
#   - ~/.gpd/ directory (bin, config, python, venv)
#   - PATH entries from shell rc files
#   - GPD_API_KEY exports from login profiles (~/.zprofile, ~/.profile)
#   - "gpd" entry from ~/Library/Application Support/opencode/auth.json
#   - /Applications/GPD.app (desktop app)
#   - ~/Library/Application Support/GPD/
#   - ~/Library/Application Support/inc.psi.gpd/
#   - ~/Library/Application Support/opencode/ (global opencode config)
#
# Does NOT remove:
#   - BasicTeX / MacTeX (detected and reported for manual cleanup)
#   - Homebrew itself
#   - Xcode Command Line Tools

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
            printf "Usage: uninstall_macos.sh [--yes]\n"
            printf "  --yes, -y   Skip confirmation prompt\n"
            exit 0
            ;;
        *) shift ;;
    esac
done

# ── Configuration ─────────────────────────────────────────────────────────

GPD_HOME="${GPD_HOME:-$HOME/.gpd}"
GPD_BIN_DIR="$GPD_HOME/bin"
APP_SUPPORT="$HOME/Library/Application Support"
# opencode uses xdg-basedir v5, which ignores platform and always resolves
# xdgData to $HOME/.local/share — so on macOS the real auth.json lives
# there, NOT in Application Support/opencode. The installer writes to
# $XDG_DATA_HOME or $HOME/.local/share to match.
XDG_DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
OPENCODE_AUTH="$XDG_DATA/opencode/auth.json"
OPENCODE_DIR="$XDG_DATA/opencode"
GPD_APP_SUPPORT="$APP_SUPPORT/GPD"
GPD_APP_SUPPORT_BUNDLE="$APP_SUPPORT/inc.psi.gpd"
GPD_APP="/Applications/GPD.app"

# Tauri WebView data on macOS — stores localStorage (including the
# "gpd.key.saved" flag the welcome screen keys off of), cookies,
# WebKit cache, and IndexedDB. Wiping these ensures a reinstall
# doesn't inherit the previous install's "already-onboarded" signal.
GPD_CACHES_BUNDLE="$HOME/Library/Caches/inc.psi.gpd"
GPD_WEBKIT_BUNDLE="$HOME/Library/WebKit/inc.psi.gpd"

# opencode also honors XDG_* env vars on macOS for anyone who sets them
# explicitly (Linux conventions on a Mac). We clean up those fallback
# paths too so a macOS user with XDG_STATE_HOME set doesn't end up with
# orphaned session state after uninstall.
opencode_extra_dirs=()
[[ -n "${XDG_STATE_HOME:-}" ]] && opencode_extra_dirs+=("$XDG_STATE_HOME/opencode")
[[ -n "${XDG_CACHE_HOME:-}" ]] && opencode_extra_dirs+=("$XDG_CACHE_HOME/opencode")
# Legacy path: previous installer versions wrote auth.json under
# ~/Library/Application Support/opencode. Clean that up too.
opencode_extra_dirs+=("$APP_SUPPORT/opencode")
opencode_extra_dirs+=("$HOME/.local/state/opencode")
opencode_extra_dirs+=("$HOME/.cache/opencode")

# Prefer the GPD-managed Python over the system `python3` stub. On a fresh
# macOS without Xcode Command Line Tools, `/usr/bin/python3` is a stub that
# pops a GUI "install developer tools" dialog when invoked — even from an
# SSH session — which is poor UX for an uninstaller. The installer always
# creates a venv at $GPD_VENV_DIR/bin/python, so we can reach for that
# first and fall back to the system python only if the venv is gone.
PY=""
if [[ -x "$GPD_HOME/venv/bin/python" ]]; then
    PY="$GPD_HOME/venv/bin/python"
elif [[ -x "$GPD_HOME/python/bin/python3" ]]; then
    PY="$GPD_HOME/python/bin/python3"
elif command -v python3 &>/dev/null && python3 -c '' &>/dev/null; then
    PY="$(command -v python3)"
fi

# ── Discovery: show what will be removed ──────────────────────────────────

printf "\n"
printf "${BOLD} GPD Uninstaller (macOS)${RESET}\n"
printf "\n"

found_anything=false

if [[ -d "$GPD_HOME" ]]; then
    log "Found GPD directory: $GPD_HOME"
    found_anything=true
fi

# Check for /Applications/GPD.app
remove_gpd_app=false
if [[ -d "$GPD_APP" ]]; then
    log "Found GPD desktop app: $GPD_APP"
    remove_gpd_app=true
    found_anything=true
fi

# Check for GUI config directories
remove_gpd_app_support=false
if [[ -d "$GPD_APP_SUPPORT" ]]; then
    log "Found GPD app support dir: $GPD_APP_SUPPORT"
    remove_gpd_app_support=true
    found_anything=true
fi

remove_gpd_bundle_support=false
if [[ -d "$GPD_APP_SUPPORT_BUNDLE" ]]; then
    log "Found GPD bundle support dir: $GPD_APP_SUPPORT_BUNDLE"
    remove_gpd_bundle_support=true
    found_anything=true
fi

# Tauri WebView data (localStorage, cookies, WebKit cache, IndexedDB).
# These are NOT in Application Support — macOS puts them under Caches
# and WebKit. Without clearing them, a fresh install inherits the
# previous run's "already-onboarded" localStorage flag and the GUI
# welcome screen never shows.
remove_caches_bundle=false
if [[ -d "$GPD_CACHES_BUNDLE" ]]; then
    log "Found GPD WebView cache: $GPD_CACHES_BUNDLE"
    remove_caches_bundle=true
    found_anything=true
fi

remove_webkit_bundle=false
if [[ -d "$GPD_WEBKIT_BUNDLE" ]]; then
    log "Found GPD WebKit data: $GPD_WEBKIT_BUNDLE"
    remove_webkit_bundle=true
    found_anything=true
fi

# Check for opencode global config dir
remove_opencode_dir=false
if [[ -d "$OPENCODE_DIR" ]]; then
    log "Found opencode config dir: $OPENCODE_DIR"
    remove_opencode_dir=true
    found_anything=true
fi

# XDG fallback paths — any of these exist on a macOS box with a
# Linux-style env would be orphaned without explicit cleanup.
opencode_extra_dirs_found=()
for d in "${opencode_extra_dirs[@]}"; do
    if [[ -d "$d" ]]; then
        opencode_extra_dirs_found+=("$d")
        log "Found opencode XDG dir: $d"
        found_anything=true
    fi
done

# Check for auth.json with a "gpd" entry, and pre-compute whether it has
# any non-gpd providers. Both checks happen here — before we remove
# $GPD_HOME (and with it the venv Python we rely on). Caching the result
# avoids calling python3 after the venv is gone.
strip_auth_gpd=false
auth_has_other_providers=false
if [[ -f "$OPENCODE_AUTH" && -n "$PY" ]]; then
    if "$PY" -c "
import json, sys
try:
    with open('$OPENCODE_AUTH') as f:
        data = json.load(f)
    sys.exit(0 if isinstance(data, dict) and 'gpd' in data else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        log "Found 'gpd' entry in $OPENCODE_AUTH"
        strip_auth_gpd=true
        found_anything=true
    fi
    if "$PY" -c "
import json, sys
try:
    with open('$OPENCODE_AUTH') as f:
        data = json.load(f)
    others = [k for k in data if k != 'gpd'] if isinstance(data, dict) else []
    sys.exit(0 if others else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        auth_has_other_providers=true
    fi
elif [[ -f "$OPENCODE_AUTH" ]] && grep -q '"gpd"' "$OPENCODE_AUTH" 2>/dev/null; then
    # Fallback when no usable python3 is available: crude grep. Good enough
    # for the common case where the installer wrote the auth entry itself.
    log "Found 'gpd' entry in $OPENCODE_AUTH"
    strip_auth_gpd=true
    found_anything=true
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

# Check login profiles for GPD_API_KEY (macOS: zprofile is the primary location)
profiles_with_key=()
for profile in "$HOME/.zprofile" "$HOME/.profile" "$HOME/.bash_profile" "${ZDOTDIR:-$HOME}/.zprofile"; do
    # Avoid duplicates
    [[ " ${profiles_with_key[*]:-} " == *" $profile "* ]] && continue
    if [[ -f "$profile" ]] && grep -q "GPD_API_KEY" "$profile" 2>/dev/null; then
        profiles_with_key+=("$profile")
        log "Found GPD_API_KEY export in: $profile"
        found_anything=true
    fi
done

# Detect LaTeX (BasicTeX / MacTeX) — do NOT remove, just report
latex_detected=false
latex_note=""
if command -v brew &>/dev/null; then
    if brew list --cask 2>/dev/null | grep -qx "basictex"; then
        latex_detected=true
        latex_note="BasicTeX (Homebrew cask)"
    elif brew list --cask 2>/dev/null | grep -qx "mactex"; then
        latex_detected=true
        latex_note="MacTeX (Homebrew cask)"
    elif brew list --cask 2>/dev/null | grep -qx "mactex-no-gui"; then
        latex_detected=true
        latex_note="MacTeX-no-GUI (Homebrew cask)"
    fi
fi
if [[ "$latex_detected" == false ]]; then
    if [[ -d "/Library/TeX" ]] || compgen -G "/usr/local/texlive/*" > /dev/null 2>&1; then
        latex_detected=true
        latex_note="TeX installation at /Library/TeX or /usr/local/texlive/"
    fi
fi

if [[ "$found_anything" == false ]]; then
    printf " ${DIM}Nothing to remove — GPD does not appear to be installed.${RESET}\n\n"
    if [[ "$latex_detected" == true ]]; then
        printf " ${DIM}Note: $latex_note is installed but will not be touched.${RESET}\n\n"
    fi
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

# ── Remove /Applications/GPD.app ─────────────────────────────────────────

if [[ "$remove_gpd_app" == true ]]; then
    log "Removing $GPD_APP..."
    # May require sudo if the app is owned by root (e.g. installed via .pkg)
    if rm -rf "$GPD_APP" 2>/dev/null; then
        success "Removed $GPD_APP"
    elif sudo rm -rf "$GPD_APP" 2>/dev/null; then
        success "Removed $GPD_APP (with sudo)"
    else
        warn "Failed to remove $GPD_APP (try: sudo rm -rf '$GPD_APP')"
    fi
else
    skip "No /Applications/GPD.app installed"
fi

# ── Strip 'gpd' entry from opencode auth.json ────────────────────────────

if [[ "$strip_auth_gpd" == true && -n "$PY" ]]; then
    if "$PY" - "$OPENCODE_AUTH" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and 'gpd' in data:
        del data['gpd']
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')
        sys.exit(0)
    sys.exit(2)
except Exception as e:
    sys.stderr.write(str(e) + '\n')
    sys.exit(1)
PYEOF
    then
        success "Removed 'gpd' entry from $OPENCODE_AUTH"
    else
        warn "Failed to strip 'gpd' entry from $OPENCODE_AUTH"
    fi
elif [[ "$strip_auth_gpd" == true ]]; then
    # No usable python3 — auth.json is going to be removed with the
    # opencode dir anyway, so just note it and move on.
    warn "No python3 available to surgically strip 'gpd' from auth.json; will remove the whole opencode dir below"
else
    skip "No 'gpd' entry in opencode auth.json"
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

# ── Remove GUI config directories ────────────────────────────────────────

if [[ "$remove_gpd_app_support" == true ]]; then
    rm -rf "$GPD_APP_SUPPORT"
    success "Removed $GPD_APP_SUPPORT"
else
    skip "No $GPD_APP_SUPPORT to remove"
fi

if [[ "$remove_gpd_bundle_support" == true ]]; then
    rm -rf "$GPD_APP_SUPPORT_BUNDLE"
    success "Removed $GPD_APP_SUPPORT_BUNDLE"
else
    skip "No $GPD_APP_SUPPORT_BUNDLE to remove"
fi

if [[ "$remove_caches_bundle" == true ]]; then
    rm -rf "$GPD_CACHES_BUNDLE"
    success "Removed $GPD_CACHES_BUNDLE"
else
    skip "No $GPD_CACHES_BUNDLE to remove"
fi

if [[ "$remove_webkit_bundle" == true ]]; then
    rm -rf "$GPD_WEBKIT_BUNDLE"
    success "Removed $GPD_WEBKIT_BUNDLE"
else
    skip "No $GPD_WEBKIT_BUNDLE to remove"
fi

# ── Remove opencode global config directory ──────────────────────────────
# Note: only remove if it still exists after stripping the gpd auth entry.
# If the user wants to keep other providers' auth, they should edit auth.json
# manually instead of running the uninstaller — we remove the whole dir here
# because the installer created it.

if [[ "$remove_opencode_dir" == true ]] && [[ -d "$OPENCODE_DIR" ]]; then
    # If auth.json still has other providers (not just gpd), preserve the
    # directory. This check was performed during discovery while the venv
    # Python was still available — we use the cached result here to avoid
    # invoking the `/usr/bin/python3` stub after the venv was removed.
    preserve_opencode=false
    if [[ "$auth_has_other_providers" == true ]]; then
        preserve_opencode=true
    fi

    if [[ "$preserve_opencode" == true ]]; then
        skip "Keeping $OPENCODE_DIR (auth.json has other providers)"
    else
        rm -rf "$OPENCODE_DIR"
        success "Removed $OPENCODE_DIR"
    fi
else
    skip "No $OPENCODE_DIR to remove"
fi

# Clean up any XDG-style opencode dirs (only when we're removing the
# main opencode dir — same "opencode only exists for GPD" heuristic).
if [[ "${preserve_opencode:-false}" != true ]] && (( ${#opencode_extra_dirs_found[@]} > 0 )); then
    for d in "${opencode_extra_dirs_found[@]}"; do
        rm -rf "$d"
        success "Removed $d"
    done
fi

# ── Done ──────────────────────────────────────────────────────────────────

printf "\n"
printf " ${GREEN}${BOLD}GPD has been uninstalled.${RESET}\n"
printf " ${DIM}Open a new terminal to clear any cached PATH entries.${RESET}\n"

if [[ "$latex_detected" == true ]]; then
    printf "\n"
    printf " ${YELLOW}Manual cleanup:${RESET} $latex_note was installed by the GPD installer\n"
    printf " but is left in place because many other apps may depend on it.\n"
    printf " To remove it yourself:\n"
    printf "   ${DIM}brew uninstall --cask basictex${RESET}   ${DIM}# or mactex / mactex-no-gui${RESET}\n"
fi

printf "\n"
