#!/usr/bin/env bash
# Shared installer functions for GPD CLI.
# Sourced by platform-specific installers — not meant to be run directly.
#
#   install.sh (ubuntu/macos)
#     └── sources common.sh
#           ├── install_opencode()    ← download CLI binary
#           ├── ensure_python()       ← check system or download standalone
#           ├── create_venv()         ← ~/.gpd/venv
#           ├── install_gpd()         ← pip install get-physics-done
#           ├── prompt_litellm_key()  ← interactive key entry
#           ├── create_gpd_wrapper()  ← ~/.gpd/bin/gpd
#           ├── add_to_path()         ← append to shell rc
#           └── run_install()         ← orchestrates all steps

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────

GPD_HOME="${GPD_HOME:-$HOME/.gpd}"
GPD_BIN_DIR="$GPD_HOME/bin"
GPD_PYTHON_DIR="$GPD_HOME/python"
GPD_VENV_DIR="$GPD_HOME/venv"
GPD_CONFIG_DIR="$GPD_HOME/config"

OPENCODE_ORG="psi-oss"
OPENCODE_REPO="opencode"
OPENCODE_FALLBACK_ORG="anomalyco"
OPENCODE_FALLBACK_REPO="opencode"

GPD_PACKAGE_REPO="psi-oss/get-physics-done"
GPD_PACKAGE_BRANCH="main"

LITELLM_PROXY_URL="https://litellm-production-46bb.up.railway.app"

# Python-build-standalone: portable, relocatable CPython builds from Astral.
# Update these when newer builds are available.
PBS_TAG="20250409"
PBS_PYTHON="3.13.3"
PBS_BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG"

REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=11

# ── Colors ─────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

# ── Logging ────────────────────────────────────────────────────────────────

log()     { printf " ${CYAN}i${RESET} %s\n" "$*"; }
success() { printf " ${GREEN}✓${RESET} %s\n" "$*"; }
warn()    { printf " ${YELLOW}⚠${RESET} %s\n" "$*"; }
error()   { printf " ${RED}✗${RESET} %s\n" "$*" >&2; }
die()     { error "$@"; exit 1; }

# ── Banner ─────────────────────────────────────────────────────────────────

print_banner() {
    printf "\n"
    printf "${CYAN} ██████╗ ██████╗ ██████╗${RESET}\n"
    printf "${CYAN}██╔════╝ ██╔══██╗██╔══██╗${RESET}\n"
    printf "${CYAN}██║  ███╗██████╔╝██║  ██║${RESET}\n"
    printf "${CYAN}██║   ██║██╔═══╝ ██║  ██║${RESET}\n"
    printf "${CYAN}╚██████╔╝██║     ██████╔╝${RESET}\n"
    printf "${CYAN} ╚═════╝ ╚═╝     ╚═════╝${RESET}\n"
    printf "\n"
    printf " ${BOLD}Get Physics Done${RESET} ${DIM}— CLI Installer${RESET}\n"
    printf " Open-source AI copilot for physics research\n"
    printf "\n"
}

print_success_banner() {
    printf "\n"
    success "GPD installed successfully!"
    printf "\n"
    printf "  Start a new session:  ${BOLD}gpd${RESET}\n"
    printf "  Show help:            ${BOLD}gpd --help${RESET}\n"
    printf "\n"
    printf "  ${DIM}Installation directory: %s${RESET}\n" "$GPD_HOME"
    printf "\n"
    warn "Open a new terminal (or run 'source ~/.bashrc' / 'source ~/.zshrc') to use the gpd command."
    printf "\n"
}

# ── Utilities ──────────────────────────────────────────────────────────────

command_exists() { command -v "$1" &>/dev/null; }

detect_arch() {
    local arch
    arch="$(uname -m)"
    case "$arch" in
        x86_64|amd64)   echo "x64" ;;
        aarch64|arm64)   echo "arm64" ;;
        *)               die "Unsupported architecture: $arch" ;;
    esac
}

