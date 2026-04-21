# Audit: Smoke + Flows

## Smoke (Phase 1)

### Test files

- `test_artifacts.py` — exercises the on-failure artifact capture path directly (screenshot + `list_windows` JSON via MCP) and asserts both files land on disk with non-trivial byte size; it then deletes them. Does not rely on triggering a real failure.
- `test_first_run.py` — when the XDG-aware `.gpd-initialized` sentinel is absent, asserts the welcome-screen API-key prompt text appears in the DOM (via `execute_js`). Skips when the sentinel exists rather than deleting it.
- `test_launch.py` — two tests: GPD process is running (via `app_state.is_running()`) and the opencode-cli sidecar returns `healthy: true` plus a `version` string from `/global/health`.
- `test_mcp.py` — MCP smoke: `ping` returns success, and `list_windows` includes a window labeled `main`.
- `test_menu_bar.py` — asserts the top-level menu bar includes `File`, `Edit`, `View`, `Help` and an app-menu entry drawn from `{"GPD", "GPD Dev", "GPD Beta"}` (via AX).
- `test_providers.py` — marked `real_backend` and skipped unless `GPD_TEST_ANTHROPIC_KEY` is set; asserts `GET /config/providers` returns a dict with a non-empty providers entry.
- `test_release_no_mcp.py` — opt-in (`PYTEST_RELEASE_BUILD=1`) release-mode regression guards. (1) the MCP Unix socket must be absent under a release bundle id of `inc.psi.gpd`, (2) the frontend `dist/assets/*.js` must not contain the vendored tauri-plugin-mcp sentinels (`__TAURI_MCP_LISTENER_PATCH__`, `setupPluginListeners`).
- `test_restart.py` — marked `restart` (excluded by default via `-m "not steals_focus and not restart"`). Calls MCP `restart_app`, waits for the old PID to vanish, a new PID to appear, the socket to come back, a fresh MCP `ping`, and asserts `File > New Conversation`/`File > New Session` is reachable again via AX.
- `test_sidebar.py` — two tests: `File > New Conversation` (or the legacy `New Session`) menu item exists and is enabled via AX; the `SIDEBAR_NEW_SESSION` CSS selector is present in the webview DOM (via `execute_js`, skips if `execute_js` is unavailable).
- `test_window.py` — via MCP `list_windows`: the `main` window's title contains `"GPD"` and inner/outer size is at least 800x600. Deliberately avoids AX to prevent focus theft.

### Fixtures used

| Fixture | Scope | Source | What it provides |
|---|---|---|---|
| `app_state` | session | root `conftest.py` | `AppState` instance that launches GPD at session start (honors `PYTEST_COLD_START` to kill stale processes), waits for launch, optionally quits on `PYTEST_QUIT_GPD`. |
| `seed_onboarding_state` | session, autouse | root `conftest.py` | When `GPD_TEST_SEED_ONBOARDING=1` and `GPD_TEST_ANTHROPIC_KEY` are both set, writes `auth.json` (0o600) and the XDG-aware onboarding sentinel with backup/restore. Otherwise no-op. |
| `mcp` | function | root `conftest.py` | `MCPClient` bound to the live socket; if `ping` fails with auth-like errors, retries with a token from `scripts/discover_mcp_token`. |
| `ax` | function | root `conftest.py` | `AXClient` without eager `activate()` — does not steal focus. |
| `http` | function | root `conftest.py` | `HTTPClient` targeting the opencode-cli sidecar on `127.0.0.1:<port>`; discovers port via `lsof` on the sidecar PID, reads `OPENCODE_SERVER_USERNAME`/`OPENCODE_SERVER_PASSWORD` from the PID env via `ps -E`, then waits for `/global/health` to answer. |
| `os_input` | function | root `conftest.py` | `OSInputClient` (cliclick wrapper); skips if cliclick is missing. Not referenced by any smoke test. |

Marker-driven behavior (`pytest_runtest_setup`): the `tier(n)` and `fresh_app` markers trigger `scripts.reset.run(tier=..., start_app=True, stop_app=True)` before the test and then refresh `_session_app_state._launched_pid`. `fresh_app` aliases to tier 2.

### Product surface hit

- Launching GPD and observing the OS-level process is alive.
- Reading the main window title and size via MCP without activating.
- Hitting the opencode-cli sidecar's `/global/health` and `/config/providers` endpoints (the latter gated by real_backend).
- Pinging the MCP Unix socket and listing windows over MCP.
- Reading the top-level application menu bar via AX (File/Edit/View/Help and the app menu).
- Checking that `File > New Conversation`/`New Session` exists and is enabled via AX.
- Querying the webview DOM via `execute_js` for the welcome-screen prompt text and the sidebar new-session selector.
- Restarting the app end-to-end via MCP `restart_app` and verifying AX menu re-mount.
- Confirming absence of the MCP socket and absence of vendor-module sentinels in the release frontend bundle (security defense-in-depth).
- Writing a screenshot JPEG and windows JSON to the artifacts directory (capture harness self-check).

