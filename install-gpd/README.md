# GPD CLI Installers

Platform-specific installers that set up the complete GPD terminal environment from scratch. No prerequisites required — each installer handles everything.

## Quick Start

### Unified installer (Ubuntu + macOS)

```bash
curl -fsSL https://download.gpd.psi.inc/install | bash
```

Or run locally:

```bash
bash install
```

Options: `--skip-key` (skip LiteLLM prompt), `--no-modify-path`, `--version 1.0.180`.

### Platform-specific installers

```bash
# Ubuntu 24.04+ (installs .deb desktop app if available)
bash ubuntu_24_04/install.sh

# macOS (Tahoe / Apple Silicon + Intel)
bash macos_26_tahoe/install.sh
```

### Windows 11

```powershell
powershell -ExecutionPolicy Bypass -File windows_11\install.ps1
```

## What Gets Installed

All files are installed to `~/.gpd/` (or `$HOME\.gpd\` on Windows):

```
~/.gpd/
├── bin/
│   ├── opencode      # OpenCode CLI binary
│   └── gpd           # Wrapper script (+ gpd.cmd on Windows)
├── python/           # App-local Python 3.13 (only if system Python < 3.11)
├── venv/             # Python venv with get-physics-done package
└── config/
    └── litellm.env   # LiteLLM API key (user-only permissions)
```

## Prerequisites

- **Ubuntu**: `curl`, `tar`, `git` (installer will `apt-get install` if missing)
- **macOS**: `curl`, `unzip`, `tar` (ships with macOS; install Xcode CLT if missing)
- **Windows**: PowerShell 5.1+, internet access

No Python required -- the installer downloads a standalone build if system Python < 3.11.

## Installation Steps

Each installer performs these steps:

1. **OpenCode CLI** -- Downloads the binary from GitHub releases (tries GPD fork first, falls back to upstream)
2. **Python 3.11+** -- Checks for system Python; if missing or too old, downloads a portable build from [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
3. **GPD package** -- Creates a Python venv and installs `get-physics-done` from GitHub
4. **LiteLLM key** -- Prompts for your virtual key (get it from your lab administrator)
5. **`gpd` command** -- Creates a wrapper script that launches OpenCode with GPD configuration
6. **PATH** -- Adds `~/.gpd/bin` to your shell PATH
7. **GPD runtime** -- Configures OpenCode with GPD settings (`gpd install opencode --global`)

## Configuration

### LiteLLM Key

The installer prompts for your key during setup. To change it later:

```bash
# Edit the config file directly
nano ~/.gpd/config/litellm.env
```

The file contains:
```
LITELLM_API_KEY=sk-your-key-here
LITELLM_API_BASE=https://litellm-production-46bb.up.railway.app
```

### Custom Install Location

Set `GPD_HOME` before running the installer:

```bash
GPD_HOME=/opt/gpd bash install/ubuntu_24_04/install.sh
```

## Re-running the Installer

Installers are idempotent — they skip steps that are already complete. Safe to re-run after updates or if a step failed.

## Uninstalling

```bash
bash uninstall.sh
```

The uninstall script removes everything the installer created:

- `~/.gpd/` directory (bin, config, python, venv)
- PATH entries from `~/.bashrc`, `~/.zshrc`, `~/.profile`
- `GPD_API_KEY` exports from `~/.profile` / `~/.zprofile`
- GPD `.deb` package on Ubuntu (if installed)

Pass `--yes` to skip the confirmation prompt.

On Windows (manual):
```powershell
Remove-Item -Recurse -Force "$HOME\.gpd"
# Remove from PATH via System > Environment Variables > User PATH
```

## File Structure

```
install-gpd/
├── install                       # Unified installer (Ubuntu + macOS)
├── uninstall.sh                  # Uninstaller (all platforms except Windows)
├── common.sh                     # Shared bash functions (Ubuntu + macOS)
├── ubuntu_24_04/
│   └── install.sh                # Ubuntu installer (adds .deb support)
├── macos_26_tahoe/
│   └── install.sh                # macOS installer
└── windows_11/
    └── install.ps1               # Windows PowerShell installer
```

`install` is a self-contained unified installer (no dependency on `common.sh`) suitable for piping from curl. The platform-specific scripts source `common.sh` and add OS-specific setup. The Windows installer is standalone PowerShell.

## Troubleshooting

### "Neither curl nor wget found"
Install curl: `sudo apt-get install curl` (Ubuntu) or install Xcode Command Line Tools (macOS).

### "Python extraction failed"
The python-build-standalone download may have failed. Check your network and retry. The installer uses Python 3.13.3 from [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone).

### "Could not find OpenCode CLI binary"
The installer tries to download from GitHub releases. Check that you have network access to github.com.

### "gpd: command not found" after install
Open a new terminal, or run `source ~/.bashrc` (or `source ~/.zshrc` on macOS).

### Re-configuring LiteLLM key
Edit `~/.gpd/config/litellm.env` directly, or delete it and re-run the installer.

## Future: GUI Installers

GUI installers (.pkg for macOS, Inno Setup .exe for Windows, .deb for Ubuntu) are planned for a future version. They will wrap the same installation logic in native platform installer wizards.
