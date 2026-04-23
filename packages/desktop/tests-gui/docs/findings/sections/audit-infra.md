# Audit: Infra (scripts, conftest, CI, triage)

Scope: `packages/desktop/tests-gui/` plus the two CI workflows `gpd-tests-gui.yml`
and `gpd-tests-flakiness.yml`. Read-only audit, 2026-04-20.

## pytest.ini

Location: `packages/desktop/tests-gui/pytest.ini`

- **testpaths:** `tests tests_unit`
- **python_files / python_classes / python_functions:** `test_*.py`, `Test*`, `test_*`
- **Markers registered (15):**
  - `unit` — fast unit test (no GPD required)
  - `smoke` — Phase 1 smoke test (requires GPD)
  - `restart` — destructive; physically restarts GPD (steals focus). Opt-in via `-m restart`
  - `surfaces` — Phase 2 surface test
  - `flows` — Phase 3 flow test
  - `regression` — Phase 4 regression test
  - `broad` — Phase 5 broad menu/UI test (requires GPD)
  - `real_backend` — requires live LLM API (guarded by `GPD_TEST_ANTHROPIC_KEY`)
  - `fresh_app` — request a full (tier-2) reset before the test
  - `visual` — screenshot-diff assertion (requires visual extras)
  - `steals_focus` — test brings GPD to foreground (⌘-shortcuts). Opt-in via `-m steals_focus`
  - `tier(n)` — override reset tier for this test (0–3)
  - `harness_selftest` — invariants that must hold for any other test result to be trusted
  - `ipc` — Tauri command contract test (requires GPD debug build + MCP socket)
  - `lifecycle` — session lifecycle test (destructive — quits + relaunches GPD)
- **addopts:**
  - `-ra`
  - `--strict-markers`
  - `--timeout-method=thread`
  - `-m "not steals_focus and not restart"`
- **Default exclusion:** any test marked `steals_focus` or `restart` is skipped unless
  explicitly opted in with a matching `-m` expression. This protects an interactive
  developer session from sudden focus theft.
- **Other settings:**
  - `timeout = 60` (per-test, thread-based)
  - `reruns = 0` (pytest-rerunfailures installed but no implicit retries)
  - `log_cli = false`, `log_cli_level = INFO`

Notable:
- `--strict-markers` is enabled → every marker must be registered here or pytest
  errors. Good discipline but means any newly-introduced marker in a test will hard-fail.
- `pytest-xdist` is actively blocked: `conftest.pytest_configure` raises
  `pytest.UsageError` if xdist is enabled — "single-instance only; would corrupt state."

## conftest.py (root)

Location: `packages/desktop/tests-gui/conftest.py` (377 lines)

### Fixtures exported

| Name | Scope | Autouse | Purpose |
|---|---|---|---|
| `seed_onboarding_state` | session | yes | Write a real `auth.json` + onboarding sentinel so GPD skips first-run, when both `GPD_TEST_SEED_ONBOARDING=1` AND `GPD_TEST_ANTHROPIC_KEY` are set. Backs up & restores the user's real files on teardown. XDG-aware paths. |
| `app_state` | session | no | Launch GPD at session start, `wait_launched()`, yield `AppState`. Kills stale processes if `PYTEST_COLD_START=1`; quits at session end if `PYTEST_QUIT_GPD=1`. |
| `mcp` | function | no | `MCPClient` bound to the live app. Auto-discovers an auth token via `scripts.discover_mcp_token` on 401. |
| `ax` | function | no | `AXClient`. Does NOT call `activate()` eagerly (avoids focus theft). |
| `http` | function | no | `HTTPClient` to the opencode-cli sidecar. Waits for sidecar PID, probes `/global/health` before yielding. |
| `os_input` | function | no | `OSInputClient`. Skips (not fails) the test if `cliclick` is missing. |

### Hooks defined

- **`pytest_configure(config)`** — raises `pytest.UsageError` if `pytest-xdist` is
  active with `dist != "no"`.
