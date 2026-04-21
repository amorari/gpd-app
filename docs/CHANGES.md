# GPD Desktop App — Changes Log

## Pre-Iteration: Immediate Branding Fixes
**Date:** 2026-04-17
**Changes:**
- `packages/desktop/src-tauri/src/windows.rs:56` — Changed `.title("OpenCode")` → `.title("GPD")` (window title bar)
- `packages/desktop/src-tauri/release/appstream.metainfo.xml:8,9,17` — Changed name "OpenCode" → "GPD", summary to "AI-powered physics research workspace", description to physics-oriented text
- `packages/ui/src/assets/favicon/site.webmanifest:2,3` — Changed name/short_name "OpenCode" → "GPD"
**Bugs fixed:**
- Window title showed "OpenCode" instead of "GPD" — root cause: hardcoded string in windows.rs → fixed to "GPD"
- AppStream metadata identified app as "OpenCode" coding agent — fixed to GPD physics workspace
- Web manifest PWA name was "OpenCode" — fixed to "GPD"
**Rebuilds triggered:** yes (Rust change in windows.rs requires `bun tauri dev` restart)

## Proactive Branding Sweep (while app down)
**Date:** 2026-04-17
**Changes:**
- `packages/desktop/src/i18n/ja.ts` — 5 "OpenCode" → "GPD" replacements (Japanese)
- `packages/desktop/src/i18n/ko.ts` — 5 "OpenCode" → "GPD" replacements (Korean)
- `packages/desktop/src/i18n/pl.ts` — 5 "OpenCode" → "GPD" replacements (Polish)
- `packages/desktop/src/i18n/no.ts` — 5 "OpenCode" → "GPD" replacements (Norwegian); "CLI-binærfil" → "GPD-applikasjonen"
- `packages/desktop/src/i18n/ru.ts` — 5 "OpenCode" → "GPD" replacements (Russian)
- `packages/desktop/src/i18n/fr.ts` — 5 "OpenCode" → "GPD" replacements (French); "d'OpenCode" → "de GPD"; "CLI" → "application"
- `packages/desktop/src/i18n/zht.ts` — 5 "OpenCode" → "GPD" replacements (Traditional Chinese)
- `packages/desktop/src/i18n/zh.ts` — 5 "OpenCode" → "GPD" replacements (Simplified Chinese)
- `packages/desktop/src/i18n/bs.ts` — 5 "OpenCode" → "GPD" replacements (Bosnian); "OpenCode-a" → "GPD-a"
- `packages/desktop/src/i18n/br.ts` — 5 "OpenCode" → "GPD" replacements (Brazilian Portuguese)
- `packages/desktop/src/i18n/es.ts` — 5 "OpenCode" → "GPD" replacements (Spanish)
- `packages/desktop/src/i18n/ar.ts` — 5 "OpenCode" → "GPD" replacements (Arabic)
- `packages/desktop/src/i18n/da.ts` — 5 "OpenCode" → "GPD" replacements (Danish)
- `packages/desktop/src/i18n/de.ts` — 5 "OpenCode" → "GPD" replacements (German); "CLI-Binary" → "GPD-Anwendung"
- `packages/ui/src/theme/context.tsx:69` — Theme display name "OpenCode" → "GPD"
- `packages/ui/src/theme/desktop-theme.schema.json` — Title/description "OpenCode" → "GPD"
- `packages/ui/src/theme/themes/opencode.json` — Theme name "OpenCode" → "GPD"
- `packages/app/src/pages/error.tsx:304` — Feedback URL opencode.ai → github.com/psi-oss/gpd-app/issues
- `packages/app/src/pages/layout.tsx:2358` — Feedback URL opencode.ai → github.com/psi-oss/gpd-app/issues
**Bugs fixed:**
- 70 "OpenCode" references across 14 non-English locale files → all replaced with "GPD" with proper grammar in each language
- "CLI binary" jargon in sidecarMissing error → replaced with "application"/"aplicación"/"Anwendung"/etc in each language
- Theme picker showed "OpenCode" → now shows "GPD"
- Error/feedback links pointed to opencode.ai → now point to GPD GitHub issues
- Theme schema referenced "OpenCode Desktop Theme" → now says "GPD Desktop Theme"
**Rebuilds triggered:** no (TypeScript/JSON changes, hot-reloaded by Vite)

