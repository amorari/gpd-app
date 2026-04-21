# Audit: Harness Architecture

## Layered view

```
pages/ (high-level)
  ↓ uses
helpers/ (composition)
  ↓ uses
drivers/ (low-level: HTTP, MCP, AX, OS input)
```

Conceptually the harness is three concentric rings. Tests import from all three;
conftest assembles driver fixtures and thin helper/page wrappers live on top.

- `drivers/` wrap exactly one transport each (subprocess + osascript, Unix
  socket, HTTP, `cliclick`). They own no test-suite concepts.
- `helpers/` compose drivers into small utilities (DOM probes, route URLs,
  slow-mo waits, artifact sinks, tauri-IPC). They own no product-level nouns.
- `pages/` model application-level nouns (app lifecycle, welcome screen,
  menu bar) and may combine drivers + helpers.

## Drivers

### `gpd_tests/drivers/ax.py`

- **Responsibility:** macOS Accessibility (AXClient) via `osascript` + System
  Events. Activates the app, reads/clicks menu-bar items, and reads main
  window geometry.
- **Public API:**
  - `MenuItem` dataclass (exported, **unused elsewhere** — see dead code)
  - `AXClient(app_name=None)`
  - `.activate()`, `.top_level_menus()`, `.menu_item_exists()`,
    `.menu_item_enabled()`, `.click_menu_item()`, `.items_of()`,
    `.enabled_items_of()`, `.main_window()`
  - Module-private `_osascript()` and `_esc_as()` — imported by
    `helpers/sheet.py` (see coupling concerns)
- **External deps:** `subprocess`, `osascript`, `shutil.which`. No Python
  dependencies beyond stdlib.
- **Thread safety / lifecycle:** Stateless besides `self._app`. Each call
  spawns an `osascript` subprocess with a 10s default timeout; no persistent
  connection. `main_window()` steals focus via `.activate()`; every other
  method is focus-safe. No fixture-level lifecycle — constructed per test.

### `gpd_tests/drivers/mcp.py`

- **Responsibility:** Tauri MCP Unix-socket client. Line-delimited JSON over
  `AF_UNIX`. Provides a thin wrapper around every command the vendored
  tauri-plugin-mcp exposes.
- **Public API:**
  - `MCPError`, `MCPTimeout` exception classes
  - `MCPClient(socket_path=None, *, timeout_s=10.0, auth_token=None)`
  - `.ping()`, `.list_windows()`, `.take_screenshot()`,
    `.take_screenshot_bytes()`, `.reload()`, `.navigate()`, `.current_url()`,
    `.execute_js()`, `.restart_app()`
  - Module-private `_discover_socket_path()` — imported by
    `pages/app_state.py` (see coupling concerns)
- **External deps:** `socket`, `glob`, `uuid`, `json`. No 3rd-party libs.
- **Thread safety / lifecycle:** One-shot sockets — each `_call` opens,
  writes, reads one line, closes. The client itself is effectively stateless
  between calls, so it can be reused across the test run. Auth token is
  captured at construction; to rotate, reconstruct.

### `gpd_tests/drivers/opencode_http.py`

- **Responsibility:** HTTP client for the `opencode-cli` sidecar (basic-auth
  over `127.0.0.1`). Also provides two module-level helpers that discover the
  sidecar's port and env-baked credentials.
- **Public API:**
  - `HTTPClient(base_url, username, password, transport=None, timeout_s=120.0)`
    — context manager, `.close()`
  - Reads: `.health()`, `.sessions(directory=…)`, `.providers()`,
    `.path_info()`, `.messages(session_id)`
  - Writes: `.create_session(directory=…, parent_id=…)`, `.send_message(…)`,
    `.abort(session_id)`, `.delete_session(session_id)`
  - Module fns: `discover_sidecar_port(pid=…, timeout_s=…)`,
    `discover_sidecar_credentials(pid)`
- **External deps:** `httpx`, plus `subprocess` for `pgrep` / `lsof` / `ps`.
- **Thread safety / lifecycle:** Each `HTTPClient` owns an `httpx.Client`
  that must be closed (context manager handles it); the root conftest yields
  and closes. `discover_sidecar_port` retries with PID revalidation to
  survive sidecar respawn.