- **`pytest_runtest_setup(item)`** — marker-driven reset hook. Honors
  `@pytest.mark.tier(n)` and `@pytest.mark.fresh_app` (latter = tier 2). Calls
  `scripts.reset.run(tier=..., stop_app=True, start_app=True)`. After reset,
  calls `fresh_state.wait_launched()` and `_session_app_state.refresh_launched_pid()`
  so the session-scoped `app_state` keeps tracking the new PID. Skips the reset
  entirely for tests that will be skipped (guarded via `_is_skipped()`, which
  correctly defers string-form `skipif` conditions to pytest).
- **`pytest_runtest_makereport(item, call)`** — on test failure (during
  `call` phase only):
  - uses the live `mcp` fixture (if present) to save `screenshot.jpg`
    and `windows.json` into `artifacts/<module>/<test>/` (MCP, not AX,
    to avoid activating GPD and stealing focus);
  - writes `nodeid.txt`;
  - imports `scripts.triage_gate4.find_related_commits` and writes a
    `artifacts/triage_hints/<nodeid>.md` listing product-code commits from
    the last 24h (paths: `packages/desktop/src-tauri/`, `packages/desktop/src/`).
    Silent no-op if the import fails.
- **`pytest_report_header(config)`** — prints a one-liner:
  `opencode-gpd-test | slow-mo=<PYTEST_SLOWMO_MS>ms | CI=<PYTEST_CI>`.

### Environment variables read

| Var | Purpose |
|---|---|
| `GPD_TEST_SEED_ONBOARDING` | 1 → enable session-autouse onboarding seed (paired with key) |
| `GPD_TEST_ANTHROPIC_KEY` | API key written into `auth.json` for real-backend tests |
| `PYTEST_COLD_START` | 1 → kill any stale GPD/opencode-cli before launching |
| `PYTEST_QUIT_GPD` | 1 → quit GPD at session end |
| `PYTEST_SLOWMO_MS` | displayed in header only (consumer lives elsewhere) |
| `PYTEST_CI` | displayed in header; turns on CI-specific behaviour in tests |
| `XDG_DATA_HOME` | respected by `_auth_json_path()` |
| `GPD_MCP_AUTH_TOKEN` | picked up indirectly via `scripts.discover_mcp_token.discover()` on MCP 401 |

### `.coveragerc`

```ini
[run] source=gpd_tests  branch=True  parallel=True
omit: __init__.py, tests_unit/*, tests/*, scripts/*, vendor/*
[report] excludes: pragma: no cover, raise NotImplementedError, if __name__, TYPE_CHECKING
[html] directory=coverage_html
```

Only `gpd_tests/` is measured — test files and scripts are deliberately excluded.
`parallel=True` is set even though xdist is blocked; harmless, required only when
multiple coverage contexts write concurrently, which does not happen here.

## Scripts

### `packages/desktop/tests-gui/scripts/`

