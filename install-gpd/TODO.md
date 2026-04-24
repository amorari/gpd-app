# GPD Installer — Roadmap

Open items for the cross-platform installer (`install` + `windows_11/install.ps1`).
Already-shipped items live in git history — see `docs/CHANGES.md` for the
rolling changelog.

## Open

### CI workflow for GPD CLI binary releases (priority: medium)

Today the installers fall back to upstream `anomalyco/opencode` CLI binaries
when the GPD fork hasn't cut its own. A GitHub Actions workflow that builds
and publishes `opencode-{linux|darwin|windows}-{x64|arm64}.{tar.gz|zip}`
artifacts from the GPD fork would guarantee users get the GPD-patched CLI.

The existing desktop release workflow (`.github/workflows/release-desktop.yml`)
is the template.

### GUI installers (deferred)

Native platform installer wizards wrapping the same install logic:

- [ ] macOS `.pkg`
- [ ] Windows Inno Setup `.exe`
- [ ] Ubuntu `.deb`

### python-build-standalone version bump automation

Portable Python is pinned in `install` and `windows_11/install.ps1`:

- `PBS_TAG=20250409`
- Python 3.13.3

Periodic bumps needed as new Python versions release. Renovate-style
automation would save manual tracking.

## Architecture notes

```
install-gpd/
├── install                    # Unified installer (Ubuntu + macOS + other Linux)
├── uninstall.sh               # Linux uninstaller
├── uninstall_macos.sh         # macOS uninstaller
├── windows_11/
│   ├── install.ps1            # Windows PowerShell installer
│   └── uninstall.ps1          # Windows uninstaller
├── README.md                  # User-facing docs
└── TODO.md                    # This file
```

**Install directory**: `~/.gpd/` on all platforms.

**OpenCode binary fallback**: tries `psi-oss/gpd-app` releases first; falls
back to `anomalyco/opencode` if no GPD-specific CLI binary is found.

**Python strategy**: uses system Python if >= 3.11; otherwise downloads
the portable build from `astral-sh/python-build-standalone`.