### `gpd_tests/drivers/os_input.py`

- **Responsibility:** Real OS input — mouse via `cliclick`, keystrokes via
  `osascript`.
- **Public API:** `OSInputClient()` → `.click(x, y)`, `.move(x, y)`,
  `.type_text(text)`, `.press_key(key)`.
- **External deps:** `subprocess`, `cliclick` (brew), `osascript`.
- **Thread safety / lifecycle:** Stateless. Constructor raises if `cliclick`
  or `osascript` aren't on PATH, so the fixture can `pytest.skip` when the
  dev box isn't provisioned.

## Helpers

### `gpd_tests/helpers/artifacts.py`

- **Responsibility:** Failure-time artifact capture. Provides a
  `<tests-gui>/artifacts/<module>/<test>/` directory and typed writers.
- **Public API:** `DEFAULT_ROOT` constant, `artifact_dir(module, test, *, root)`,
  `save_json`, `save_text`, `save_bytes`.
- **External deps:** stdlib only (`json`, `time`, `pathlib`).
- **Thread safety / lifecycle:** Filesystem-only; collision suffix uses UTC
  timestamp so reruns don't silently overwrite.
- **Consumers:** Root `conftest.py` (screenshot/window/triage hints on
  failure); unit + smoke tests of the helper itself.

### `gpd_tests/helpers/dom_probe.py`

- **Responsibility:** Wrap `MCPClient.execute_js` so bridge flakiness
  surfaces as a `ProbeSkip` exception (tests catch and `pytest.skip`) instead
  of a hard error.
- **Public API:** `ProbeSkip` exception, `DOMProbe(mcp)` with `.eval(code)`,
  `.eval_bool(code)`, `.eval_json(code)`, `.eval_int(code)`.
- **External deps:** `gpd_tests.drivers.mcp` (for `MCPError`/`MCPTimeout`
  types only — duck-typed Protocol used for the client itself).
- **Thread safety / lifecycle:** Stateless holder over a passed-in MCP.
- **Consumers:** `pages/onboarding.py`, several surface tests, smoke tests.
  Note: `.eval_json()` and `.eval_int()` currently have **no consumers**.

### `gpd_tests/helpers/i18n.py`

- **Responsibility:** Read the committed en.json snapshot at
  `gpd_tests/fixtures/en.json` and look up keys.
- **Public API:** `t(key)`, `all_keys()`.
- **External deps:** `json`, `functools.lru_cache`. Purely filesystem.
- **Thread safety / lifecycle:** Cached-once dictionary for the process.
- **Consumers:** `helpers/selectors.py` (for `_safe(key, fallback)`) and the
  unit test; no production test imports `t` directly today.

### `gpd_tests/helpers/ipc.py`

- **Responsibility:** Invoke a Tauri command through MCP `execute_js` by
  wrapping `window.__TAURI_INTERNALS__.invoke` in an async IIFE and decoding
  the JSON result. Error promise-rejections surface as `IPCError`.
- **Public API:** `IPCError`, `invoke_via_mcp(mcp, command, args=None, *, window_label='main')`.
- **External deps:** `json`; Protocol-typed against anything with an
  `execute_js` method.
- **Thread safety / lifecycle:** Stateless function.
- **Consumers:** Every `tests/ipc/*.py` test module (tauri-command tests) and
  the `test_helpers_ipc` unit test.

### `gpd_tests/helpers/llm_tolerant.py`

- **Responsibility:** Shape-level assertions over assistant messages — no
  content matching, so real-LLM variance doesn't flake tests.
- **Public API:** `assistant_text(response)`, `assert_assistant_replied(response)`.
- **External deps:** None.
- **Thread safety / lifecycle:** Pure functions.
- **Consumers:** `tests/flows/test_new_session.py`, `test_tool_use_flow.py`,
  `test_abort_flow.py`, `test_concurrent_sessions_flow.py`, and the unit test.

### `gpd_tests/helpers/navigator.py`

- **Responsibility:** Build `tauri://localhost/...` URLs and drive the
  webview to them, polling `current_url()` until it matches
  (trailing-slash / query / hash tolerant).