| Script | Purpose | Invocation | Unit-tested? |
|---|---|---|---|
| `__init__.py` | Package marker | — | n/a |
| `_bundle.py` | Derive macOS app name + bundle ID from `GPD_APP_PATH` (release `GPD` / debug `GPD Dev` / beta `GPD Beta` → bundle IDs). Shared helper imported by `reset.py`, `discover_mcp_token.py`. | library | indirectly (reset tests) |
| `discover_mcp_token.py` | Search for tauri-plugin-mcp auth token: env `GPD_MCP_AUTH_TOKEN` → `~/Library/Application Support/<bundle>/mcp-auth.token` → recent log scan. Called lazily from `conftest.mcp` fixture on 401. Prints token on stdout when run as `__main__`. | `python -m scripts.discover_mcp_token` | **no** |
| `extract_tauri_commands.py` | Scan `src-tauri/src/*.rs` for `#[tauri::command]` and emit JSON catalog. | `python scripts/extract_tauri_commands.py > gpd_tests/fixtures/tauri_commands.json` | yes — `tests_unit/test_tauri_commands_catalog.py` |
| `refresh_en_dict.py` | Parse `packages/app/src/i18n/en.ts` + `packages/desktop/src/i18n/en.ts`, merge (desktop wins), write `gpd_tests/fixtures/en.json`. Includes a UTF-8-safe JS-escape unescaper (avoids `unicode_escape` latin-1 codec). | `python scripts/refresh_en_dict.py` | yes — `tests_unit/test_refresh_en_dict.py` |
| `reset.py` | Tiered state reset: tier 1 deletes `opencode.db*`; tier 2 adds Application Support / WebKit / Caches / Logs for the derived bundle + `auth.json`; tier 3 adds `$XDG_CONFIG_HOME/gpd/.gpd-initialized`. Stops GPD (graceful quit → SIGKILL fallback), wipes paths, restarts with `open -g -a` (backgrounded). | `python -m scripts.reset --tier N [--dry-run] [--no-restart]` — also invoked from `pytest_runtest_setup` | yes — `tests_unit/test_scripts_reset.py` |
| `run_coverage.sh` | Run `uv run pytest tests_unit --cov=gpd_tests --cov-branch --cov-report=html,term-missing,xml`. **Unit coverage only.** | `./scripts/run_coverage.sh` | no |
| `triage.py` | Four-gate protocol driver: runs a nodeid N times against current build (gate 1) and, if a reference `/Applications/GPD.app` exists, N times against that (gate 3). Prints `LABEL: FLAKY|PASSING|REGRESSION_ON_BRANCH|…`. | `python scripts/triage.py <nodeid> [--iterations N] [--reference PATH]` | no |
| `triage_gate4.py` | Given a `since` date, return product-code commits in `src-tauri/` + `src/`. Exposes `find_related_commits()` used by `pytest_runtest_makereport`; CLI entrypoint for manual use. | `python scripts/triage_gate4.py <YYYY-MM-DD>` | yes — `tests_unit/test_triage_gate4.py` |
| `flakiness/__init__.py` | Package marker | — | n/a |
| `flakiness/report.py` | Aggregate `junit-*.xml` files into `{stable, flaky, broken, total_runs}`. Emits markdown on stdout. | `python scripts/flakiness/report.py <junit_dir>` | yes — `tests_unit/test_flakiness_report.py` |

### `packages/desktop/src-tauri/scripts/`

| Script | Purpose | Invocation | Tested? |
|---|---|---|---|
| `rust_coverage.sh` | `cargo llvm-cov clean` then `cargo llvm-cov --html --workspace --ignore-filename-regex='vendor/'`. Falls back to Homebrew LLVM if rustup is missing. | `./packages/desktop/src-tauri/scripts/rust_coverage.sh` | no |

## CI workflows

### `.github/workflows/gpd-tests-gui.yml`

- **Triggers:**
  - `push` — path-filtered to `packages/desktop/tests-gui/**`, `packages/desktop/src-tauri/**`, `packages/desktop/src/**`, and the workflow file itself.
  - `pull_request` — only against branch `gpd`.
  - `workflow_dispatch`.
- **Concurrency:** grouped by `github.ref`, in-progress runs cancelled.
- **Jobs (4, all on `macos-15`):**

  | Job | needs | timeout | Markers run |
  |---|---|---|---|
  | `unit` | — | 10 min | `-m unit` (no GPD) |
  | `smoke-and-flows` | `unit` | 60 min | `-m "(smoke and not restart) or (flows and not real_backend)"` + optional `-m "flows and real_backend"` when `GPD_TEST_ANTHROPIC_KEY` secret is set |
  | `surfaces` | `smoke-and-flows` | 60 min | `-m "surfaces and not steals_focus"` (`continue-on-error: true`) |
  | `regression` | `smoke-and-flows` | 60 min | `-m regression` |

- **Env shared by GPD-launching jobs:** `PYTEST_CI=1`, `PYTEST_COLD_START=1`, `PYTEST_QUIT_GPD=1`.
- **Build pipeline** (repeated across 3 jobs with identical steps):
  `checkout → setup-bun → dtolnay/rust-toolchain@stable (aarch64-apple-darwin) → Swatinem/rust-cache → setup-uv@v6 → brew install cliclick → bun install --frozen-lockfile → bun run predev (builds opencode-cli sidecar) → download uv-bundle from astral-sh/uv release → bun run tauri build --debug → uv sync → open the built .app → wait for sidecar`.