download() {
    local url="$1" dest="$2"
    log "Downloading $(basename "$dest")..."
    if command_exists curl; then
        curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url"
    elif command_exists wget; then
        wget -q --tries=3 -O "$dest" "$url"
    else
        die "Neither curl nor wget found. Install one and retry."
    fi
}

# Probe a URL with HTTP HEAD — returns 0 if 2xx/3xx, 1 otherwise.
url_exists() {
    local url="$1"
    if command_exists curl; then
        curl -fsSL --head --retry 1 --max-time 10 -o /dev/null "$url" 2>/dev/null
    elif command_exists wget; then
        wget --spider -q --timeout=10 "$url" 2>/dev/null
    else
        return 1
    fi
}

# ── OpenCode CLI ───────────────────────────────────────────────────────────

opencode_asset_name() {
    local os="$1" arch="$2"
    case "$os" in
        linux)  echo "opencode-linux-${arch}.tar.gz" ;;
        darwin) echo "opencode-darwin-${arch}.zip" ;;
        *)      die "Unsupported OS for OpenCode: $os" ;;
    esac
}

install_opencode() {
    local os="$1" arch="$2"
    local dest="$GPD_BIN_DIR/opencode"

    if [[ -x "$dest" ]]; then
        success "OpenCode CLI already installed at $dest"
        return 0
    fi

    local asset
    asset="$(opencode_asset_name "$os" "$arch")"
    local gpd_url="https://github.com/${OPENCODE_ORG}/${OPENCODE_REPO}/releases/latest/download/${asset}"
    local fallback_url="https://github.com/${OPENCODE_FALLBACK_ORG}/${OPENCODE_FALLBACK_REPO}/releases/latest/download/${asset}"

    local url=""
    log "Checking for GPD-branded OpenCode CLI release..."
    if url_exists "$gpd_url"; then
        url="$gpd_url"
        log "Found GPD release"
    else
        log "GPD CLI release not found, using upstream OpenCode"
        if url_exists "$fallback_url"; then
            url="$fallback_url"
        else
            die "Could not find OpenCode CLI binary for ${os}/${arch}. Check network connectivity."
        fi
    fi

    local tmp_dir
    tmp_dir="$(mktemp -d)"

    # Download and extract in a block with guaranteed cleanup
    local binary=""
    {
        local archive="$tmp_dir/$asset"
        download "$url" "$archive"

        log "Extracting OpenCode CLI..."
        case "$asset" in
            *.tar.gz) tar -xzf "$archive" -C "$tmp_dir" ;;
            *.zip)    unzip -qo "$archive" -d "$tmp_dir" ;;
        esac

        binary="$(find "$tmp_dir" -name 'opencode' -type f -not -path "$archive" | head -1)"
    }

    if [[ -z "$binary" ]]; then
        rm -rf "$tmp_dir"
        die "Could not find opencode binary in downloaded archive"
    fi

    mv "$binary" "$dest"
    chmod +x "$dest"
    rm -rf "$tmp_dir"

    success "OpenCode CLI installed to $dest"
}

# ── Python ─────────────────────────────────────────────────────────────────

python_version_ok() {
    local python="$1"
    local version_output
    version_output="$("$python" --version 2>&1)" || return 1
    local ver_string major minor
    ver_string="$(echo "$version_output" | grep -oE '[0-9]+\.[0-9]+' | head -1)"
    major="${ver_string%%.*}"
    minor="${ver_string##*.}"
    [[ -n "$major" && -n "$minor" ]] || return 1
    (( major > REQUIRED_PYTHON_MAJOR || (major == REQUIRED_PYTHON_MAJOR && minor >= REQUIRED_PYTHON_MINOR) ))
}

find_system_python() {
    for cmd in python3 python; do
        if command_exists "$cmd" && python_version_ok "$cmd"; then
            command -v "$cmd"
            return 0
        fi
    done
    return 1
}

