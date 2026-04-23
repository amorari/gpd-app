# CL-B: check_project_accessible failures

Both failing tests invoke the Tauri command `check_project_accessible`. The
command exists in source and is registered in the Tauri invoke handler, but
the GPD debug binary the suite is running against was built before the
command landed, so both invocations return the same "command not found"
error.

## Failure 1: test_check_project_accessible_happy_path

- **Failure message:** _exact_
  - `gpd_tests.helpers.ipc.IPCError: Command check_project_accessible not found`
  - Raised from `gpd_tests/helpers/ipc.py:119` (the `{ok: false, err: ...}`
    branch of `invoke_via_mcp`). The err string `"Command
    check_project_accessible not found"` is produced by Tauri's
    `__TAURI_INTERNALS__.invoke` when no handler with that name is
    registered in the running binary.

- **Test invocation:** _args it passes_
  - `invoke_via_mcp(mcp, "check_project_accessible", {"path": d})` where
    `d` is a freshly-created `tempfile.TemporaryDirectory()` (a readable
    directory the main process owns). Asserts the return equals `"ok"`.

- **Command signature:** _from project_fs.rs_
  - `pub fn check_project_accessible(path: String) -> Result<String, String>`
    (`packages/desktop/src-tauri/src/project_fs.rs:55`).
  - Arg name `path` matches the test — no harness mismatch.
  - Returns `Ok("ok")` for a readable dir, `Ok("locked")` for EACCES/EPERM,
    `Ok("missing")` for NotFound, else `Err(...)`. Registered in
    `packages/desktop/src-tauri/src/lib.rs:425` inside
    `tauri_specta::collect_commands![...]`.

- **Root cause:**
  - The running GPD debug binary is stale. The command was added on the
    current branch in commit `c14fa7c feat(tcc): track C - macOS
    TCC-aware project opening` at `2026-04-20 17:08:10 -0400`, but the
    binary at
    `packages/desktop/src-tauri/target/debug/GPD` has `mtime 2026-04-20
    15:54` and the test run's `ipc-1.xml` `testsuite.timestamp` is
    `2026-04-20T22:00:14`. Source is correct; the binary driving the
    suite simply doesn't have the command compiled in, so Tauri's IPC
    layer reports "Command ... not found". (No running GPD process
    matches pid 62782 now, so I couldn't probe live — but the binary
    mtime vs. commit time is unambiguous.)

- **Label:** `HARNESS_BUG` (operational: stale binary under test) — **not**
  `PRODUCT_DRIFT_TEST_STALE` and **not** `REAL_BUG`. The Rust source +
  handler registration are correct; the test's args and expected return
  value are correct. The only defect is that the suite ran against a
  build older than the feature it is exercising.

- **Fix hint:**
  - Rebuild and relaunch GPD before re-running the `ipc` markers:
    `pnpm --filter gpd-desktop tauri dev` (or whatever the suite's
    launch helper is) from a clean state after `c14fa7c` is in HEAD.
    Verify with a live probe:
    ```python
    invoke_via_mcp(mcp, "check_project_accessible", {"path": "/tmp"})
    # expect "ok"
    ```
  - Consider a conftest-level guard in `tests-gui` that enumerates the
    running binary's commands via `tauri_commands.json` vs. a live probe
    of one sentinel newcomer (e.g. `check_project_accessible`) and fails
    fast with a clear "rebuild GPD; binary is stale" message instead of
    surfacing this as N per-command failures.

## Failure 2: test_command_rejects_bogus_arg_shape[check_project_accessible]

- **Failure message:** _exact_
  - `AssertionError: check_project_accessible errored but message doesn't
    mention arg issue: IPCError('Command check_project_accessible not
    found')`
  - Triggered at `tests/ipc/test_ipc_negative.py:66-69` where the sweep
    asserts the err message contains one of `("arg", "field", "parse",
    "deserialize", "missing", "invalid", "expected", "unknown")`. The
    message `"Command check_project_accessible not found"` contains none
    of those tokens, so the `any(...)` check is False and the assert
    fires.

- **Why it fails** (remember: the negative sweep expects IPCError with one
  of `["arg", "field", "parse", "deserialize", "missing", "invalid",
  "expected", "unknown"]` in the message):
  - Because the command isn't registered in the running binary, the
    invoke short-circuits at Tauri's command-dispatch layer with a
    "handler not found" error. The deserializer (which would have
    emitted an `unknown field \`__bogus__\`` / `missing field \`path\``
    message matching the expected hints) is never reached. The test is
    checking deserializer behavior for a command that, from the running
    binary's point of view, doesn't exist at all.

- **Root cause:**
  - Same as Failure 1 — stale GPD binary. Once rebuilt, the invoke will
    reach Tauri's serde-based arg deserializer, which for
    `check_project_accessible(path: String)` will reject
    `{"__bogus__": null}` with a message of the form `invalid args \`path\`
    for command \`check_project_accessible\`: command
    check_project_accessible missing required key path` — that message
    contains "invalid", "missing", and "command" and the sweep will
    pass.

- **Label:** `HARNESS_BUG` (same operational issue: stale binary). Not a
  product bug; not test staleness against a newer product.

- **Fix hint:**
  - Rebuild GPD and rerun. The sweep has no per-command logic for
    `check_project_accessible` — the fix is purely environmental.
  - Optional hardening: if the negative-sweep ever sees "not found" /
    "handler" / "command not found" on a command that IS in the catalog
    (`gpd_tests/fixtures/tauri_commands.json`), treat it as a build-skew
    error (xfail with a clear reason) rather than a sweep failure,
    since the sweep's contract is "the deserializer rejects nonsense",
    not "the binary exposes this command".

## Common thread

Both failures share a single root cause: **the GPD debug binary under
test predates commit `c14fa7c` (the commit that introduces
`check_project_accessible`), so Tauri's IPC layer has no handler for
that command name and returns `"Command check_project_accessible not
found"` for every invocation — happy-path, bogus-arg, or otherwise.**
Source (`project_fs.rs`) and registration (`lib.rs:425`) are both
correct. The test invocations and assertions are also correct. There is
no product bug and no test-side drift; the test harness was run against
a stale binary. Rebuild GPD from HEAD (which contains `c14fa7c`) and
both tests will pass without any code changes. A small harness-level
guard (`build-skew detector` in conftest or a catalog-vs-live probe)
would prevent the same class of failure from masquerading as N
per-command regressions in future runs.
