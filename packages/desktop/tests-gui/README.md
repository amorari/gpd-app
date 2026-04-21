# GPD GUI test suite

End-to-end tests that drive the live GPD desktop app. Runs against an installed `/Applications/GPD.app` by default; point `GPD_APP_PATH` at `packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app` (or similar) to target an in-tree dev build.

**Status:** Phase 1 (smoke) is complete — 68 unit tests + 11 live-app smoke tests + an opt-in restart test. Phase 2 (surfaces, per-route) is complete — 9 surface test files covering all primary routes and dialogs; run with `-m surfaces`. Phase 3 (flows) is complete with 5 end-to-end flow files: create-session, theme-switch, deep-link, onboarding, and provider-switch; Phase 4 (regression) tracks regressions against known-good baselines; Phase 5 (broad menu coverage) adds AX-only menu sweeps that stay green even when the JS bridge is unavailable.

## Setup

```bash
cd packages/desktop/tests-gui
uv sync
brew install cliclick
# Grant Accessibility permission to your terminal in System Settings → Privacy & Security → Accessibility
```

## Running

```bash
uv run pytest -m unit                               # fast unit tests, no GPD needed
uv run pytest -m smoke                              # Phase 1 smoke tests (launches GPD backgrounded)
uv run pytest -m restart                            # destructive: physically restarts GPD (briefly steals focus)
uv run pytest -m "smoke or restart"                 # full Phase 1 (CI / pre-release)
uv run pytest -m "not real_backend"                 # skip tests that need a real LLM key
```

### Phase 3 (flows)

> All paths below assume `cwd = packages/desktop/tests-gui/`.

```bash
# Non-destructive, no LLM key needed:
uv run pytest -m "flows and not real_backend" -v

# Full Phase 3 including LLM-backed flows:
export GPD_TEST_ANTHROPIC_KEY=<key>
export GPD_APP_PATH="$(cd ../src-tauri/target/debug/bundle/macos && pwd)/GPD Dev.app"
uv run pytest -m flows -v

# Include the destructive onboarding flow:
export PYTEST_RUN_DESTRUCTIVE_FLOWS=1
uv run pytest -m flows -v
```

The live LLM test (`test_new_session.py`) requires GPD's debug build to be running with the sidecar active, the same as the rest of the smoke suite.

### Targeting a dev build

```bash
# After `cd packages/desktop && cargo tauri build --debug`
export GPD_APP_PATH="$(pwd)/src-tauri/target/debug/bundle/macos/GPD Dev.app"
uv run pytest -m smoke
```

### Phase 2 — Surfaces

```bash
uv run pytest -m surfaces                               # all surface tests
uv run pytest -m "surfaces and not steals_focus"        # backgrounded default (recommended)
uv run pytest -m "surfaces and steals_focus"            # focus-stealing (⌘, etc.) — briefly brings GPD to front
```

Current surface coverage: `test_loading`, `test_home`, `test_project`, `test_session`, `test_dialog_settings` (`steals_focus`), `test_dialog_edit_project`, `test_dialog_select_server`, `test_dialog_select_provider`, `test_dialog_select_directory`. Many DOM-probing tests skip gracefully when the `execute_js` bridge is unresponsive — structural route checks still run and assert URL reachability via MCP `navigate_webview`.

### Phase 5 — Broad (menu coverage)

AX-only tests that iterate GPD's macOS menu bar. No JS bridge required, so these work reliably even when the welcome overlay blocks `execute_js`.

```bash
uv run pytest -m broad -v                               # menu sweep + per-menu expectations
uv run pytest -m "broad and not steals_focus" -v        # skip anything that would steal focus
```

Tests cover: every top-level menu is non-empty; File has New-Conversation / Open / Close-Window concepts; Edit has clipboard standards (Undo/Redo/Cut/Copy/Paste/Select-All); View is non-empty + soft-check for full-screen/zoom/reload; Help is non-empty; the application menu (`GPD` or `GPD Dev`) exposes About, Settings, and an enabled Quit entry.

Drift tolerance: each concept accepts multiple label variants, so upstream i18n sweeps don't break the suite.

### Release-mode security assertions

After `cargo tauri build` (no `--debug`):

```bash
export GPD_APP_PATH="$(cd ../src-tauri/target/release/bundle/macos && pwd)/GPD Dev.app"
open "$GPD_APP_PATH"
PYTEST_RELEASE_BUILD=1 uv run pytest tests/smoke/test_release_no_mcp.py -v
```

Both assertions must pass: the Rust-side plugin is absent (no socket) **and** the Vite tree-shake worked (no vendored code in release `dist/`). These are the regression-safety net for the security fix in `src-tauri/src/lib.rs:351` plus the `__GPD_TAURI_DEBUG__` define in `vite.config.ts`.

### Environment variables