pbs_triple() {
    local os="$1" arch="$2"
    case "${os}_${arch}" in
        linux_x64)   echo "x86_64-unknown-linux-gnu" ;;
        linux_arm64)  echo "aarch64-unknown-linux-gnu" ;;
        darwin_x64)   echo "x86_64-apple-darwin" ;;
        darwin_arm64)  echo "aarch64-apple-darwin" ;;
        *)            die "No python-build-standalone build for ${os}/${arch}" ;;
    esac
}

install_local_python() {
    local os="$1" arch="$2"
    local python_bin="$GPD_PYTHON_DIR/bin/python3"

    if [[ -x "$python_bin" ]] && python_version_ok "$python_bin"; then
        success "App-local Python already installed at $GPD_PYTHON_DIR" >&2
        echo "$python_bin"
        return 0
    fi

    local triple
    triple="$(pbs_triple "$os" "$arch")"
    local filename="cpython-${PBS_PYTHON}+${PBS_TAG}-${triple}-install_only.tar.gz"
    local url="${PBS_BASE_URL}/${filename}"

    log "Downloading Python ${PBS_PYTHON} (app-local, not system-wide)..." >&2
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    local archive="$tmp_dir/$filename"

    download "$url" "$archive" >&2

    log "Extracting Python to $GPD_PYTHON_DIR..." >&2
    rm -rf "$GPD_PYTHON_DIR"
    mkdir -p "$GPD_PYTHON_DIR"
    tar -xzf "$archive" -C "$GPD_PYTHON_DIR" --strip-components=1

    rm -rf "$tmp_dir"

    if [[ ! -x "$python_bin" ]]; then
        die "Python extraction failed — $python_bin not found"
    fi

    success "Python ${PBS_PYTHON} installed to $GPD_PYTHON_DIR" >&2
    echo "$python_bin"
}

ensure_python() {
    local os="$1" arch="$2"

    # Prefer app-local Python if already installed
    local local_python="$GPD_PYTHON_DIR/bin/python3"
    if [[ -x "$local_python" ]] && python_version_ok "$local_python"; then
        success "Using app-local Python at $local_python" >&2
        echo "$local_python"
        return 0
    fi

    # Check system Python
    local sys_python
    if sys_python="$(find_system_python)"; then
        local ver
        ver="$("$sys_python" --version 2>&1)"
        success "Found system $ver" >&2
        echo "$sys_python"
        return 0
    fi

    # Download standalone Python
    log "No Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ found — installing app-local Python" >&2
    install_local_python "$os" "$arch"
}

# ── Venv & GPD package ─────────────────────────────────────────────────────

create_venv() {
    local python="$1"

    if [[ -f "$GPD_VENV_DIR/bin/python" ]] || [[ -f "$GPD_VENV_DIR/bin/python3" ]]; then
        success "Python venv already exists at $GPD_VENV_DIR"
        return 0
    fi

    log "Creating Python virtual environment..."
    "$python" -m venv "$GPD_VENV_DIR"
    success "Virtual environment created at $GPD_VENV_DIR"
}

install_gpd() {
    local venv_pip="$GPD_VENV_DIR/bin/pip"
    local venv_python="$GPD_VENV_DIR/bin/python"

    # Upgrade pip first
    "$venv_python" -m pip install --upgrade --quiet pip

    local source_url="https://github.com/${GPD_PACKAGE_REPO}/archive/refs/heads/${GPD_PACKAGE_BRANCH}.tar.gz"

    log "Installing get-physics-done from GitHub..."
    "$venv_pip" install --upgrade --quiet "$source_url"

    if [[ -x "$GPD_VENV_DIR/bin/gpd" ]]; then
        success "GPD package installed"
    else
        die "GPD package installation failed — gpd command not found in venv"
    fi
}

# ── LiteLLM key ────────────────────────────────────────────────────────────

