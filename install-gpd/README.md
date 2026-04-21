# GPD CLI Installers

Platform-specific installers that set up the complete GPD terminal environment from scratch. No prerequisites required — each installer handles everything.

## Quick Start

### Ubuntu / macOS (recommended)

```bash
bash <(curl -fsSL https://download.gpd.psi.inc/install)
```

This uses process substitution so interactive prompts (sudo password, PSI
key) work normally. On Ubuntu it installs the GPD desktop `.deb` (GUI +
CLI); on other Linux and macOS it installs the standalone CLI.

For fully non-interactive installs, preset the key and pipe:

```bash
curl -fsSL https://download.gpd.psi.inc/install | GPD_API_KEY=sk-... bash
```

Options: `--skip-key`, `--no-modify-path`, `--version 1.0.180`.

### Windows 11

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
irm https://download.gpd.psi.inc/install.ps1 -OutFile $env:TEMP\install.ps1
& $env:TEMP\install.ps1
```

Download-then-run (instead of `irm | iex`) keeps stdin connected to your
terminal so the PSI key prompt works. For non-interactive installs
(CI / scripted), preset the key and use the pipe form:

```powershell
$env:GPD_API_KEY = "sk-your-key"
irm https://download.gpd.psi.inc/install.ps1 | iex
```

### Local testing (developers only)

If you're editing the installer itself, test from a local clone:

```bash
bash install                              # Run local version
GPD_API_KEY=sk-test bash install          # Non-interactive
```

## What Gets Installed

All files are installed to `~/.gpd/` (or `$HOME\.gpd\` on Windows):

```
~/.gpd/
├── bin/
│   ├── opencode      # GPD runtime binary (symlinked to /usr/bin/opencode-cli on Ubuntu)
│   └── gpd           # The `gpd` command you'll use
├── python/           # App-local Python 3.13 (only if system Python < 3.11)
├── venv/             # Python venv with the GPD package
└── config/
    └── litellm.env   # PSI API key (user-only permissions)
```

On Ubuntu, GPD is also installed system-wide via `.deb`:
```
/usr/bin/GPD             # Desktop app (launched from menu)
```

## Prerequisites

- **Ubuntu**: `curl`, `tar`, `git` (installer will `apt-get install` if missing)
- **macOS**: `curl`, `unzip`, `tar` (ships with macOS; install Xcode CLT if missing)
- **Windows**: PowerShell 5.1+, internet access

No Python required -- the installer downloads a standalone build if system Python < 3.11.

## Installation Steps

Each installer performs these steps:

1. **GPD runtime** -- On Ubuntu, installs the GPD desktop `.deb` (GUI + CLI). Elsewhere, downloads the standalone CLI.
2. **Python 3.11+** -- Checks for system Python; if missing or too old, downloads a portable build from [python-build-standalone](https://github.com/astral-sh/python-build-standalone)
3. **GPD package** -- Creates a Python venv and installs `get-physics-done`
4. **LaTeX tools** -- Installs pdflatex, bibtex, latexmk, kpsewhich for physics paper compilation (via apt on Linux, BasicTeX on macOS, MiKTeX on Windows). Warns and skips if the platform package manager is unavailable.
5. **PSI key** -- Prompts for your virtual key (get it from your lab administrator), or reads `GPD_API_KEY` env var for non-interactive installs
6. **`gpd` command** -- Creates the `gpd` launcher
7. **PATH** -- Adds `~/.gpd/bin` to your shell PATH
8. **Runtime config** -- Installs 24 agents and 69 commands into your global config

## Configuration

### PSI Key

The installer prompts for your key during setup. To change it later:

```bash
# Edit the config file directly
nano ~/.gpd/config/litellm.env
```

The file contains:
```
GPD_API_KEY=sk-your-key-here
LITELLM_API_BASE=https://litellm-production-46bb.up.railway.app
```

### Custom Install Location

Set `GPD_HOME` before running the installer:

```bash
GPD_HOME=/opt/gpd bash install
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
├── install                       # Unified installer (Ubuntu + macOS + other Linux)
├── uninstall.sh                  # Uninstaller (Linux + macOS)
└── windows_11/
    └── install.ps1               # Windows PowerShell installer
```

`install` is a self-contained script suitable for piping from curl. It detects
the platform at runtime, installs the GPD desktop `.deb` on Debian/Ubuntu (or
the standalone CLI elsewhere), and auto-installs missing system deps via apt
where available. The Windows installer is standalone PowerShell.

## Troubleshooting

### "Neither curl nor wget found"
Install curl: `sudo apt-get install curl` (Ubuntu) or install Xcode Command Line Tools (macOS).

### "Python extraction failed"
The python-build-standalone download may have failed. Check your network and retry. The installer uses Python 3.13.3 from [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone).

### "Could not find GPD binary"
The installer tries to download from GitHub releases. Check that you have network access to github.com.

### "gpd: command not found" after install
Open a new terminal, or run `source ~/.bashrc` (or `source ~/.zshrc` on macOS).

### Re-configuring the PSI key
Edit `~/.gpd/config/litellm.env` directly (set `GPD_API_KEY=sk-...`), or delete it and re-run the installer.

## Future: GUI Installers

GUI installers (.pkg for macOS, Inno Setup .exe for Windows, .deb for Ubuntu) are planned for a future version. They will wrap the same installation logic in native platform installer wizards.
