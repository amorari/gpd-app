# Audit: Unit tests (tests_unit/)

## Inventory

| Test file | Target module | # tests | Coverage notes |
|---|---|---|---|
| `test_app_state.py` | `gpd_tests/pages/app_state.py` | 2 | `is_running()` only; pgrep true/false paths |
| `test_driver_ax.py` | `gpd_tests/drivers/ax.py` | 9 | Menu-introspection, geometry parser, separator filtering, AppleScript escaping |
| `test_driver_http_abort.py` | `gpd_tests/drivers/opencode_http.py` | 1 | `abort()` endpoint shape |
| `test_driver_http_session.py` | `gpd_tests/drivers/opencode_http.py` | 9 | Session CRUD: create/send/messages/delete incl. 204, parent-id, model-object, directory-as-query |
| `test_driver_http.py` | `gpd_tests/drivers/opencode_http.py` | 12 | Health, sessions, providers shape, 401/500 error paths, send_message body, malformed JSON |
| `test_driver_mcp.py` | `gpd_tests/drivers/mcp.py` | 13 | Full wire protocol: ping, list_windows, take_screenshot, navigate, current_url, execute_js (+unwrap/timeout), error envelope, authToken field, list_windows unwrap |
| `test_driver_os_input.py` | `gpd_tests/drivers/os_input.py` | 3 | `click()`, `type_text()` escaping, `press_key("escape")` |
| `test_flakiness_report.py` | `scripts/flakiness/report.py` | 5 | `aggregate()` stable/flaky/broken buckets, error-as-failure, `to_markdown()` |
| `test_helpers_artifacts.py` | `gpd_tests/helpers/artifacts.py` | 4 | `artifact_dir()` + `save_{json,text,bytes}` |
| `test_helpers_dom_probe.py` | `gpd_tests/helpers/dom_probe.py` | 9 | `eval`, `eval_bool` (truthy/falsy coverage), ProbeSkip on timeout/None, MCPError re-raise |
| `test_helpers_i18n.py` | `gpd_tests/helpers/i18n.py` | 3 | `t()` hit/miss, `all_keys()` size check |
| `test_helpers_ipc.py` | `gpd_tests/helpers/ipc.py` | 6 | `invoke_via_mcp()` JS body, JSON parse, tauri error, null result, non-JSON error, window_label kwarg |
| `test_helpers_llm_tolerant.py` | `gpd_tests/helpers/llm_tolerant.py` | 7 | `assert_assistant_replied` shape checks (role/empty/tool-use-only/non-dict/error envelope), `assistant_text()` concat |
| `test_helpers_navigator.py` | `gpd_tests/helpers/navigator.py` | 4 | `encode_dir_token`, route builders, `Navigator.go()` happy path + timeout |
| `test_helpers_selectors.py` | `gpd_tests/helpers/selectors.py` | 3 | data-action constants, `kobalte()` builder, i18n-constant drift guard |
| `test_helpers_sheet.py` | `gpd_tests/helpers/sheet.py` | 3 | `has_native_sheet()` count>0/==0/error |
| `test_helpers_timings.py` | `gpd_tests/helpers/timings.py` | 4 | `slowmo_ms` env/CI/default, `wait_until` pass/timeout |
| `test_refresh_en_dict.py` | `scripts/refresh_en_dict.py` | 10 | UTF-8 round-trip, JS-escape materialization, backslash order, single/double/multiline parse shapes |
| `test_scripts_reset.py` | `scripts/reset.py` | 5 | `paths_for_tier(1/2/3)`, dry-run, file removal |
| `test_tauri_commands_catalog.py` | `scripts/extract_tauri_commands.py` + `fixtures/tauri_commands.json` | 2 | Catalog freshness, min file count |
| `test_triage_gate4.py` | `scripts/triage_gate4.py` | 3 | `find_related_commits()` git-log parse, empty, path passthrough |
| **Total** | | **117** | |

## Coverage matrix — gpd_tests/ → tests_unit/

### drivers/

- **`mcp.py`** — **Y** — `test_driver_mcp.py`
  - Covered: socket round-trip (via `fake_mcp_socket` conftest fixture), id-as-string + payload required, `ping`, `list_windows` (list + dict-wrapped), `take_screenshot` (data URI), `reload`, `navigate`, `current_url`, `execute_js` (+ dict-result unwrap, timeout surfacing), error-envelope → `MCPError`, `authToken` field name.
  - NOT covered: `take_screenshot_bytes` (base64 decode), `restart_app`, `_discover_socket_path` (env-override and glob fallback branches, `FileNotFoundError` path), `MCPTimeout` raised from the socket-timeout branch (only the "empty response" variant is exercised), multi-line buffer reads on `_call`, auth token absent + server requires it (e.g., forbidden/unauthorized error mapping beyond generic `MCPError`), concurrent client safety.