- **Public API:** `BASE` constant, `encode_dir_token(path)`, `route_home()`,
  `route_loading()`, `route_project(path)`, `route_session(id=None)`
  (**deprecated**), `route_session_in_project(dir_token, id=None)`,
  `Navigator(mcp)` with `.go(url, *, timeout_s, poll_s)`.
- **External deps:** `base64`, `urllib.parse`; Protocol against MCP.
- **Thread safety / lifecycle:** Navigator is a stateless wrapper; all
  `route_*` functions are pure.
- **Consumers:** All `tests/surfaces/*.py`, `tests/flows/test_deep_link.py`,
  and the unit test.

### `gpd_tests/helpers/selectors.py`

- **Responsibility:** Canonical CSS selectors and user-facing text
  constants. Text constants fall back on a fixed default if the i18n key is
  absent so the constant is always safe to import.
- **Public API:** `SIDEBAR_*` selector strings, `kobalte(component, slot=None)`,
  `TEXT_WELCOME_*`, `TEXT_PROMPT_PLACEHOLDER`, `TEXT_SIDEBAR_*`.
- **External deps:** `helpers.i18n`.
- **Thread safety / lifecycle:** Module-level constants resolved once at import.
- **Consumers:** `pages/onboarding.py`, smoke tests, surface tests, the unit test.

### `gpd_tests/helpers/sheet.py`

- **Responsibility:** Detect native macOS sheets on GPD's first window
  without activating the app.
- **Public API:** `has_native_sheet(app_name='GPD')`.
- **External deps:** Reaches into **`gpd_tests.drivers.ax._osascript`** — the
  module-private runner. See coupling concerns.
- **Thread safety / lifecycle:** Stateless.
- **Consumers:** Only the unit test (`tests_unit/test_helpers_sheet.py`).

### `gpd_tests/helpers/timings.py`

- **Responsibility:** Test-wide waiting primitives. `slowmo_ms` / `slowmo_sleep`
  implement a per-action slow-motion knob driven by `PYTEST_SLOWMO_MS` /
  `PYTEST_CI`. `wait_until` polls a predicate to a deadline.
- **Public API:** `slowmo_ms()`, `slowmo_sleep()`, `wait_until(predicate, *, timeout_s, poll_s=0.1, reraise_on_timeout=False)`.
- **External deps:** `os`, `time`.
- **Thread safety / lifecycle:** Pure / single-thread polling.
- **Consumers:** Root `conftest.py`, `pages/app_state.py`, multiple tests.

## Pages

### `gpd_tests/pages/app_state.py`

- **Responsibility:** GPD application lifecycle — running?, launch, quit,
  wait-for-ready, kill-stale (SIGTERM → SIGKILL with bounded wait), PPID
  tracking so `sidecar_pid()` doesn't latch onto an unrelated `opencode-cli`.
  Resolves `GPD_APP_PATH` and derives the AX/pgrep name from it.
- **Public API:** `APP_PATH` constant, `AppState()` with `.is_running()`,
  `.gpd_pid()`, `.sidecar_pid()`, `.kill_stale()`, `.launch(background=True)`,
  `.quit()`, `.refresh_launched_pid()`, `.wait_launched(timeout_s=20.0)`,
  `.wait_quit(timeout_s=10.0)`.
- **External deps:** `subprocess` (pgrep/kill/osascript), `os.kill`/`signal`;
  imports the module-private `_discover_socket_path` from `drivers.mcp`;
  imports `helpers.timings.wait_until`. `wait_launched` also imports
  `MCPClient` at call time to ping-probe readiness.
- **Thread safety / lifecycle:** Session-scoped in the root conftest. Tracks
  the PID of the GPD process it launched so `sidecar_pid()` can PPID-filter;
  `refresh_launched_pid()` rebinds after an out-of-band restart.

### `gpd_tests/pages/menu.py`

- **Responsibility:** Higher-level iterator over the menu bar — filters the
  implicit Apple menu, yields `(menu, item)` pairs, and has an
  `enabled_pairs()` variant.
