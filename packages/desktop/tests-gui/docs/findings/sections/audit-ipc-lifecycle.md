# Audit: IPC + Lifecycle

Scope: `packages/desktop/tests-gui/tests/ipc/` (Phase B, 7 test files) and
`packages/desktop/tests-gui/tests/lifecycle/` (Phase D, 3 test files + conftest),
cross-referenced against the 28-command catalog at
`packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json` and the
`invoke_via_mcp` helper at `packages/desktop/tests-gui/gpd_tests/helpers/ipc.py`.

The helper wraps `window.__TAURI_INTERNALS__.invoke(cmd, args)` in an async
IIFE, serializes the result to JSON, and normalises rejections into `IPCError`
with shape `{"__tauri_error__": message}` so `execute_js` never times out on a
thrown Promise. Every IPC test goes through this single chokepoint.

## IPC contract tests (Phase B)

### Coverage matrix

All 28 catalog commands have at least one direct contract test, and every
command is additionally swept by the parametrized `test_ipc_negative.py`
bogus-arg-shape test.

| # | Command | Rust file | Test file | Direct tests | Covered? |
|---|---------|-----------|-----------|-------------:|----------|
| 1 | `install_cli` | `cli.rs` | `test_tectonic_markdown_cli.py` | 1 | yes (platform-gated) |
| 2 | `install_git_macos` | `dependencies.rs` | `test_dependencies.py` | 1 | yes (platform-gated) |
| 3 | `install_git_windows` | `dependencies.rs` | `test_dependencies.py` | 1 | yes (platform-gated) |
| 4 | `linux_install_hint` | `dependencies.rs` | `test_dependencies.py` | 6 (5 parametrized + 1 unknown) | yes |
| 5 | `repair_gpd_venv` | `gpd_setup.rs` | `test_lib_commands.py` | 1 (skipped) | enumerated only |
| 6 | `kill_sidecar` | `lib.rs` | `test_lib_commands.py` | 1 (skipped) | enumerated only |
| 7 | `await_initialization` | `lib.rs` | `test_lib_commands.py` | 1 | yes (missing-arg only) |
| 8 | `check_app_exists` | `lib.rs` | `test_lib_commands.py` | 2 | yes |
| 9 | `resolve_app_path` | `lib.rs` | `test_lib_commands.py` | 1 | yes |
| 10 | `open_path` | `lib.rs` | `test_lib_commands.py` | 1 | yes (error-path only) |
| 11 | `get_display_backend` | `lib.rs` | `test_lib_commands.py` | 1 | yes |
| 12 | `set_display_backend` | `lib.rs` | `test_lib_commands.py` | 1 (roundtrip) | yes |
| 13 | `wsl_path` | `lib.rs` | `test_lib_commands.py` | 2 | yes |
| 14 | `parse_markdown_command` | `markdown.rs` | `test_tectonic_markdown_cli.py` | 2 | yes |
| 15 | `create_project_directory` | `project_fs.rs` | `test_project_fs.py` | 2 | yes |
| 16 | `check_project_accessible` | `project_fs.rs` | `test_project_fs.py` | 2 | yes |
| 17 | `get_default_server_url` | `server.rs` | `test_server.py` | 1 | yes |
| 18 | `set_default_server_url` | `server.rs` | `test_server.py` | 2 | yes |
| 19 | `get_wsl_config` | `server.rs` | `test_server.py` | 1 | yes |
| 20 | `set_wsl_config` | `server.rs` | `test_server.py` | 2 | yes |
| 21 | `install_tectonic` | `tectonic.rs` | `test_tectonic_markdown_cli.py` | 1 | yes |
| 22 | `detect_tex_root` | `tex_compiler.rs` | `test_tex_compiler.py` | 2 | yes |
| 23 | `detect_tex_compiler` | `tex_compiler.rs` | `test_tex_compiler.py` | 1 | yes |
| 24 | `compile_tex` | `tex_compiler.rs` | `test_tex_compiler.py` | 2 | yes |
| 25 | `synctex_forward` | `tex_compiler.rs` | `test_tex_compiler.py` | 1 | yes |
| 26 | `synctex_reverse` | `tex_compiler.rs` | `test_tex_compiler.py` | 1 | yes |
| 27 | `read_tex_artifact_base64` | `tex_compiler.rs` | `test_tex_compiler.py` | 2 | yes |
| 28 | `parse_tex_log` | `tex_compiler.rs` | `test_tex_compiler.py` | 2 | yes |

NOT COVERED: none. Every command in the catalog has a named test. Two tests
(`kill_sidecar`, `repair_gpd_venv`) are explicit `pytest.mark.skip`s with
destructive-side-effect rationales; their contract is still asserted by the
catalog invariant + the negative-space sweep, but no runtime call is made.