prompt_litellm_key() {
    local env_file="$GPD_CONFIG_DIR/litellm.env"

    if [[ -f "$env_file" ]]; then
        success "LiteLLM configuration already exists at $env_file"
        return 0
    fi

    printf "\n"
    printf " ${BOLD}LiteLLM API Key Configuration${RESET}\n"
    printf " ${DIM}Your LiteLLM virtual key connects GPD to AI models.${RESET}\n"
    printf " ${DIM}Get your key from your lab administrator.${RESET}\n"
    printf "\n"

    local key="${GPD_API_KEY:-}"
    if [[ -z "$key" ]]; then
        if [[ ! -t 0 ]]; then
            warn "No terminal and GPD_API_KEY not set — skipping key configuration."
            warn "Set GPD_API_KEY and re-run, or run interactively to be prompted."
            return 0
        fi
        while [[ -z "$key" ]]; do
            printf " Enter your LiteLLM key (sk-...): "
            read -r key
            if [[ -z "$key" ]]; then
                warn "Key cannot be empty. Press Ctrl+C to skip and configure later."
            fi
        done
    fi

    # Write with restrictive umask to avoid race where file is briefly world-readable
    ( umask 077; cat > "$env_file" <<EOF
# GPD configuration — used by CLI wrapper and sourced into desktop app session
GPD_API_KEY=${key}
LITELLM_API_BASE=${LITELLM_PROXY_URL}
EOF
    )

    # Export GPD_API_KEY in login profile so the desktop app inherits it
    local profile="$HOME/.profile"
    [[ "$(basename "${SHELL:-bash}")" == "zsh" ]] && profile="${ZDOTDIR:-$HOME}/.zprofile"
    local export_line="export GPD_API_KEY=\"${key}\""
    if ! grep -qF "GPD_API_KEY" "$profile" 2>/dev/null; then
        printf '\n# GPD API key for desktop app\n%s\n' "$export_line" >> "$profile"
    fi

    success "LiteLLM key saved to $env_file"
}

# ── LaTeX ─────────────────────────────────────────────────────────────────
#
# GPD compiles physics papers, so we ensure pdflatex/bibtex/latexmk/kpsewhich
# are available. Install is optional: failure warns, doesn't abort.
#
# Called from platform-specific installers:
#   - Ubuntu: installs texlive-latex-base + latexmk via apt
#   - macOS:  installs BasicTeX via Homebrew, then `tlmgr install latexmk`

latex_installed() { command_exists pdflatex; }

install_latex() {
    local os="$1"

    if latex_installed; then
        success "LaTeX already installed ($(pdflatex --version 2>&1 | head -1))"
        return 0
    fi

    log "Installing LaTeX (this may take a few minutes — ~500MB download)..."

    case "$os" in
        linux)
            if ! command_exists apt-get; then
                warn "LaTeX auto-install only supports apt-based distros — install manually"
                return 0
            fi
            if ! sudo apt-get install -y -qq texlive-latex-base texlive-binaries latexmk 2>&1 | tail -5; then
                warn "LaTeX install failed — install manually: sudo apt install texlive-latex-base texlive-binaries latexmk"
                return 0
            fi
            ;;
        darwin)
            if ! command_exists brew; then
                warn "Homebrew not found — skipping LaTeX install."
                warn "Install Homebrew (https://brew.sh), then run: brew install --cask basictex"
                return 0
            fi
            if ! brew install --cask basictex 2>&1 | tail -5; then
                warn "BasicTeX install failed — install manually: brew install --cask basictex"
                return 0
            fi
            # BasicTeX installs to /Library/TeX/texbin (not on PATH until new shell)
            local texbin="/Library/TeX/texbin"
            if [[ -x "$texbin/tlmgr" ]]; then
                log "Installing latexmk via tlmgr..."
                sudo "$texbin/tlmgr" update --self 2>/dev/null || true
                sudo "$texbin/tlmgr" install latexmk 2>&1 | tail -3 || \
                    warn "latexmk install via tlmgr failed — run manually: sudo tlmgr install latexmk"
                export PATH="$texbin:$PATH"
            fi
            ;;
        *)
            warn "LaTeX auto-install not supported on $os — install manually"
            return 0
            ;;
    esac

    if latex_installed; then
        success "LaTeX installed"
    else
        warn "LaTeX install completed but pdflatex not on PATH yet — open a new shell"
    fi
}

# ── GPD wrapper ────────────────────────────────────────────────────────────