- **Public API:** `Menu(ax)`, `.SYSTEM_MENUS`, `.top_level()`, `.pairs()`,
  `.enabled_pairs()`.
- **External deps:** `drivers.ax.AXClient` (injected).
- **Thread safety / lifecycle:** Stateless wrapper.
- **Consumers:** **None.** No test imports `pages.menu`; the broad tests
  call `AXClient` directly. See dead code.

### `gpd_tests/pages/onboarding.py`

- **Responsibility:** Welcome-screen probe and driver. Reads `XDG_CONFIG_HOME`
  to find the sentinel file, probes the DOM for the welcome-title text,
  drives the API-key input + submit via JS, and waits for the sentinel +
  welcome-hidden transition.
- **Public API:** `sentinel_path()`, `Onboarding(mcp)` with
  `.sentinel_present()` (staticmethod), `.welcome_visible()`,
  `.enter_api_key(key)`, `.wait_for_home(timeout_s=20.0)`.
- **External deps:** `helpers.dom_probe.DOMProbe` / `ProbeSkip`;
  `helpers.selectors.TEXT_WELCOME_*` (lazily imported inside methods).
- **Thread safety / lifecycle:** Stateless wrapper around MCP.
- **Consumers:** `tests/flows/test_onboarding.py`,
  `tests/smoke/test_first_run.py`, root `conftest.py` uses
  `sentinel_path()`.

## Coupling concerns

1. **`helpers/sheet.py` → `drivers/ax._osascript` (private import).** The
   helper imports the module-private `_osascript` runner rather than going
   through `AXClient`. This couples a helper to a driver's internals — if
   `drivers/ax.py` ever renames `_osascript` (or changes the escaping
   convention), `sheet.py` silently breaks. Preferred fix: expose a public
   `run_applescript(...)` on `AXClient` or a new `drivers/applescript.py`
   module, then have `sheet.py` consume that.

2. **`pages/app_state.py` → `drivers/mcp._discover_socket_path` (private import).**
   Same pattern: the page reaches into a private driver symbol. Consumers
   in tests go through `MCPClient(socket_path=None)` which already handles
   discovery; `app_state` would be cleaner if it either constructed an
   `MCPClient` directly (which it already does inside `wait_launched`) or
   if `_discover_socket_path` were made public.

3. **Driver construction duplicated.** `AppState.wait_launched` imports
   `MCPClient` inline to ping for readiness; the fixture in
   `conftest.py::mcp` does the ping+auth-fallback dance again. The page and
   the fixture would be easier to keep in sync if the auth-token discovery
   plus ping were encapsulated in a helper (e.g. `helpers/mcp_ready.py`).

4. **`conftest.py::mcp` reaches into `scripts.discover_mcp_token`.** Not a
   layering violation exactly (the top-level `scripts/` directory is
   sibling to `gpd_tests/`), but it's a second out-of-package dependency
   that the harness fixtures import at call time. Documented here for
   visibility — the path insertion in `conftest.py` makes it work, and it
   is functionally necessary.

No strict layering violations were found beyond (1) and (2). Helpers do
not reach into pages; tests reach across all three layers but that's by
design.

## Obsolete / dead code

- **`gpd_tests/pages/menu.py`** — the `Menu` class has **no callers**.
  `tests/broad/test_menu_*.py` all use `AXClient` directly. The
  `full-coverage-phase` plan even lists `pages/menu.py` as a zero-coverage
  module. Candidate for deletion or adoption by the broad tests.

- **`gpd_tests.drivers.ax.MenuItem` dataclass** — defined but never
  instantiated, imported, or referenced outside its own declaration.

- **`gpd_tests.helpers.navigator.route_session`** — docstring marks it
  deprecated; only the unit test references it. SPA no longer exposes
  top-level `/session`. Ready to remove once the unit test is pruned.

- **`gpd_tests.helpers.dom_probe.DOMProbe.eval_json`** and **`.eval_int`** —
  no call sites in tests. Either drop or add usage; they are small but add
  API surface that must be kept working.

- **`gpd_tests.helpers.i18n.t`** direct consumers — `t()` is only used from
  `helpers/selectors.py::_safe`; no test calls `t` directly despite the
  public export. `all_keys()` is only called from the unit test. Not urgent
  but a signal the surface is wider than needed.