- **Artifacts:**
  - `gpd-tests-gui-artifacts-<run_id>` (on failure) — `tests-gui/artifacts/` (screenshots, windows, triage hints)
  - `gpd-surfaces-artifacts-<run_id>` (always)
  - `gpd-regression-artifacts-<run_id>` (on failure)
  - `coverage-html-smoke-and-flows`, `coverage-html-surfaces`, `coverage-html-regression` (always)
  - `coverage-xml-*` counterparts (always)
- **Known failure modes** (inferred from workflow comments + recent commits):
  - Accessibility (AX) permission can't be granted on GitHub-hosted runners; workflow emits a `::notice::` and keeps going. AX-dependent tests will fail on first run until a self-hosted runner is provisioned.
  - Real-backend flows are gated by `secrets.GPD_TEST_ANTHROPIC_KEY`; fork PRs will skip them. This step has `continue-on-error: true`, so its failures don't block the job.
  - Verify step in `smoke-and-flows` greps `strings` for `tauri-plugin-mcp` — if the plugin gets re-gated or stripped, every downstream job fails at this step.

### `.github/workflows/gpd-tests-flakiness.yml`

- **Triggers:** `schedule` (`cron: 17 7 * * *` — 07:17 UTC daily) + `workflow_dispatch`.
- **Concurrency:** group `gpd-tests-flakiness-<ref>`, cancel-in-progress.
- **Jobs:**
  - `flakiness` — matrix `iteration: [1..10]`, `fail-fast: false`, `macos-15`, 30 min timeout. Each cell: build debug app → launch → `pytest -m "smoke and not restart" --junitxml=junit-<i>.xml -v` (with `continue-on-error: true`) → upload `junit-<i>` artifact.
  - `aggregate` — needs `flakiness`, `if: always()`, `ubuntu-latest`. Downloads every JUnit artifact into `junit/`, flattens, runs `scripts/flakiness/report.py flatten/ > flakiness_report.md`, uploads `flakiness-report` artifact (retention 30d).
- **Aggregator wiring:** uses the local repo checkout's `scripts/flakiness/report.py`. The workflow still contains a legacy "script not present" fallback branch labelled `until Phase E2` — the aggregator IS now implemented, so that branch is dead.

## Triage tooling

- **Four-gate methodology plan:** `packages/desktop/tests-gui/docs/superpowers/plans/2026-04-20-test-harness-triage-methodology.md`. Defines gates 1–4, the labels (`FLAKY`, `HARNESS_BUG`, `REGRESSION_ON_BRANCH`, `PRODUCT_DRIFT_TEST_STALE`, `REAL_BUG`) and the invariant that every green-suite claim MUST come paired with a harness-selftest pass.
- **`scripts/triage.py`:** implemented. Automates gates 1 and 3 — repeats `pytest <nodeid> -q --no-header -x` N times against current build; if pass-rate is 20–80% → `FLAKY`, if 100% → `PASSING`; otherwise repeats against reference build at `--reference` (default `/Applications/GPD.app`) and emits `REGRESSION_ON_BRANCH` / `HARNESS_BUG or PRODUCT_DRIFT` / `NEEDS_MANUAL`. Note: the triage-methodology plan doc still says this is "NOT YET BUILT — tracked as an open task," which is stale.
- **`scripts/triage_gate4.py`:** implemented. Library function `find_related_commits(since, paths, repo_root)` runs `git log --since=<since> --pretty=format:%H\t%s -- <paths>`. Wired into `conftest.pytest_runtest_makereport` — every failure writes a `artifacts/triage_hints/<nodeid>.md` file with product-code commits from the last 24h. CLI entrypoint for manual windows.
- **Harness self-test:** `packages/desktop/tests-gui/tests/harness_selftest/test_harness_invariants.py` — 7 tests, all tagged `@pytest.mark.harness_selftest`:
  1. `test_python_version_meets_floor` — ≥ 3.12
  2. `test_uv_available` — `uv` in PATH
  3. `test_cliclick_available_when_os_input_imported` — skip if missing
  4. `test_osascript_available`
  5. `test_gpd_app_path_resolves_if_set` — skip unless `GPD_APP_PATH` set
  6. `test_mcp_socket_discoverable_when_gpd_running` — asserts that if any `GPD` binary is alive, a `/var/folders/*/*/T/tauri-mcp.sock` exists
  7. `test_sidecar_available_when_gpd_running` — asserts GPD-alive ⇒ opencode-cli alive
  8. `test_en_fixture_is_fresh_enough` — ≥ 800 keys and each namespace prefix (`welcome.`, `home.`, `sidebar.`, `session.`, `dialog.`, `error.`) has at least one key
  Local `conftest.py` exposes a `tests_root` session fixture and keeps imports minimal so the selftest remains runnable even when the rest of the harness is broken.