- `GPD_APP_PATH` — path to the `.app` bundle. Defaults to `/Applications/GPD.app`.
- `GPD_MCP_SOCKET` — explicit Unix-socket path. Default: glob `/var/folders/*/*/T/tauri-mcp.sock`.
- `GPD_TEST_ANTHROPIC_KEY` — Anthropic API key; enables `real_backend`-marked tests.
- `PYTEST_SLOWMO_MS` — per-action delay (default 200 local, 0 in CI).
- `PYTEST_CI=1` — CI mode (no slow-mo, HTML report, reruns).
- `PYTEST_QUIT_GPD=1` — quit GPD at end of session (default: leave running).
- `PYTEST_COLD_START=1` — kill stale GPD/opencode-cli before launching (use in CI; avoid locally).
- `PYTEST_RUN_DESTRUCTIVE_FLOWS=1` — opt in to the onboarding flow (mutates `~/.config/gpd` and `auth.json`).
- `GPD_TEST_SEED_ONBOARDING=1` — seed `auth.json` + sentinel for the session (requires `GPD_TEST_ANTHROPIC_KEY`). Both flags must be set; the two-flag guard avoids surprise writes on a developer's laptop.

## Layout

- `gpd_tests/drivers/` — MCP Unix socket, opencode-cli HTTP, macOS Accessibility, OS input.
- `gpd_tests/helpers/` — i18n (reads committed `fixtures/en.json`), selectors, timings, artifacts, DOMProbe, Navigator.
- `gpd_tests/pages/` — thin lifecycle + page objects.
- `tests/smoke/` — Phase 1 smoke suite.
- `tests_unit/` — fast driver/helper unit tests (no GPD needed).
- `scripts/` — tiered state reset (`--tier {0..3}`), i18n refresh, MCP token discovery.
- `gpd_tests/fixtures/en.json` — snapshot of GPD 1.1.0's i18n dictionary (831 keys). Refresh with `uv run python scripts/refresh_en_dict.py`.

## Phase 2

Phase 2 (one test per route/dialog) needs `execute_js` (and therefore any DOM probe) to respond. That requires `setupPluginListeners()` from `tauri-plugin-mcp/guest-js/index.ts` to run in the webview.

Upstream (`psi-oss/opencode`) hasn't wired this in yet, so this branch carries a **local workaround**: the plugin's `guest-js/index.ts` is vendored at `packages/desktop/src/vendor/tauri-plugin-mcp.ts` and wired from `packages/desktop/src/index.tsx` behind `__GPD_TAURI_DEBUG__` (see `vite.config.ts`). Vite tree-shakes it out of release builds, matching the Rust-side `#[cfg(debug_assertions)]` gate on the plugin in `packages/desktop/src-tauri/src/lib.rs`.

Refresh the vendor if the plugin repo changes:

```bash
curl -sfL https://raw.githubusercontent.com/psi-oss/tauri-plugin-mcp/main/guest-js/index.ts \
  -o packages/desktop/src/vendor/tauri-plugin-mcp.ts
# re-prepend the provenance header
```

Only functional against a debug build (`cargo tauri build --debug`), since the Rust-side plugin is gated. A release build has neither the socket nor the JS listeners.

## Troubleshooting

- **MCP socket missing** (`FileNotFoundError: /var/folders/.../tauri-mcp.sock`) — GPD isn't running, or you're running a release build (the plugin is gated behind `#[cfg(debug_assertions)]`). Launch a debug build.
- **AppleScript error -1719 / "not allowed assistive access"** — grant your terminal Accessibility permission.
- **`execute_js` timeouts** — webview listeners never registered. Confirm the build is debug (dev only) and that `src/vendor/tauri-plugin-mcp.ts` is intact.
- **Providers test skipped** — set `GPD_TEST_ANTHROPIC_KEY` and re-run.
- **`cliclick: command not found`** — `brew install cliclick`.

## CI

The workflow is defined at `.github/workflows/gpd-tests-gui.yml`.

**Triggers:**
- `push` to any branch that touches `packages/desktop/tests-gui/**`, `packages/desktop/src-tauri/**`, `packages/desktop/src/**`, or the workflow file itself.
- `pull_request` targeting the `gpd` branch.
- Manual `workflow_dispatch`.

**Jobs:**

| Job | Runner | What runs |
|-----|--------|-----------|
| `unit` | `macos-latest` | `pytest -m unit -q` — fast, no GPD needed |
| `smoke-and-flows` | `macos-latest` | Builds debug GPD, launches it, then runs smoke (marker: `smoke and not restart`) + non-real-backend flows |

**Real-backend flows (`GPD_TEST_ANTHROPIC_KEY` secret):**

Tests marked `real_backend` (those that make live LLM calls) are skipped unless the repository secret `GPD_TEST_ANTHROPIC_KEY` is configured. Add it under *Settings → Secrets and variables → Actions* with an Anthropic API key. When the secret is present the workflow also sets `GPD_TEST_SEED_ONBOARDING=1` so the `seed_onboarding_state` autouse fixture (in `conftest.py`) writes `auth.json` before GPD launches.

Fork PRs never receive repository secrets — real-backend steps will be skipped silently on forks.

**Known CI limitations (first-run):**

GitHub-hosted macOS runners do not grant Accessibility (AX) permission to arbitrary processes. Tests that rely on AX (AppleScript window queries, `cliclick` keyboard injection) will fail with *-1719 not allowed assistive access*. The HTTP-only driver tests and MCP-socket tests still pass. This is documented in the workflow comments and is expected until a provisioned self-hosted runner is available.