- **`opencode_http.py`** — **Y** — `test_driver_http.py`, `test_driver_http_session.py`, `test_driver_http_abort.py`
  - Covered: `health`, `sessions` (no-directory), `providers` (correct + wrong shape guard), 401/500 error paths, `send_message` (body/model nested object/agent/flat-keys guard), `create_session` (directory as query param, `parentID` camelcase), `messages`, `delete_session` (truthy and 204), `abort`, `path_info` malformed-JSON.
  - NOT covered: `sessions(directory=...)` query-param path, `path_info` success path, `discover_sidecar_port` (retry/pid-alive logic, `_probe_port_once`, `lsof` parsing), `discover_sidecar_credentials` + `_extract_env`, `_pid_alive` subprocess interaction, `send_message` `ValueError` when `model_id XOR provider_id`, non-JSON-but-non-empty response in `_post`, timeout handling (no slow-server test).

- **`os_input.py`** — **Y** — `test_driver_os_input.py`
  - Covered: `click` args, `type_text` escapes quotes, `press_key("escape")` uses correct key code.
  - NOT covered: `move()` (no test at all), constructor's `cliclick`/`osascript` missing-binary error branches (one is monkeypatched away; the negative paths are never asserted), `type_text` `ValueError` on `\n`/`\r`, other key codes (return/tab/space/delete/arrows), subprocess `TimeoutExpired` and `CalledProcessError` re-raise paths (all 3 public methods have these branches; none tested).

- **`ax.py`** — **Y** — `test_driver_ax.py`
  - Covered: `top_level_menus` parse, `menu_item_exists` applescript shape, `main_window` geometry parse + comma-in-title, `items_of` with `missing value` filtered + AppleScript injection escaping, `enabled_items_of` with separator positional zip.
  - NOT covered: `activate()` direct test, `menu_item_enabled`, `click_menu_item`, `top_level_menus` "Apple" filtering, `_default_app_name` (env override vs. default), `_osascript` failure path (non-zero returncode → RuntimeError), `main_window` retry loop when window count stays 0 for all 20 polls, `_raw_items_of` returning `None` on failure.

### helpers/

- **`artifacts.py`** — **Y** — `test_helpers_artifacts.py`
  - Covered: `artifact_dir` creates nested path, `save_json`/`save_text`/`save_bytes` roundtrip.
  - NOT covered: collision path (existing dir with files → timestamp suffix), `DEFAULT_ROOT` resolution, UTF-8 encoding in `save_json`/`save_text`, `default=str` fallback for non-JSON-serializable values.

- **`dom_probe.py`** — **Y** — `test_helpers_dom_probe.py`
  - Covered: happy `eval`, `MCPTimeout`→`ProbeSkip`, `MCPError` with timeout hint→`ProbeSkip` vs. re-raise, `eval_bool` truthy/falsy (incl. full JS-falsy set), `eval`/`eval_bool` None handling.
  - NOT covered: `eval_json` (success + ProbeSkip-on-None), `eval_int` (success + ProbeSkip-on-None), all `_TIMEOUT_HINTS` variants besides "timeout" (`peer closed`, `channel closed`, `connection reset`, `bridge`, `webview not ready`).

- **`i18n.py`** — **Y** — `test_helpers_i18n.py`
  - Covered: known-key hit, missing-key KeyError, `all_keys()` length + sample lookups.
  - NOT covered: `_load` cache behavior, missing fixture file, malformed JSON fixture.

- **`ipc.py`** — **Y** — `test_helpers_ipc.py`
  - Covered: JS composition, JSON parse, `__tauri_error__`→IPCError, null result, non-JSON response→IPCError, `window_label` kwarg passthrough.
  - NOT covered: args default (None→`{}`) explicit test, `_MCPLike` protocol runtime check, complex nested args JSON encoding.

- **`llm_tolerant.py`** — **Y** — `test_helpers_llm_tolerant.py`
  - Covered: valid response, missing role, empty text rejection, tool-use-only pass, non-dict input, error envelope (`error`/nested `info.error`), `assistant_text` concat filtering non-text parts.
  - NOT covered: `_MAX_REPR` truncation behavior in error messages, `parts=None` (only empty list tested), non-string text values in parts.

- **`navigator.py`** — **Y** — `test_helpers_navigator.py`
  - Covered: `encode_dir_token` base64url no-pad, all `route_*` builders, `Navigator.go` polling success + timeout.
  - NOT covered: `route_loading` (deprecated warning sentinel), `route_session_in_project` (the non-deprecated helper), `_urls_match` trailing-slash/hash/query-param-order tolerance (only called transitively via `Navigator.go`), ValueError fallback in `_urls_match`, `current_url` exception swallow in `go`.