### Known gaps

Based on what's actually present:
- No smoke-level check that the **onboarding sentinel is absent** prevents a first-run regression in the already-onboarded path (the `test_first_run.py` path skips when the sentinel exists; there's no symmetric guard for the "sentinel present → home route loads" path).
- No smoke-level read of `current_url()` to confirm the webview landed on the expected post-launch route when the sentinel is present.
- No smoke assertion that the **sidecar version string** matches a build-expected value — only that it's a string.
- No smoke-level verification of a second window/panel, tray icon, or dock icon state.
- The `Edit > View > Help` menus are asserted to exist but no smoke test probes a single item inside them (e.g. `Edit > Copy`, `Help > About`).
- No smoke check for presence of the deep-link URL scheme registration (which is exercised only in flows under ambiguity-skip logic).
- The `os_input` fixture is defined but no smoke test uses it — no keyboard/mouse-level smoke check (e.g. Cmd+N dispatches).

## Flows (Phase 3)

### Test files

- `test_abort_flow.py` — starts a long generation on a background thread, waits ~2.5 s for tokens, calls `http.abort`, joins the thread within 15 s, and asserts partial output was captured and `"1000"` is not present (abort beat the model to 1000).
- `test_concurrent_sessions_flow.py` — creates two sessions, sends marker prompts in parallel on a `ThreadPoolExecutor`, waits up to 90 s per future, and asserts each session echoed its own marker and neither leaked into the other.
- `test_deep_link.py` — module-level autouse fixture skips when the `gpd://` URL scheme is plausibly registered by more than one bundle id (primary check via `lsregister -dump`, fallback heuristic via `/Applications/GPD.app` + running dev-build detection). When unambiguous: creates a session, shells out to `open gpd://session/<id>`, and polls `mcp.current_url()` for up to 10 s.
- `test_multi_turn_flow.py` — 3-turn conversation: plant fact `"octarine"` on turn 1, distract with `"What is 2+2?"` on turn 2, recall on turn 3. Asserts `>= 3` assistant turns and `"octarine"` appears in the final reply.
- `test_new_session.py` — creates a session scoped to a `scratch_project_dir`, sends `"Say hi."`, asserts shape-only (via `assert_assistant_replied`), then verifies the session is returned by both dir-scoped and unscoped `GET /session`, and message history has both a user and assistant role.
- `test_onboarding.py` — `real_backend` + `fresh_app` + destructive-opt-in (`PYTEST_RUN_DESTRUCTIVE_FLOWS=1`). Asserts tier-2 reset removed the sentinel, the welcome screen is visible via the `Onboarding` page object, pastes the API key, waits for home, and asserts both `auth.json` and the sentinel now exist.
- `test_provider_switch.py` — two tests. (1) shape round-trip on `GET /config/providers` (dict with `providers` list and `default` dict, first provider has `id` + `name`). (2) reads providers, skips if fewer than two are configured, confirms shape-stability across two reads, then `pytest.xfail`s because no safe dedicated write endpoint exists. Not marked `real_backend`.
- `test_theme_switch.py` — reads `localStorage["opencode-color-scheme"]` via DOM probe; if current value is null/`"dark"`/`"light"`, toggles to the opposite value and dispatches a `storage` event, asserts round-trip. Always restores the original value in a `finally`. Skips when a custom/system/auto value would be clobbered. Not marked `real_backend`.
- `test_tool_use_flow.py` — creates a temp file with a sentinel `"psi-marker-7f3a2b"`, opens a session scoped to its parent dir, asks the assistant to read the file and quote the sentinel, asserts the sentinel appears in the concatenated assistant text. `real_backend`.

### Real-backend coverage

| Test | `real_backend` | Skip/xfail behavior |
|---|---|---|
| `test_abort_flow.py::test_abort_stops_generation` | Yes | skipped without `GPD_TEST_ANTHROPIC_KEY` |
| `test_concurrent_sessions_flow.py::test_two_sessions_do_not_cross_contaminate` | Yes | skipped without `GPD_TEST_ANTHROPIC_KEY` |
| `test_multi_turn_flow.py::test_three_turn_context_retention` | Yes | skipped without `GPD_TEST_ANTHROPIC_KEY` |
| `test_new_session.py::test_new_session_send_prompt_assistant_replies` | Yes | skipped without `GPD_TEST_ANTHROPIC_KEY` |
| `test_onboarding.py::test_first_run_paste_key_reach_home` | Yes | also gated on `PYTEST_RUN_DESTRUCTIVE_FLOWS=1`; `fresh_app` reset |
| `test_tool_use_flow.py::test_assistant_reads_file_via_tool` | Yes | skipped without `GPD_TEST_ANTHROPIC_KEY` |
| `test_deep_link.py::test_deep_link_session_routes_to_session` | No | skipped on URL-scheme ambiguity; touches only sidecar + MCP |
| `test_provider_switch.py::test_provider_list_shape` | No | always live (pure read) |
| `test_provider_switch.py::test_default_provider_switch_write_path_not_yet_exposed` | No | skips when <2 providers configured; otherwise `xfail` |
| `test_theme_switch.py::test_theme_toggle_updates_local_storage` | No | skips if DOM probe unavailable or current value isn't null/"dark"/"light" |

No flow test is mocked — there are no stubs or fake LLM responses. Tests that don't need an LLM hit the real sidecar or the real webview directly.

### Product surface hit

- Creating, listing, and deleting sidecar sessions via `/session` and `/session/{id}`.
- Sending prompts via `POST /session/{id}/message` and reading history via `GET /session/{id}/message`.
- Aborting an in-flight generation via `POST /session/{id}/abort`.
- Running two sessions in parallel against the sidecar and checking context isolation.
- Dispatching a `gpd://session/<id>` URL through macOS `open` and observing the webview route change.
- Reading and writing `localStorage["opencode-color-scheme"]` via `execute_js` and dispatching a `storage` event.
- Reading `/config/providers` shape and comparing two sequential reads for stability.
- Driving the onboarding screen end-to-end (welcome → paste API key → home) through the `Onboarding` page object.
- Invoking a read-file tool via the assistant and checking the returned text quotes a disk sentinel.

### Known gaps

Based on what's actually present:
- The provider-switch write half is `xfail` — there is no flow exercising an actual default-provider change or its effect on `default` in `/config/providers`.
- No flow test validates `/session?directory=...` scoping on its own (`test_new_session.py` falls back to unscoped listing if scoped lookup returns empty, masking regressions).
- No flow test exercises cancellation via a UI button — abort is driven via HTTP only.
- No flow for **model switching mid-conversation** or for **agent switching** (`agent="default"` is always hardcoded).
- No flow asserting that **auth.json with a bad key** surfaces a recoverable error in the UI — onboarding only exercises the happy path.
- No flow test exercises deep-link routes other than `gpd://session/<id>` (e.g. `gpd://onboarding`, `gpd://` bare).
- Theme toggle only checks localStorage — nothing asserts the webview actually re-renders a dark/light class on `<html>` or equivalent.
- No flow covers **concurrent prompts within the same session** (only across separate sessions).
- No flow covers **attachment parts** (`type != "text"`) in `send_message`.
- Multi-turn test sleeps on model latency implicitly via the 60 s per-test timeout; no staged streaming assertion.

## Fixture architecture (smoke/flows-relevant)

The session-scoped `app_state` fixture owns GPD's lifecycle: it launches the app once, optionally kills stale processes first (`PYTEST_COLD_START=1`), and waits for it to reach a ready state; subsequent fixtures depend on it. `mcp` is function-scoped and builds an `MCPClient` against the Unix socket discovered under `/var/folders/*/*/T/tauri-mcp.sock` (overridable with `GPD_MCP_SOCKET`), retrying once with a discovered auth token if the initial `ping` fails with an auth-shaped error. `http` is function-scoped, waits for `app_state.sidecar_pid()` via `wait_until`, runs `discover_sidecar_port` (which `lsof`s the sidecar PID for a `127.0.0.1` LISTEN line and `ps -E`s the env for `OPENCODE_SERVER_USERNAME`/`PASSWORD`), builds an `HTTPClient` with those creds, then probes `/global/health` before yielding. The session-autouse `seed_onboarding_state` fixture, opted in via the paired `GPD_TEST_SEED_ONBOARDING=1` + `GPD_TEST_ANTHROPIC_KEY=<key>` envs, writes the XDG-aware `auth.json` (mode 0o600) and onboarding sentinel with backup-restore around the whole session — this is what lets smoke tests assume GPD is already onboarded. The flows-only `anthropic_key` fixture simply returns `GPD_TEST_ANTHROPIC_KEY` or skips, gating every `real_backend` flow; `scratch_project_dir` gives each flow test a `tmp_path_factory`-owned subdir so sidecar `directory` scoping is clean. `clean_onboarding_state` (aliased as `clean_auth_json`) backs up and removes both `auth.json` and the sentinel, restoring them on teardown — it pairs with `@pytest.mark.fresh_app` to force genuine first-run behavior in `test_onboarding.py`.

## Test count summary

- smoke: 10 files, 14 tests
- flows: 9 files, 10 tests
- total: 24 tests gated behind these markers