## Proactive Branding Sweep Part 2 (while app down)
**Date:** 2026-04-17
**Changes:**
- 17 app i18n files (`packages/app/src/i18n/*.ts`) — replaced "opencode.json" with localized "GPD settings" in 2 keys each:
  - `dialog.plugins.empty`: "configured in opencode.json" → "configured in GPD settings" (17 languages)
  - `error.chain.checkConfig`: "Check your config (opencode.json)" → "Check your GPD settings" (17 languages)
  - Includes en, ja, ko, pl, no, ru, es, zht, de, bs, ar, zh, da, fr, br, th, tr
**Bugs fixed:**
- 34 "opencode.json" references in user-facing error messages across 17 locale files → replaced with "GPD settings" in each language
- Removed technical `(opencode.json)` parenthetical from error messages — professors don't need to know config file names
**Rebuilds triggered:** no

## Iteration 3: MCP Server Python Path Fix
**Date:** 2026-04-17
**Changes:**
- `packages/desktop/src-tauri/src/gpd_setup.rs` — `inject_provider_config()` now overwrites MCP server entries with the correct venv Python path (`~/.config/gpd/.venv/bin/python`). Previously, `gpd install opencode` wrote MCP entries pointing to a stale `~/.gpd/venv/` which lacked the `arxiv_bridge` module.
- `~/.config/gpd/opencode.json` (runtime fix) — updated all 8 MCP server Python paths from `~/.gpd/venv/bin/python` → `~/.config/gpd/.venv/bin/python`
**Bugs fixed:**
- gpd-arxiv MCP server failed to start — root cause: `gpd install opencode` used `hook_python_interpreter()` which picked `~/.gpd/venv/` (older venv without arxiv_bridge), while the correct venv at `~/.config/gpd/.venv/` had the module. Fix: `inject_provider_config()` now always overwrites MCP paths with the managed venv.
**Rebuilds triggered:** yes (Rust change, but runtime config also fixed immediately)

## Iteration 7: Scientific Packages Fix
**Date:** 2026-04-17
**Changes:**
- Runtime: `uv pip install numpy scipy matplotlib sympy` into `~/.config/gpd/.venv/` (immediate fix)
- `packages/desktop/src-tauri/src/gpd_setup.rs` — Added scientific packages install step in `ensure_gpd_installed()` after GPD package. Installs numpy, scipy, matplotlib, sympy. Made non-fatal (warns but doesn't block startup if it fails).
**Bugs fixed:**
- GPD venv missing scientific packages — fixed by installing numpy/scipy/matplotlib/sympy into current venv via uv.
- Revised approach: instead of pre-installing packages globally, make `uv` available to the agent so it can create per-project venvs on demand.
**Rebuilds triggered:** yes

## Iteration 7 (revised): Per-project venv support via uv
**Date:** 2026-04-17
**Changes:**
- `packages/desktop/src-tauri/src/gpd_setup.rs` — Replaced global scientific package install with uv symlink into `~/.config/gpd/bin/`. Agent can now run `uv venv && uv pip install numpy` per-project.
- `packages/desktop/src-tauri/src/lib.rs` — Prepend `~/.config/gpd/bin/` and `~/.config/gpd/.venv/bin/` to sidecar PATH so agent can find `uv` and GPD Python.
- Runtime: created `~/.config/gpd/bin/uv` symlink to bundled uv binary.
**Bugs fixed:**
- Agent couldn't install packages on demand — uv wasn't on PATH. Now `uv` is available at `~/.config/gpd/bin/uv` and on the agent's PATH.
**Rebuilds triggered:** yes (Rust changes to lib.rs and gpd_setup.rs)