- **`selectors.py`** — **Y** — `test_helpers_selectors.py`
  - Covered: data-action constants, `kobalte()` with/without slot, TEXT_* constants equal dict entries (drift guard).
  - NOT covered: `_safe` fallback branch (only the happy path is asserted via the drift check; the KeyError→fallback path is dead in current en.json).

- **`sheet.py`** — **Y** — `test_helpers_sheet.py`
  - Covered: count>0→True, count==0→False, exception→False.
  - NOT covered: non-numeric osascript output (e.g., `""`→returns False via the `isdigit()` guard), default `app_name="GPD"` vs. custom.

- **`timings.py`** — **Y** — `test_helpers_timings.py`
  - Covered: `slowmo_ms` env / CI-flag / local-default, `wait_until` pass + timeout.
  - NOT covered: `slowmo_ms` with invalid env value (→0), `slowmo_sleep` (no direct test), `wait_until` `reraise_on_timeout=True` path, predicate-raises-exception-but-passes-later path.

### pages/

- **`app_state.py`** — **partial** — `test_app_state.py`
  - Covered: `is_running()` (pgrep stdout populated / empty).
  - NOT covered: `gpd_pid`, `sidecar_pid` (inc. PPID filtering, `_launched_pid` tracking, "return None rather than unrelated sidecar" branch), `kill_stale` (SIGTERM→SIGKILL escalation, `TimeoutError` when processes refuse to die), `launch` (subprocess open, wait_until, failure RuntimeError), `quit`, `refresh_launched_pid`, `wait_launched` (socket discovery + ping + auth-tolerant readiness), `wait_quit`, `_default_app_path` env handling, `_pgrep` helper, `_PGREP_PATTERN` derivation for `GPD Dev` bundle.

- **`menu.py`** — **N** — no unit tests
  - NOT covered: `Menu.top_level()` (SYSTEM_MENUS filter), `pairs()`, `enabled_pairs()` iterators. These are thin passthroughs to `AXClient` but the Apple-filter contract is untested.

- **`onboarding.py`** — **N** — no unit tests
  - NOT covered: `sentinel_path()` (XDG_CONFIG_HOME override vs. default), `Onboarding.sentinel_present` static, `welcome_visible` (JS composition, ProbeSkip→False), `enter_api_key` (JS quoting, placeholder escaping, result-shape handling, mismatch RuntimeError), `wait_for_home` (poll + sentinel + welcome combo, TimeoutError). No mock-based tests despite most logic being JS-string construction + branching on DOMProbe returns.

## Scripts coverage

| Script file | Has unit tests | Test file | What's covered |
|---|---|---|---|
| `scripts/__init__.py` | N/A | — | empty package init |
| `scripts/_bundle.py` | **N** | — | `app_name()` (env override vs. default), `bundle_id()` for GPD/Dev/Beta and the unknown-name fallback — all untested |
| `scripts/discover_mcp_token.py` | **N** | — | `discover()` env-var / file / log fallback; `_token_paths`, `_log_dir`, `_discover_from_logs` regex — all untested (module marked "dead code in production") |
| `scripts/extract_tauri_commands.py` | **partial** | `test_tauri_commands_catalog.py` | Catalog freshness (re-runs script and diffs against fixture) and min file count. `extract()` regex is not unit-tested directly — no tests for attribute-stack, `pub`/`async` toggles, or signature capture edge cases. |
| `scripts/refresh_en_dict.py` | **Y** | `test_refresh_en_dict.py` | `_unescape_js_string` UTF-8 round-trip + escape materialization + backslash order, `parse_en_ts` single/double/multiline/mixed/UTF-8/embedded-newline. NOT covered: `main()` CLI entrypoint, file-read error handling, writing output. |
| `scripts/reset.py` | **Y** | `test_scripts_reset.py` | `paths_for_tier(1/2/3)` + superset invariant + sentinel; `run()` dry-run + removal. NOT covered: `stop_app`/`start_app` branches, tier-0 behavior, permission errors on delete, non-existent tier values, re-launch failure. |
| `scripts/triage.py` | **N** | — | `run_pytest_once` subprocess wrapper and `main()` gate logic (flaky/passing/regression/harness-bug classification) — all untested |
| `scripts/triage_gate4.py` | **Y** | `test_triage_gate4.py` | `find_related_commits` parse + empty + path passthrough. NOT covered: `main()` CLI entry, non-zero git exit, `repo_root` override. |
| `scripts/flakiness/__init__.py` | N/A | — | empty |
| `scripts/flakiness/report.py` | **Y** | `test_flakiness_report.py` | `aggregate()` stable/flaky/broken incl. error-as-failure, `to_markdown()` counts. NOT covered: `main()` CLI, empty-dir input, malformed XML, `total_runs=0` div-by-zero-like paths. |
| `scripts/run_coverage.sh` | N/A | — | shell script, not Python |

## Test count: 117 (confirmed via `uv run pytest tests_unit -q`)
