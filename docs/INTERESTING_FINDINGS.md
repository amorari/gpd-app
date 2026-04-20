# GPD Desktop App — Interesting Findings

## Branding: 41 "OpenCode" references in user-visible text — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~High~~ None (resolved)
**Description:** 14 non-English desktop i18n files all contained ~5 "OpenCode" strings each. Fixed proactively during cron run while app was down.
**Action:** RESOLVED — 70 replacements across 14 files, with grammar-correct translations in each language.

## Branding: Error/help links point to opencode.ai — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~Medium~~ None (resolved)
**Description:** Fixed — both URLs in error.tsx and layout.tsx now point to github.com/psi-oss/opencode/issues.
**Action:** RESOLVED.

## Branding: "opencode.json" in user-facing error messages — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~Medium~~ None (resolved)
**Description:** Fixed — 34 "opencode.json" references across 17 locale files replaced with localized "GPD settings" equivalents.
**Action:** RESOLVED.

## Branding: Theme named "OpenCode" in theme picker — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~Low~~ None (resolved)
**Description:** Fixed — theme display name, schema title/description, and theme JSON name all changed to "GPD".
**Action:** RESOLVED.

## Branding: Web manifest says "OpenCode" — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~Low~~ None (resolved)
**Description:** Fixed in pre-iteration changes — both name and short_name now say "GPD".
**Action:** RESOLVED.

## Architecture: Window title shows "OpenCode" — RESOLVED
**Found in:** Pre-iteration baseline audit
**Severity:** ~~High~~ None (resolved)
**Description:** Fixed in windows.rs:56 (.title("OpenCode") → .title("GPD")). Confirmed working after Rust rebuild — `query_page(mode='app_info')` now returns `"title": "GPD"`.
**Action:** RESOLVED.

## Config: MCP server paths reference ~/.gpd/venv — RESOLVED
**Found in:** Pre-iteration baseline audit (filesystem check)
**Severity:** ~~Medium~~ None (resolved)
**Description:** All 8 MCP server commands in opencode.json reference `~/.gpd/venv/bin/python`. Confirmed in Iteration 1 that `~/.gpd/venv/bin/python` EXISTS as a symlink to python3. This is a separate venv path from `~/.config/gpd/.venv/` — both exist and are valid.
**Why interesting:** Two separate Python venv paths coexist. `~/.gpd/venv` is used by MCP servers, `~/.config/gpd/.venv` is the first-run setup venv.
**Action:** RESOLVED — both paths are valid. No fix needed.

## Testing: Tauri MCP JS bridge unresponsive
**Found in:** Pre-iteration UI check
**Severity:** High
**Description:** The Tauri MCP plugin's JS-dependent operations (`execute_js`, `manage_storage`, `query_page` in map/state modes) all time out consistently. Only Rust-side operations (`app_info`, `take_screenshot`) succeed. This means we cannot programmatically inspect DOM elements, check localStorage, or execute JavaScript in the webview via MCP.
**Why interesting:** This severely limits UI automation testing. Many iteration tests rely on DOM inspection and JS execution. The cause could be a blocked JS event loop, missing MCP JS bridge initialization, or the webview being saturated.
**Action:** Investigate root cause. Fallback to macOS Accessibility APIs + screenshots for UI testing. May need to restart `bun tauri dev` to see if it resolves.

## Branding: All user-visible "OpenCode" references eliminated
**Found in:** Proactive branding sweep (while app was down for iterations 2-6 cron runs)
**Severity:** Informational
**Description:** Comprehensive audit confirms zero "OpenCode" in any user-facing text:
- 0 in desktop i18n (14 files, 70 replaced)
- 0 in app i18n (17 files, 34 "opencode.json" replaced)
- 0 in theme names, schema, web manifest, error links
- 0 in window title (Rust fix confirmed after rebuild — title is "GPD")
- Remaining "OpenCode" strings are all internal code (Shiki theme registry in marked.tsx/pierre, TypeScript types in deep-links.ts, Storybook stories, code comments) — never shown to professors.
**Why interesting:** Branding sweep is effectively complete ahead of Iteration 16. The final sweep can focus on jargon audit and visual verification instead.
**Action:** Iteration 16 agents can skip i18n scanning and focus on git/coding jargon and visual verification.

## Bug: MCP servers used wrong Python venv — RESOLVED
**Found in:** Iteration 3 (MCP Servers)
**Severity:** ~~High~~ None (resolved)
**Description:** `gpd install opencode` wrote MCP entries pointing to `~/.gpd/venv/bin/python` (stale venv from older install, missing arxiv_bridge). The correct venv at `~/.config/gpd/.venv/bin/python` had all modules including arxiv_bridge. Root cause: GPD's `hook_python_interpreter()` picked the wrong venv. NOT an upstream package bug — the module exists, it was just the wrong Python path.
**Fix:** (1) Runtime: updated all 8 paths in opencode.json. (2) Code: gpd_setup.rs now overwrites MCP entries in inject_provider_config().
**Action:** RESOLVED.

## Finding: Gemini sanitizeGemini fix is client-side only
**Found in:** Iteration 5 (Model Selection)
**Severity:** Medium
**Description:** Direct curl to LiteLLM with an `anyOf` schema in tool params returns 400 from Gemini. The `sanitizeGemini` fix (commit 09e808385b) strips `anyOf`/`allOf` client-side in the OpenCode sidecar before sending to LiteLLM — it does NOT run at the proxy level. This means the fix works in the app but not for direct API calls.
**Why interesting:** Confirms the fix architecture — client-side sanitization, not proxy-level. Needs in-app verification to confirm it works end-to-end.
**Action:** Verify during UI testing by sending a message to Gemini with all 8 MCP tools enabled.

## Bug: GPD venv missing scientific packages and pip
**Found in:** Iteration 7 (Python Script Execution)
**Severity:** High
**Description:** The GPD venv at `~/.config/gpd/.venv/` has Python 3.12.10 and the GPD application stack (68 packages: aiohttp, httpx, mcp, rich, etc.) but is completely missing scientific computing packages: numpy, scipy, matplotlib, sympy. pip itself is also absent. The venv was created with `get-physics-done[arxiv]` which only adds arxiv dependencies, not scientific computing.
**Why interesting:** This is a physics research tool. A professor asking the AI to "plot sin(x)" or "compute eigenvalues" will hit `ModuleNotFoundError`. The agent can't even install packages on-demand because pip is missing. This is the most impactful UX bug found so far.
**Action:** Fix in gpd_setup.rs — add scientific packages to the first-run venv setup. Either: (1) install numpy, scipy, matplotlib, sympy during `ensure_gpd_installed()`, or (2) ensure pip is available so the agent can install on-demand.
