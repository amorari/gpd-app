# GPD GUI test suite

End-to-end tests that drive the live GPD desktop app. Runs against an installed `/Applications/GPD.app` by default; point `GPD_APP_PATH` at `packages/desktop/src-tauri/target/debug/bundle/macos/GPD.app` (or similar) to target an in-tree dev build.

**Status:** Phase 1 (smoke) is complete — 40 unit tests + 9 live-app smoke tests + an opt-in restart test. Phase 2 (surfaces, per-route) is blocked until `setupPluginListeners()` from `tauri-plugin-mcp` is wired into the desktop frontend — see the Phase 2 section below.

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

### Targeting a dev build

```bash
# After `cd packages/desktop && cargo tauri build --debug`
export GPD_APP_PATH="$(pwd)/src-tauri/target/debug/bundle/macos/GPD.app"
uv run pytest -m smoke
```

### Environment variables

- `GPD_APP_PATH` — path to the `.app` bundle. Defaults to `/Applications/GPD.app`.
- `GPD_MCP_SOCKET` — explicit Unix-socket path. Default: glob `/var/folders/*/*/T/tauri-mcp.sock`.
- `GPD_TEST_ANTHROPIC_KEY` — Anthropic API key; enables `real_backend`-marked tests.
- `PYTEST_SLOWMO_MS` — per-action delay (default 200 local, 0 in CI).
- `PYTEST_CI=1` — CI mode (no slow-mo, HTML report, reruns).
- `PYTEST_QUIT_GPD=1` — quit GPD at end of session (default: leave running).
- `PYTEST_COLD_START=1` — kill stale GPD/opencode-cli before launching (use in CI; avoid locally).

## Layout

- `gpd_tests/drivers/` — MCP Unix socket, opencode-cli HTTP, macOS Accessibility, OS input.
- `gpd_tests/helpers/` — i18n (reads committed `fixtures/en.json`), selectors, timings, artifacts, DOMProbe, Navigator.
- `gpd_tests/pages/` — thin lifecycle + page objects.
- `tests/smoke/` — Phase 1 smoke suite.
- `tests_unit/` — fast driver/helper unit tests (no GPD needed).
- `scripts/` — tiered state reset (`--tier {0..3}`), i18n refresh, MCP token discovery.
- `gpd_tests/fixtures/en.json` — snapshot of GPD 1.1.0's i18n dictionary (831 keys). Refresh with `uv run python scripts/refresh_en_dict.py`.

## Phase 2 (blocked)

Phase 2 (one test per route/dialog) needs `execute_js` / `get_page_map` / `wait_for` to actually respond. Today they time out at 5 s because `setupPluginListeners()` from `tauri-plugin-mcp/guest-js/index.ts` is never called in `packages/desktop/src/index.tsx`, so the webview never installs the listeners the Rust plugin is emitting to.

Minimal unblocking fix (in debug builds only, matching the plugin's `#[cfg(debug_assertions)]` gate already applied in `packages/desktop/src-tauri/src/lib.rs`):

```tsx
// packages/desktop/src/index.tsx (after existing imports)
if (import.meta.env.DEV) {
  void (await import("tauri-plugin-mcp")).setupPluginListeners()
}
```

plus adding the npm dep (pin matching the Cargo rev) and either committing `dist-js/` in `psi-oss/tauri-plugin-mcp` or adding a `prepare` build script there.

## Troubleshooting

- **MCP socket missing** (`FileNotFoundError: /var/folders/.../tauri-mcp.sock`) — GPD isn't running, or you're running a release build (the plugin is gated behind `#[cfg(debug_assertions)]`). Launch a debug build.
- **AppleScript error -1719 / "not allowed assistive access"** — grant your terminal Accessibility permission.
- **`execute_js` timeouts** — known, see Phase 2 section above. Structural checks (menu bar, window geometry via MCP, `/global/health`) still pass.
- **Providers test skipped** — set `GPD_TEST_ANTHROPIC_KEY` and re-run.
- **`cliclick: command not found`** — `brew install cliclick`.