### Test shapes

Three repeated patterns across the suite:

1. **Happy-path shape check.** Invoke with known-good args, assert the
   returned value matches the declared Rust return type, coerced through
   `serde_json` (`Option<T>` → `None | T`, `Result<(), E>` → `None`, structs
   → `dict` with the `#[serde(rename_all = "camelCase")]` keys). Examples:
   `test_get_default_server_url_happy_path`, `test_detect_tex_compiler_returns_well_formed_info`,
   `test_check_project_accessible_happy_path`.
2. **Negative-space via missing/bad args.** Omit a required field or pass a
   wrong-typed value and assert `pytest.raises(IPCError)`. This exercises
   Tauri's deserializer, not the handler body, and is the go-to substitute
   when the handler itself is destructive (`open_path`,
   `check_project_accessible`, `await_initialization`). Also used where the
   schema is load-bearing (`test_set_default_server_url_rejects_wrong_type`,
   `test_set_wsl_config_rejects_missing_field`).
3. **Platform-gated happy/error split.** Use `sys.platform` to pick a branch;
   on the non-target platform assert an `IPCError` whose message names the
   gate (`"macOS"`, `"Windows"`, `"supported"`). On the target platform
   accept either a well-formed Ok or one of an enumerated set of acceptable
   host-environment failures (network absent, binary not on PATH, permission
   denied). Seen in `test_install_git_macos_platform_gated`,
   `test_install_git_windows_platform_gated`, `test_install_cli_platform_gated`,
   `test_install_tectonic_returns_path_or_errors_cleanly`.

A fourth, global pattern: `test_ipc_negative.py` parametrizes across the
full catalog name list and invokes each command with `{"__bogus__": None}`,
asserting that any error raised mentions arg/parse/deserialize vocabulary
(never a crash or hang). This is the suite's safety-net "no silent failure"
invariant. It also adds a `nonexistent_command_errors_cleanly` check and a
`test_empty_args_on_commands_with_required_fields` probe derived from the
catalog signatures.

Round-trip with state restore is used for settable store values
(`test_set_display_backend_roundtrip`, `test_set_default_server_url_happy_path`,
`test_set_wsl_config_happy_path`): read original, set temp values in a
`try`, restore in `finally` — so a mid-test assertion failure still leaves
the shared GPD instance clean for the next test.

### Known gaps

- `kill_sidecar` and `repair_gpd_venv` are skipped: both have destructive
  session-wide side effects (kills the opencode-cli sidecar / wipes
  `~/.config/gpd/.venv` and re-runs setup). Contract is asserted only by
  the catalog invariant and the bogus-arg sweep — no runtime call is
  actually made. If their signatures change, only the negative-space sweep
  and catalog regeneration will catch it.
- `open_path` is covered only on the error path (missing required arg).
  The happy path would open a Finder window or browser on the test host
  and is intentionally untested; there is no mock seam for the Tauri
  opener plugin.
- `await_initialization` requires a `Channel<InitStep>` allocated from JS.
  The test only asserts that omitting the channel triggers a deserializer
  error; the happy path (listen for init steps during boot) is not
  exercised because the command only fires before the sidecar is ready,
  which is already over by the time the test session attaches to the MCP
  plugin socket.
- `install_cli` / `install_tectonic` / `install_git_*` happy paths are
  "accept Ok *or* enumerated failure modes". On a dev machine where the
  artifact is pre-cached the test is almost a no-op; on a clean CI host
  without network it exercises the error path. Neither case exercises an
  actual install — a future full-matrix run would need a dedicated
  sandbox host.
- `get_wsl_config` / `set_wsl_config`: the getter currently hardcodes
  `enabled: false` (noted inline in `test_server.py`), so the setter's
  happy-path test cannot read-back-assert. Contract verified is only
  "setter accepts a valid WslConfig without error".
- `read_tex_artifact_base64` happy path is skipped when no TeX compiler
  is on the host (cannot produce an artifact to read back).
- `synctex_forward` / `synctex_reverse` accept two legitimate outcomes
  (IPCError vs `None`-filled result) when given a malformed synctex file;
  this is under-specified at the Rust layer, not the test's fault.

## Lifecycle tests (Phase D)

### Test files + what they validate

- `conftest.py` — deliberately minimal (no fixtures beyond the default
  collection hooks); a header comment notes that "lifecycle tests restart
  GPD between steps" and defers the heavy lifting to the project-wide
  `app_state` and `http` fixtures.
- `test_session_list_persistence.py` (`test_multiple_sessions_persist`) —
  creates three sessions via the HTTP API, snapshots their IDs, quits the
  app (`app_state.quit()` + `wait_quit(timeout=15)`), relaunches, and
  asserts every ID still appears in `http.sessions()`. Cleans up its
  sessions in a best-effort loop.
