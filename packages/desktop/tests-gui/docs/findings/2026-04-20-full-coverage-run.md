# GPD GUI Full-Coverage Run & Findings

**Date:** 2026-04-20
**Branch:** `feature/gui-test-suite`
**Build under test:** local debug build at `packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app` (productName `GPD Dev`, bundle id `inc.psi.gpd.dev`, binary `GPD`)
**Reporter:** Claude Opus 4.7 (1M context) + subagents

---

## Executive summary

_To be completed after Phase X3 runs._

- Static audit: 6 sections, 11,220 words describing every file in the test suite.
- Live runs: N iterations per marker group (unit ×5, smoke ×5, surfaces ×3, ipc ×3, flows ×3, regression ×3, broad ×3, lifecycle ×2).
- Findings: per-test root-cause in the Findings section below.
- Top-severity items: _TBD_

---

## Table of contents

1. [Architecture audit](#architecture-audit)
   - [Smoke + flows](#smoke--flows)
   - [Surfaces + regression + broad](#surfaces--regression--broad)
   - [IPC + lifecycle](#ipc--lifecycle)
   - [Unit tests](#unit-tests)
   - [Harness architecture](#harness-architecture)
   - [Infra (scripts, CI, triage)](#infra-scripts-ci-triage)
2. [Run results](#run-results)
3. [Findings](#findings)
4. [Cross-cutting observations](#cross-cutting-observations)
5. [Next steps](#next-steps)

---

## Architecture audit

Each subsection is the verbatim output of one Phase X1 audit agent; they were dispatched in parallel, reading disjoint areas of the test suite. Minor formatting adjustments for composition only.

### Smoke + flows

See `sections/audit-smoke-flows.md` (1,915 words). Summary:

- **Smoke (Phase 1):** 10 files, 14 test functions. Covers launch, sidecar health, MCP socket, window geometry, top-level menu bar, welcome screen, artifact capture, restart (opt-in), release-mode defenses (opt-in), providers list (real-backend).
- **Flows (Phase 3):** 9 files, 10 test functions. Covers session create/list/send, onboarding, multi-turn memory, tool use, concurrent sessions, abort, theme switch, deep-link routing, provider-list shape round-trip.
- **Red flags** (X1a):
  1. `test_provider_switch.py::test_default_provider_switch_write_path_not_yet_exposed` is a permanent `xfail` — documents intent rather than asserting it.
  2. `test_release_no_mcp.py` is double-gated (`PYTEST_RELEASE_BUILD` + bundle-id check) — a critical security regression surface that never runs by default.
  3. `test_onboarding.py` is triple-gated (`real_backend` + `fresh_app` + `PYTEST_RUN_DESTRUCTIVE_FLOWS=1`) — never runs in a typical dev or CI flow.
  4. `test_theme_switch.py` silently skips for users in auto/system theme — masks coverage for the dominant config.
  5. `test_new_session.py` falls back from scoped `sessions(directory=...)` to unscoped `sessions()` — would mask a directory-scoping regression.
  6. `os_input` fixture is defined but unused anywhere in smoke/flows — no keyboard/mouse smoke path.

### Surfaces + regression + broad

See `sections/audit-surfaces-regression.md` (1,743 words). Summary:

- **Surfaces (Phase 2):** 6 files, 11 tests. Covers home page, onboarding, settings, provider management, session list, sidebar.
- **Regression (Phase 4):** 1 file, 1 test (`test_empty_accelerator_token.py`).
- **Broad (Phase 5):** 6 files, 11 tests. AX menu sweeps (top-level + per-menu items), keyboard shortcuts, window ops.
- **Red flags** (X1b):
  1. `gpd_tests/pages/menu.py` is **dead code** — no imports anywhere in the repo. Broad uses `AXClient` directly.
  2. Surfaces `conftest.py` exposes `nav` and `dom` fixtures that every test ignores — consumers rebuild `Navigator(mcp)` / `DOMProbe(mcp)` inline.
  3. `smoke/test_menu_bar.py` ↔ `broad/test_menu_sweep.py` overlap on top-level menu assertion.
  4. Regression is a directory of one — no regressions added for recent Tauri removal or TeX/preview work.
  5. Two tests silently skip missing preconditions, looking green while asserting nothing.
  6. No broad test invokes a menu item (all read-only AX queries). No accelerator round-trip.
  7. `prepared_project_path` duplicated between `test_project.py` and `test_session.py`.
  8. Page-object coverage: `AppState` ~80%, `Onboarding` ~40%, `Menu` 0%.

### IPC + lifecycle

See `sections/audit-ipc-lifecycle.md` (1,712 words). Summary:

- **IPC (Phase B):** 7 test files covering all 28 `#[tauri::command]`s from the catalog. Three test shapes: happy-path shape-check, missing/wrong-type negative, and `sys.platform` platform-gated split. A parametrized `{"__bogus__": None}` sweep (`test_ipc_negative.py`) asserts no silent success on malformed args for every command.
- **Lifecycle (Phase D):** 3 files, 3 tests: multi-session persistence, session-with-assistant memory (real-backend), sidecar SIGKILL respawn.
- **Red flags** (X1c):
  1. **100% catalog coverage** of the 28 commands (by name reference). 2 are explicit `pytest.mark.skip`s for destructive side effects (`kill_sidecar`, `repair_gpd_venv`).
  2. 5 commands lack a runtime happy-path contract (all documented): `kill_sidecar`, `repair_gpd_venv`, `open_path`, `install_cli`, `await_initialization`.
  3. `get_wsl_config` currently hardcodes `enabled: false` — its setter can't round-trip verify.
  4. **`HTTPClient.rediscover(pid)` is missing** — after `app_state.quit()+launch()`, the old `http` instance still points at the dead sidecar's port+creds. Both lifecycle tests are currently tolerant-of-staleness workarounds rather than strict post-restart continuity checks. Tracked as task #76.
  5. Lifecycle gaps: no forced-crash test (e.g. SIGSEGV the sidecar), no project-list persistence test, no settings-store persistence test.

### Unit tests

See `sections/audit-unit.md` (1,446 words). Summary:

- 117 tests across ~18 files. Confirmed via `uv run pytest tests_unit -q --collect-only`.
- **Modules with no unit tests:** `pages/menu.py` (dead code), `pages/onboarding.py` (integration-only), `scripts/_bundle.py`, `scripts/discover_mcp_token.py`, `scripts/triage.py`. `pages/app_state.py` is partial (`is_running()` tested; `launch/quit/kill_stale/wait_launched` not).
- **Red flags** (X1d):
  1. `test_driver_http_abort.py` duplicates coverage in `test_driver_http_session.py`.
  2. `test_tauri_commands_catalog.py` is marked `unit` but spawns a subprocess — functionally a snapshot/integration test.
  3. `scripts/discover_mcp_token.py::_discover_from_logs()` is documented dead code but still shipped.
  4. `drivers/os_input.py::move()` has zero coverage.
  5. `helpers/dom_probe.py::eval_json` and `eval_int` have zero coverage despite being public API.

### Harness architecture

See `sections/audit-harness.md` (2,096 words). Summary:

- **Layering:** `drivers/` (low-level: HTTP, MCP, AX, OS input) ← `helpers/` (composition) ← `pages/` (app-level).
- **Layering violations (X1e):**
  1. `helpers/sheet.py` imports module-private `_osascript` from `drivers/ax.py`.
  2. `pages/app_state.py` imports module-private `_discover_socket_path` from `drivers/mcp.py`.
- **Dead code:**
  - `pages/menu.py::Menu` — zero callers.
  - `drivers/ax.py::MenuItem` dataclass — never referenced.
  - `helpers/navigator.py::route_session` — self-deprecated.
  - `helpers/dom_probe.py::eval_json`, `eval_int` — no consumers.
  - `helpers/i18n.py::t` — only used transitively.
  - `tests/flows/conftest.py::clean_auth_json` — backwards-compat alias, no callers.
- **Incidental bug flagged:** `tests_unit/test_driver_http.py` calls `c.path_info(directory="/tmp")` but `HTTPClient.path_info()` accepts no args. The surrounding `pytest.raises(Exception)` masks the mismatch.

### Infra (scripts, CI, triage)

See `sections/audit-infra.md` (2,308 words). Summary:

- `pytest.ini`: 15 markers registered. Default filter `-m "not steals_focus and not restart"`.
- Root `conftest.py`: merged hooks (`pytest_runtest_makereport` writes both screenshot and Gate-4 triage-hint markdown on failure).
- 10 scripts in `scripts/`; most have unit tests.
- CI: `gpd-tests-gui.yml` (unit+smoke+flows+surfaces+regression), `gpd-tests-flakiness.yml` (nightly 10× cron).
- **Infra red flags (X1f):**
  1. **CI marker gap:** `ipc`, `lifecycle`, `broad`, `harness_selftest` markers are registered but no CI job selects them. ~74 ipc + 3 lifecycle + 11 broad tests never run in CI.
  2. Plan doc `2026-04-20-test-harness-triage-methodology.md` still says `scripts/triage.py` and `tests/harness_selftest/` are "NOT YET BUILT" — both exist.
  3. `gpd-tests-flakiness.yml` has a dead "until Phase E2" fallback (E2 landed as commit `24836fe`).
  4. `discover_mcp_token.py` is the only script with no unit test.
  5. **CI build triplication** — three jobs each rebuild the Tauri debug bundle (~10 min each on macOS-15). Share-via-artifact would save ~20 min.
  6. `run_coverage.sh` is unit-only despite its name.
  7. `.coveragerc` `parallel = True` is unused (xdist is hard-blocked).

---

## Run results

_Phase X3 sweep running in background (bash task `bcclb5io9`). Iterations:_

| Marker group | Iterations | Status |
|---|---|---|
| unit | 5 | _running_ |
| smoke | 5 | _pending_ |
| surfaces | 3 | _pending_ |
| ipc | 3 | _pending_ |
| flows (non real_backend) | 3 | _pending_ |
| regression | 3 | _pending_ |
| broad | 3 | _pending_ |
| lifecycle | 2 | _pending_ |

### Flakiness aggregation

_To be populated from `runs/flakiness_report.md` once the sweep finishes._

---

## Findings

_Each finding is independently verified via Phase X4 classification agents: they read the test, the product code it exercises, and the harness code it depends on; then they assign one of five labels per the triage four-gate methodology._

Labels:
- **REAL_BUG** — product code has a defect.
- **REGRESSION_ON_BRANCH** — product code worked on `origin/gpd` but broke on the branch.
- **PRODUCT_DRIFT_TEST_STALE** — product code changed legitimately; test assertion is now wrong.
- **HARNESS_BUG** — test code itself is incorrect; product is fine.
- **FLAKY** — passes and fails intermittently without deterministic cause.

_Findings table to be populated._

---

## Cross-cutting observations

These emerged from the audits (pre-run) and will be cross-referenced against run results:

1. **Marker-driven CI gap.** ~88 tests (ipc + lifecycle + broad + harness_selftest) never run in CI. Fix: extend `gpd-tests-gui.yml` with a second job that applies `-m "ipc or lifecycle or broad"` with appropriate destructive-skip flags.
2. **Page-object dead-code debt.** `pages/menu.py` has no consumers; neither does `drivers/ax.py::MenuItem`, `helpers/navigator.py::route_session`, `helpers/dom_probe.py::eval_{json,int}`, `helpers/i18n.py::t`, `tests/flows/conftest.py::clean_auth_json`. Safe to delete after a one-round grep.
3. **Two layering violations** to clean up: `helpers/sheet.py` → `drivers/ax.py::_osascript`, `pages/app_state.py` → `drivers/mcp.py::_discover_socket_path`. Promote the imports to public API.
4. **`HTTPClient.rediscover(pid)` must land before Phase D can become strict.** Currently D1/D3 are workarounds.
5. **Onboarding + release-mode tests are gated on env vars** that no dev or CI ever sets. Either wire them in or delete them as inert.
6. **The `test_driver_http.py::test_path_info_malformed_json_raises` bug.** Test calls `path_info(directory="/tmp")` with a kwarg the function doesn't accept; the broad `pytest.raises(Exception)` hides a TypeError.
7. **Triage plan doc drift.** The 2026-04-20 triage methodology plan still lists `scripts/triage.py` as unbuilt. Update.

---

## Next steps

In priority order (to be re-ranked after run results land):

1. Extend CI to cover the missing markers (`ipc`, `lifecycle`, `broad`, `harness_selftest`).
2. Ship `HTTPClient.rediscover(pid)`; tighten D1/D3 to strict post-restart asserts.
3. Delete the dead code in one PR.
4. Fix the `test_path_info_malformed_json_raises` masked bug (or fix the target).
5. Update the triage-methodology plan doc.
6. Decide the fate of the triple-gated tests (`test_onboarding.py`, `test_release_no_mcp.py`) — wire, delete, or mark as explicit "manual-only."
7. Fix CI "Verify debug bundle" step (aarch64 target path).
8. Resolve the smoke `test_sidebar_new_session_selector_is_in_dom` finding from the first live run (needs X4 verification).