## Known config/infra gaps

1. **CI never runs `harness_selftest`.** The methodology plan says every green-suite
   claim must be paired with a passing selftest; no CI job executes `-m harness_selftest`.
   The `smoke-and-flows` selector (`(smoke and not restart) or (flows and not real_backend)`)
   excludes it. A ~single-digit-second job (no GPD needed for most invariants) would
   fix this.
2. **CI never runs `ipc`, `lifecycle`, or `broad` markers.** `tests/ipc/`,
   `tests/lifecycle/`, `tests/broad/` all contain tests and have registered markers,
   but none of the 4 CI jobs includes them. The `smoke-and-flows` filter only picks
   up `smoke` + `flows`; `surfaces` and `regression` have their own filters that also
   exclude them. Consequence: the Phase 5 broad menu suite, the Tauri-command contract
   tests (`ipc`), and the destructive lifecycle tests never run in CI and so regressions
   there land unobserved.
3. **Triage-methodology plan doc is stale.** `scripts/triage.py` (section
   "Supporting infrastructure (to build) — item 1") and the harness self-test suite
   (item 2) are both described as "NOT YET BUILT — tracked as an open task." Both
   are implemented and present. Doc should be refreshed.
4. **Flakiness workflow retains dead fallback.** `gpd-tests-flakiness.yml:127-134`
   has an `if [ -f scripts/flakiness/report.py ]` branch that emits a placeholder
   "aggregator is a no-op until Phase E2" report. That file has existed since
   commit `24836fe`; the fallback can never fire and should be deleted.
5. **`discover_mcp_token.py` is not unit-tested.** Every other production script
   in the package (`extract_tauri_commands`, `refresh_en_dict`, `reset`,
   `triage_gate4`, `flakiness/report`) has a matching `tests_unit/test_*.py`.
   Discovery covers env / file / log-scan fallbacks — worth the test, especially
   because the log-scan path is dead code per the module's own comment.
6. **`run_coverage.sh` is unit-only.** The script runs `pytest tests_unit` and
   so coverage never includes any driver/page code exercised only by integration
   tests. Fine if deliberate, but the file's name suggests a full-coverage run.
7. **Per-job build duplication in `gpd-tests-gui.yml`.** Three jobs
   (`smoke-and-flows`, `surfaces`, `regression`) each check out, install toolchains,
   build the sidecar, stage uv, and rebuild the debug Tauri bundle (~10 min each
   on macOS). Shared artifact upload from a single `build` job would cut ~20 min
   of wall clock per run.
8. **`.coveragerc` declares `parallel = True` unnecessarily.** `pytest-xdist` is
   hard-blocked by `pytest_configure` and no other process writes coverage data,
   so `parallel` buys nothing. Harmless, but noise.
9. **No `ipc` / `lifecycle` coverage in the path-filter trigger set is fine**,
   but the fact that they're unwired from CI (gap #2) means changes to
   `src-tauri/src/*.rs` Tauri commands won't be validated against the `ipc`
   contract suite on PR — even though that's exactly the scenario the contract
   suite exists for.
10. **`pytest_runtest_setup` reset hook swallows nothing.** If `scripts.reset.run`
    raises mid-reset (e.g. SIGKILL timeout → `RuntimeError`), the test erroring
    at setup will propagate; the subsequent test won't get a fresh app because
    `fresh_state.wait_launched(timeout_s=20.0)` is unreachable. Not a bug per se,
    but there is no recovery path — one broken reset cascades through the rest
    of the session.