- `test_session_persistence.py` (`test_session_survives_quit_relaunch`) —
  the end-to-end memory-persistence test. Real-backend gated: skips unless
  `GPD_TEST_ANTHROPIC_KEY` is set (the check is inlined rather than
  imported from `tests/flows/conftest.py` to keep the lifecycle conftest
  minimal). Creates one session, sends a prompt that embeds a secret
  number, quits and relaunches, then sends a follow-up asking GPD to
  recall the number. Asserts the assistant's reply contains `"847392"`.
  Marked `@pytest.mark.lifecycle`, `@pytest.mark.flows`,
  `@pytest.mark.real_backend`.
- `test_sidecar_respawn.py` (`test_sidecar_respawns_after_sigkill`) —
  pre-checks `http.health()` is healthy, `pgrep -f 'opencode-cli.*serve'`
  for the PID, `SIGKILL`s it, then polls `pgrep` up to 30 s for a
  respawn with a different PID. After seeing the new PID it polls
  `http.health()` for up to 15 s and asserts it returns `{healthy: True}`.

### Destructive steps (quit/launch/SIGKILL)

- `app_state.quit()` followed by `app_state.wait_quit(...)` — full Tauri
  app teardown. Used in both session-persistence tests.
- `app_state.launch()` (+ `wait_launched()` where required) — cold relaunch.
- `os.kill(old_pid, signal.SIGKILL)` targeted at `opencode-cli serve` —
  kills only the sidecar, leaving the Tauri parent alive to observe and
  respawn it. This is the only hard-kill in the suite.

These steps assume the `app_state` fixture handles the underlying
`pgrep`/SIGTERM/launch orchestration; the lifecycle tests themselves do
not manage processes beyond the sidecar SIGKILL.

### Known gaps (HTTPClient rediscover issue flagged by D1)

Flagged inline in `test_session_persistence.py:39-42` and reiterated in
`test_sidecar_respawn.py:41-45`: **the `http` fixture does not have a
`rediscover()` method.** After a sidecar respawn the cached port/credential
pair in `opencode_http.HTTPClient` is stale, and the root `conftest.py`
`http` fixture is function-scoped so it only picks up a fresh port on the
*next* test, not mid-test after a relaunch. The two lifecycle tests work
around this by:

- `test_session_persistence.py` — accepts that the first `http` call post-
  relaunch may fail, and treats such failure as "a legit finding worth
  escalating" rather than a test bug.
- `test_sidecar_respawn.py` — polls `http.health()` with a 15 s deadline,
  catching exceptions and retrying so a single stale-port failure doesn't
  abort the test. If it never recovers, the assertion fails "loudly" per
  the inline comment.

Recommendation tracked in the D1 write-up: add a `HTTPClient.rediscover()`
method (re-read port + cred from the same source the session fixture uses
at boot) and call it from the lifecycle tests immediately after
`app_state.launch()`. Without that, the tests are tolerant of transient
staleness rather than truly verifying post-restart continuity.

Other lifecycle gaps:

- No test exercises forced crash (e.g. `SIGSEGV` to the Tauri parent,
  OOM, panic in a Rust command) — only clean `quit()` and targeted
  sidecar SIGKILL.
- No test verifies project-list / recent-projects persistence; only
  session state is checked.
- No test covers settings-store persistence (`set_default_server_url`
  across a relaunch); the contract-layer `test_server.py` round-trip
  restores state within a single session.

## Test count summary

- **ipc:** 7 files (`test_dependencies.py`, `test_ipc_negative.py`,
  `test_lib_commands.py`, `test_project_fs.py`, `test_server.py`,
  `test_tectonic_markdown_cli.py`, `test_tex_compiler.py`), **74 tests**
  including parametrized expansion.
  - Per-file breakdown: `test_dependencies.py` 8 (2 platform-gated + 5
    parametrized `linux_install_hint` + 1 unknown-tool);
    `test_ipc_negative.py` 30 (28 catalog-parametrized +
    `test_nonexistent_command_errors_cleanly` +
    `test_empty_args_on_commands_with_required_fields`);
    `test_lib_commands.py` 11 (2 skipped);
    `test_project_fs.py` 4;
    `test_server.py` 6;
    `test_tectonic_markdown_cli.py` 4;
    `test_tex_compiler.py` 11.
- **lifecycle:** 3 files (+ `conftest.py` with no tests), **3 tests**
  total: `test_multiple_sessions_persist`, `test_session_survives_quit_relaunch`
  (real-backend gated), `test_sidecar_respawns_after_sigkill`.

Catalog coverage: **28 / 28** direct references; **2 skipped** runtime
invocations (`kill_sidecar`, `repair_gpd_venv`) guarded by the catalog
invariant + negative-space sweep.
