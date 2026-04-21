# GPD Installer — Status & Follow-up Tasks

**Last updated**: 2026-04-16
**Branch**: `gpd` on `psi-oss/gpd-app`
**Commit**: `88fa669f1` — "Add GPD CLI installers for Ubuntu, macOS, and Windows"

## Completed

- [x] Ubuntu 24.04 CLI installer (`ubuntu_24_04/install.sh`)
- [x] macOS Tahoe CLI installer (`macos_26_tahoe/install.sh`, arm64 + x64 + Rosetta detection)
- [x] Windows 11 PowerShell installer (`windows_11/install.ps1`, standalone 638 lines)
- [x] Shared bash library (`common.sh` — download, Python install, venv, GPD install, key prompt, PATH)
- [x] README with usage, troubleshooting, uninstall instructions
- [x] Parallel code review (security + engineering) — 6 issues fixed:
  - `grep -oP` → `grep -oE` for macOS compat
  - EXIT trap collision in install_opencode — switched to block cleanup
  - Secrets file race — umask 077 before writing litellm.env
  - Hardcoded OPENCODE_ORG (removed env var override, security)
  - Ubuntu python3-venv package detection
  - CMD wrapper `eol=#` fix for comment filtering
- [x] Idempotent (safe to re-run)
- [x] LiteLLM key prompted and stored securely (`~/.gpd/config/litellm.env`)
- [x] `gpd` wrapper launches OpenCode with GPD config

## NOT Tested

Scripts have not been tested on actual fresh installs (no VM was available). This is the highest priority follow-up.

## Follow-up Tasks

### 0. Set up `download.gpd.psi.inc` (BLOCKER for launch)

The README's quick-start one-liner points at `https://download.gpd.psi.inc/install`,
which does not resolve. Options:

- **Redirect** — create a CNAME/redirect from `download.gpd.psi.inc/install` to
  `raw.githubusercontent.com/psi-oss/opencode/gpd/install-gpd/install` (and similarly
  for `install.ps1`). Simplest, no hosting needed.
- **Self-host** — put the installer on a static bucket (S3, Cloudflare Pages) and
  update on each release. More control, versioning.

Until this is done, users must use the GitHub raw URL directly, which leaks
the internal repo layout.

### 0.5. Test on macOS (HIGH PRIORITY — no VM available)

The macOS installer (`macos_26_tahoe/install.sh`) and the macOS branch of the
unified `install` have not been tested end-to-end. The new LaTeX install step
(`brew install --cask basictex` + `/Library/TeX/texbin/tlmgr install latexmk`)
has no test coverage at all. Options:

- Borrow a physical Mac (Apple Silicon + Intel if possible)
- Use a GitHub Actions macOS runner for automated testing
- Cloud Mac service (MacStadium, AWS EC2 Mac)

Should verify: Homebrew guard works when brew is absent, BasicTeX install
succeeds, tlmgr path works even when `/Library/TeX/texbin` isn't on PATH for
the current shell.

### 1. Test on Fresh Installs (HIGH PRIORITY)

Test each installer on a clean machine/VM:

- [ ] Ubuntu 24.04 fresh install (VM or container)
- [ ] macOS (Apple Silicon + Intel, or Rosetta)
- [ ] Windows 11 fresh install (VM)

Verify: OpenCode runs, `gpd` command works, Python venv has get-physics-done, litellm.env is created with correct permissions.

### 2. CI Workflow for GPD CLI Binary Releases (HIGH PRIORITY)

**Problem**: The GPD fork (`psi-oss/gpd-app`, `gpd` branch) only publishes desktop app assets (.deb, .dmg, .exe) — no standalone CLI binaries. The installers currently fall back to upstream `anomalyco/opencode` CLI binaries.

**Needed**: A GitHub Actions workflow that builds and publishes CLI binaries (`opencode-{linux|darwin|windows}-{x64|arm64}.{tar.gz|zip}`) from the GPD fork. This ensures users get the GPD-patched version of OpenCode, not upstream.

**Reference**: The upstream release workflow is at the root of the anomalyco/opencode repo. The existing GPD release workflow (`.github/workflows/release-desktop.yml`) handles desktop builds — a similar one is needed for CLI.

### 3. Download Checksum Verification (MEDIUM)

**Problem**: Installers download binaries over HTTPS but don't verify SHA256 checksums. The security review flagged this.

**Needed**: Publish SHA256 checksum files alongside release binaries. Update installers to verify checksums after download.

### 4. GUI Installers (NEXT VERSION — DEFERRED)

Planned for a future release:

- [ ] macOS: `.pkg` installer
- [ ] Windows: Inno Setup `.exe` installer  
- [ ] Ubuntu: `.deb` package

These wrap the same installation logic in native platform installer wizards.

### 5. python-build-standalone Version Updates (LOW)

The portable Python version is hardcoded in `common.sh` and `install.ps1`:
- `PBS_TAG=20250409`
- Python 3.13.3

This needs periodic bumps as new Python versions release. Consider automating this via CI or a renovate-style check.

### 6. GPD Runtime Configuration (LOW)

The step `gpd install --opencode --global` in the installer may fail if the GPD CLI doesn't support it yet from a venv context. Verify this works end-to-end once GPD package stabilizes.

## Architecture Notes

```
install-gpd/
├── common.sh                  # Shared bash functions (sourced by Ubuntu + macOS)
├── ubuntu_24_04/install.sh    # Sources common.sh, adds apt deps
├── macos_26_tahoe/install.sh  # Sources common.sh, detects Rosetta/arm64
├── windows_11/install.ps1     # Standalone PowerShell (mirrors common.sh logic)
└── README.md                  # User-facing docs
```

**Install directory**: `~/.gpd/` on all platforms

**OpenCode binary fallback**: Tries `psi-oss/gpd-app` releases first, falls back to `anomalyco/opencode` if no CLI binary found.

**Python strategy**: Uses system Python if >= 3.11, otherwise downloads portable build from astral-sh/python-build-standalone.

## Slack Thread

Coordination was done in `#engineering-agents-coworking` (channel `C0AT3R2HX1T`), thread_ts: `1776373474.365499`.
