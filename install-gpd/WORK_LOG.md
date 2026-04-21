# GPD Installer — Work Log

**Date**: 2026-04-16
**Agent**: Claude Opus (via /implement workflow)
**Repo**: `psi-oss/gpd-app` branch `gpd`
**Working directory**: Originally `gpd-web` (`physicalsuperintelligence/gpd-web`), then moved to `psi-oss/gpd-app`

## Original Prompt

User invoked `/implement` with the following requirements:

> You are tasked with creating installers for Ubuntu, Mac, and Windows 11 for this project. You will install first OpenCode and then if not already installed Python (but local to the app instead of system global install), and GPD. References are https://github.com/psi-oss/gpd-app/blob/gpd/docs/GPD_DISTRIBUTION.md. There is an install folder in the project already. Follow all agent instructions at ~/dev/code/eai.txt. Use teams of agents. Here are steps at high level, but you need to investigate yourself as to what is needed:
> 1. Install OpenCode (our fork)
> 2. Install GPD
> 3. Install Python
> 4. Ask for LiteLLM key
> 5. Add gpd or gpd-cli or something to path so that when you run it, it runs our version of OpenCode.

## Key Decisions Made During Implementation

1. **CLI-first, GUI deferred**: User chose CLI installers first; GUI (.pkg, Inno Setup, .deb) planned for next version.
2. **Repo location**: Work started in `gpd-web` repo, user redirected to `psi-oss/gpd-app` repo. Scaffolding commit in gpd-web was reverted.
3. **Folder name**: `install-gpd/` (not `install/`) to avoid conflict with existing root-level `install` script (upstream OpenCode installer).
4. **Python strategy**: Use system Python if >= 3.11, otherwise download portable build from astral-sh/python-build-standalone (PBS_TAG=20250409, Python 3.13.3). Install is app-local to `~/.gpd/python/`, not system-wide.
5. **OpenCode binary fallback**: GPD fork has no CLI binary releases yet (only desktop .deb/.dmg/.exe). Installers try GPD fork first, fall back to upstream `anomalyco/opencode` CLI binaries.
6. **Shared code**: `common.sh` holds all logic for bash platforms (Ubuntu + macOS). Windows `install.ps1` is standalone PowerShell since it can't source bash.

## What Was Done

### Phase 1: Research (parallel agents)

- Read GPD_DISTRIBUTION.md from the opencode repo
- Read existing `install` script (upstream OpenCode bash installer)
- Read `bin/install.js` (existing GPD npm bootstrap)
- Checked GPD fork releases — found only desktop assets, no CLI binaries
- Read agent instructions at `~/dev/code/agent-instructions/AGENT.txt` and workflow files

### Phase 2: Implementation

Wrote 5 files in `install-gpd/`:

1. **`common.sh`** (~330 lines) — Shared bash functions:
   - `install_opencode()` — downloads CLI binary from GitHub releases
   - `ensure_python()` — checks system Python, downloads portable build if needed
   - `create_venv()` — creates Python venv at ~/.gpd/venv/
   - `install_gpd()` — installs get-physics-done from GitHub source
   - `prompt_litellm_key()` — interactive key prompt, stores in ~/.gpd/config/litellm.env
   - `create_gpd_wrapper()` — creates `gpd` shell script that sources env and execs opencode
   - `add_to_path()` — adds ~/.gpd/bin to shell PATH config
   - `run_install()` — orchestrates all steps

2. **`ubuntu_24_04/install.sh`** (~45 lines) — Sources common.sh, installs apt deps (curl, tar, unzip, python3-venv)

3. **`macos_26_tahoe/install.sh`** (~40 lines) — Sources common.sh, detects Rosetta translation (x64→arm64 switch)

4. **`windows_11/install.ps1`** (638 lines) — Standalone PowerShell:
   - Full reimplementation of common.sh logic
   - .NET tar fallback for systems without tar.exe
   - Creates both `gpd.ps1` and `gpd.cmd` wrappers
   - ACL-based file permissions for litellm.env
   - PATH modification via `[Environment]::SetEnvironmentVariable`

5. **`README.md`** (~130 lines) — Quick start, what gets installed, configuration, troubleshooting, uninstall

### Phase 3: Parallel Review (6 agents)

Ran security + engineering review agents in parallel. Fixed 6 issues:

| Severity | Issue | Fix |
|----------|-------|-----|
| CRITICAL | `grep -oP` (Perl regex) breaks on macOS | Changed to `grep -oE` with POSIX regex |
| HIGH | EXIT trap collision in `install_opencode` | Removed trap, use block cleanup with explicit rm |
| HIGH | Secrets file race (litellm.env world-readable briefly) | `umask 077` subshell before writing |
| MEDIUM | `OPENCODE_ORG` env var override (download redirect attack) | Hardcoded to `"psi-oss"` |
| MEDIUM | Ubuntu missing python3-venv package | Added detection in `install_system_deps()` |
| MEDIUM | CMD wrapper comment filter syntax error | Fixed with `eol=#` in for/f statement |

### Phase 4: Commit & Push

- Committed to `psi-oss/gpd-app` gpd branch: `88fa669f1`
- Reverted scaffolding commit in gpd-web: `cb2018ac`
- Posted status updates to Slack `#engineering-agents-coworking` thread

## User Corrections During Session

1. **Agent instructions location**: I initially looked for `agent-instructions/AGENT.txt` relative to the project dir. User corrected: "references are relative to location of eai.txt" (`~/dev/code/eai.txt` → `~/dev/code/agent-instructions/AGENT.txt`).
2. **Repo location**: I started working in `gpd-web`. User asked "which repo are you on?" and directed me to clone `psi-oss/gpd-app` to `../opencode/` and work there instead.
3. **Slack coordination**: User reminded me to check custom.md for Slack posting instructions.

## References

- **GPD distribution docs**: https://github.com/psi-oss/gpd-app/blob/gpd/docs/GPD_DISTRIBUTION.md
- **Upstream OpenCode installer**: `/home/nima/dev/code/work/gpd/opencode/install` (root-level bash script)
- **GPD Python package**: https://github.com/psi-oss/get-physics-done
- **python-build-standalone**: https://github.com/astral-sh/python-build-standalone
- **LiteLLM proxy**: `https://litellm-production-46bb.up.railway.app`
- **Agent instructions**: `~/dev/code/agent-instructions/AGENT.txt`
- **Checkpoint**: `~/.claude/implement-checkpoints/1_gpd-ui-install/implement-2026-04-16T21-21.md`
- **Slack thread**: Channel `C0AT3R2HX1T`, thread_ts `1776373474.365499`