create_gpd_wrapper() {
    local wrapper="$GPD_BIN_DIR/gpd"

    cat > "$wrapper" <<'WRAPPER'
#!/usr/bin/env bash
# GPD CLI wrapper — launches OpenCode with GPD configuration.
GPD_HOME="${GPD_HOME:-$HOME/.gpd}"

# Load LiteLLM credentials
if [[ -f "$GPD_HOME/config/litellm.env" ]]; then
    set -a
    source "$GPD_HOME/config/litellm.env"
    set +a
fi

# Ensure GPD venv tools are available (MCP servers, etc.)
export PATH="$GPD_HOME/venv/bin:$GPD_HOME/bin:$PATH"

exec "$GPD_HOME/bin/opencode" "$@"
WRAPPER
    chmod +x "$wrapper"

    success "GPD wrapper created at $wrapper"
}

# ── PATH ───────────────────────────────────────────────────────────────────

path_entry() { printf 'export PATH="%s:$PATH"' "$GPD_BIN_DIR"; }

add_to_path() {
    local entry
    entry="$(path_entry)"

    # Already on PATH?
    if echo "$PATH" | tr ':' '\n' | grep -qxF "$GPD_BIN_DIR"; then
        success "$GPD_BIN_DIR is already on PATH"
        return 0
    fi

    local added=false
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [[ -f "$rc" ]]; then
            if ! grep -qF "$GPD_BIN_DIR" "$rc"; then
                printf '\n# GPD CLI\n%s\n' "$entry" >> "$rc"
                log "Added to $rc"
                added=true
            fi
        fi
    done

    # Create .bashrc entry if nothing was modified (e.g., fresh system)
    if [[ "$added" == false ]]; then
        local target="$HOME/.bashrc"
        if [[ "$(basename "${SHELL:-bash}")" == "zsh" ]]; then
            target="$HOME/.zshrc"
        fi
        printf '\n# GPD CLI\n%s\n' "$entry" >> "$target"
        log "Added to $target"
    fi

    export PATH="$GPD_BIN_DIR:$PATH"
    success "Added $GPD_BIN_DIR to PATH"
}

# ── Main install orchestrator ──────────────────────────────────────────────

run_install() {
    local os="$1" arch="$2"

    print_banner

    log "Installing GPD to $GPD_HOME"
    log "Platform: ${os}/${arch}"
    printf "\n"

    # Create directory structure
    mkdir -p "$GPD_BIN_DIR" "$GPD_PYTHON_DIR" "$GPD_VENV_DIR" "$GPD_CONFIG_DIR"

    # Step 1: OpenCode CLI binary
    log "Step 1/7: Installing OpenCode CLI..."
    install_opencode "$os" "$arch"
    printf "\n"

    # Step 2: Python
    log "Step 2/7: Ensuring Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+..."
    local python
    python="$(ensure_python "$os" "$arch")"
    printf "\n"

    # Step 3: Venv + GPD package
    log "Step 3/7: Installing GPD package..."
    create_venv "$python"
    install_gpd
    printf "\n"

    # Step 4: LaTeX tools
    log "Step 4/7: Installing LaTeX tools..."
    install_latex "$os"
    printf "\n"

    # Step 5: LiteLLM key
    log "Step 5/7: Configuring LiteLLM..."
    prompt_litellm_key
    printf "\n"

    # Step 6: Wrapper script
    log "Step 6/7: Creating gpd command..."
    create_gpd_wrapper
    printf "\n"

    # Step 7: PATH
    log "Step 7/7: Configuring PATH..."
    add_to_path
    printf "\n"

    # Run GPD install for OpenCode runtime configuration
    if [[ -x "$GPD_VENV_DIR/bin/gpd" ]]; then
        log "Configuring GPD for OpenCode runtime..."
        "$GPD_VENV_DIR/bin/gpd" install --opencode --global 2>/dev/null || \
            warn "GPD runtime configuration skipped (run 'gpd install --opencode --global' manually)"
    fi

    print_success_banner
}