- **`tests/flows/conftest.py::clean_auth_json`** alias — kept as a
  backwards-compat name for `clean_onboarding_state`. No grep hit outside
  the conftest itself and a plan file; can be removed after confirming no
  in-flight branches reference it.

- **Test-code reference mismatch (not harness code, but surfaced by this
  audit):** `tests_unit/test_driver_http.py::test_path_info_malformed_json_raises`
  calls `c.path_info(directory="/tmp")`, but `HTTPClient.path_info()` takes
  no arguments. The test still "passes" because `pytest.raises(Exception)`
  catches the resulting `TypeError`, but it is not exercising the code
  path the docstring claims.

## Fixtures surface (from conftest.py files)

### Root `packages/desktop/tests-gui/conftest.py`

Session-wide plumbing for the whole suite.

- `pytest_configure` — bails out if `pytest-xdist` parallelism is requested.
- `seed_onboarding_state` *(session, autouse)* — opt-in seeding of
  `auth.json` + the onboarding sentinel gated on
  `GPD_TEST_SEED_ONBOARDING=1` + `GPD_TEST_ANTHROPIC_KEY`; backs up and
  restores.
- `app_state` *(session)* — builds `AppState`, optionally `kill_stale` in
  `PYTEST_COLD_START=1`, launches if needed, `wait_launched`, yields;
  quits on teardown if `PYTEST_QUIT_GPD=1`.
- `mcp` *(function)* — `MCPClient()`, pings; on an auth-like error,
  resolves a token via `scripts.discover_mcp_token` and reconstructs.
- `ax` *(function)* — `AXClient()` without eager `activate()` (keeps
  focus with the caller).
- `http` *(function)* — waits for sidecar PID, discovers port + creds
  via `ps`/`lsof`, probes `/global/health`, yields `HTTPClient`, closes.
- `os_input` *(function)* — constructs `OSInputClient` or `pytest.skip`
  if `cliclick` missing.
- `pytest_runtest_setup` — marker-driven resets: `@pytest.mark.tier(n)` /
  `@pytest.mark.fresh_app` (alias for tier 2) invoke `scripts.reset.run`
  and then `wait_launched` + `refresh_launched_pid`.
- `pytest_runtest_makereport` — on failure: writes screenshot + windows
  JSON to `artifacts/`, plus an optional `triage_gate4` markdown hint
  listing product commits in the last 24 h.
- `pytest_report_header` — prints slow-mo and CI flags.

### Flow conftest `tests/flows/conftest.py`

Function-scoped per-flow helpers.

- `scratch_project_dir` — unique `tmp_path_factory` subdir; directory
  scope for `/session?directory=…`.
- `anthropic_key` — read `GPD_TEST_ANTHROPIC_KEY` or skip (gate for
  `@pytest.mark.real_backend`).
- `auth_json_path` — `~/.local/share/opencode/auth.json` Path.
- `clean_onboarding_state` — back up + delete `auth.json` and the
  sentinel, restore on teardown.
- `clean_auth_json` — backwards-compat alias for `clean_onboarding_state`.

### Lifecycle conftest `tests/lifecycle/conftest.py`

Empty — only a module docstring and `import pytest`. Present as an
anchor so pytest treats the subdirectory as a collection root; no
fixtures exposed today.

### Surface conftest `tests/surfaces/conftest.py`

- `nav(mcp)` → `Navigator(mcp)`.
- `dom(mcp)` → `DOMProbe(mcp)`.

### Broad conftest `tests/broad/conftest.py`

Docstring-only — no fixtures.

### Harness-selftest conftest `tests/harness_selftest/conftest.py`

- `tests_root` *(session)* — path to the tests-gui root; intentionally
  lightweight so this suite runs even when other harness pieces are
  broken.

### Unit conftest `tests_unit/conftest.py`

- `fake_mcp_socket` — factory that spins up an `AF_UNIX` server thread
  with a caller-supplied handler, returns the path; cleans up threads
  and socket files on teardown. Used by MCP driver unit tests to avoid
  depending on a live GPD.
