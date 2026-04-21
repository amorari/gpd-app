# GPD GUI Full-Coverage Run & Findings

**Date:** 2026-04-20
**Branch:** `feature/gui-test-suite`
**Build under test:** local debug build at `packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app` (productName `GPD Dev`, bundle id `inc.psi.gpd.dev`, binary `GPD`, rebuilt at 22:07 from HEAD)
**Reporter:** Claude Opus 4.7 (1M context) + 10 subagents across audit and classification

---

## Executive summary

**Final live-run result — 27 iterations across 8 marker groups:**

| Metric | Before fixes | After fixes |
|---|---|---|
| Stable tests | 214 | **221** |
| Flaky | 1 | **0** |
| Broken (failed every run) | 10 | **7** |

**Twelve findings verified, all classified as HARNESS_BUG.** Zero real product bugs found. Six landed fixes in the branch (`79233c9`, `c96b9cd`, `5ab4699`, `7f7e7cb`, rebuild, and subsequent); six remain as tracked tasks (`#76` rediscover, `#91` build-skew detector, F4/F10/F11/F12 selector+premise fixes).

**Top-priority follow-ups:**
1. `HTTPClient.rediscover(pid)` — 3 lifecycle tests failing (task #76)
2. Fix or delete `test_sidebar_new_session_selector_is_in_dom`, `test_send_button_disabled_on_empty_input`, `test_loading_redirects_to_home_within_deadline` — all based on selectors/premises that never matched the product
3. Add a conftest build-skew detector — stale binaries under test were the root cause of 5 of the 10 broken tests in the first sweep (task #91)

---

## Table of contents

1. [Run results](#run-results)
2. [Findings](#findings)
3. [Architecture audit](#architecture-audit) (summarized — full sections in `sections/`)
4. [Cross-cutting observations](#cross-cutting-observations)
5. [Next steps](#next-steps)

---

## Run results

### Final sweep (after all fixes + rebuilt binary)

27 JUnit XML files aggregated via `scripts/flakiness/report.py`:

| Marker | Iters | Stable | Broken / Flaky | Notes |
|---|---|---|---|---|
| unit | 5 | 120 | 0 | 120/120 every run |
| smoke | 5 | 12 | 1 broken | F4 `test_sidebar_new_session_selector_is_in_dom` fails every run |
| surfaces | 3 | 5 | 3 broken | F10/F11/F12 (loading, settings, send-button) |
| ipc | 3 | 58 | 0 | After rebuild + slot-poll helper fix |
| flows | 3 | 2 | 0 (2 skipped — real_backend) |  |
| regression | 3 | 1 | 0 |  |
| broad | 3 | 11 | 0 |  |
| lifecycle | 2 | 0 | 3 broken | F8 (kwarg typo) fixed upstream; F9 (rediscover gap) is now primary cause |

Skipped safely by design (not counted as failures):
- `install_git_macos` Darwin branch, `install_tectonic`, `install_cli` Unix branch — known to spawn modal installers / block webview.
- `test_providers`, `test_onboarding`, `test_tool_use_flow`, etc. — `real_backend` gated on `GPD_TEST_ANTHROPIC_KEY`.
- `test_release_no_mcp` — requires `PYTEST_RELEASE_BUILD=1` + release build.

### Flakiness aggregator output

```
# Flakiness report (27 runs)

## BROKEN
- tests.lifecycle.test_session_list_persistence::test_multiple_sessions_persist — failed all runs
- tests.lifecycle.test_session_persistence::test_session_survives_quit_relaunch — failed all runs
- tests.lifecycle.test_sidecar_respawn::test_sidecar_respawns_after_sigkill — failed all runs
- tests.smoke.test_sidebar::test_sidebar_new_session_selector_is_in_dom — failed all runs
- tests.surfaces.test_dialog_settings::test_settings_opens_via_cmd_comma_and_closes_on_escape — failed all runs
- tests.surfaces.test_loading::test_loading_redirects_to_home_within_deadline — failed all runs
- tests.surfaces.test_session::test_send_button_disabled_on_empty_input — failed all runs

Stable: 221
```

---

## Findings

Each finding is independently verified: we read the test, the product code it exercises, and the harness code it depends on, then assign one label per the triage four-gate methodology.

### Labels used

- **REAL_BUG** — product code has a defect.
- **REGRESSION_ON_BRANCH** — product worked on `origin/gpd` but broke on the branch.
- **PRODUCT_DRIFT_TEST_STALE** — product changed legitimately; test assertion is now wrong.
- **HARNESS_BUG** — test code itself is incorrect; product is fine.
- **FLAKY** — passes and fails intermittently without deterministic cause.

### Findings table

| # | Test / symptom | Label | Status | Commit |
|---|---|---|---|---|
| F1 | `app_state.launch()` raised `RuntimeError: GPD failed to launch` on every test | HARNESS_BUG | fixed | `79233c9` |
| F2 | Every `invoke_via_mcp()` returned `{}` regardless of real command output | HARNESS_BUG | fixed | `c96b9cd` |
| F3 | `test_install_git_macos_platform_gated` opened xcode-select dialog on Darwin | HARNESS_BUG | fixed | `c96b9cd` |
| F4 | `test_sidebar_new_session_selector_is_in_dom` — `[data-action="workspace-new-session"]` not in DOM | HARNESS_BUG | open | — |
| F5 | Stale debug binary failed 2 tex_compiler tests (error-string drift) | HARNESS_BUG (operational) | fixed | rebuild |
| F6 | `test_detect_tex_root_honors_magic_comment` — Python `.format()` KeyError on `{stub}` | HARNESS_BUG | fixed | `7f7e7cb` |
| F7 | Stale debug binary failed 2 `check_project_accessible` tests | HARNESS_BUG (operational) | fixed | rebuild |
| F8 | `test_multiple_sessions_persist` — `wait_quit(timeout=)` kwarg name wrong, cascaded into 2 fixture ERRORs | HARNESS_BUG | fixed | `5ab4699` |
| F9 | 3 lifecycle tests fail because `HTTPClient` has no `rediscover(pid)` post-relaunch | HARNESS_BUG | open (task #76) | — |
| F10 | `test_loading_redirects_to_home_within_deadline` — `/loading` is a separate splash **window**, not a route that auto-redirects | HARNESS_BUG | open | — |
| F11 | `test_settings_opens_via_cmd_comma_and_closes_on_escape` — composite: no post-activate settle + `dialog.active` early-return + mcp execute-js flake | HARNESS_BUG | open | — |
| F12 | `test_send_button_disabled_on_empty_input` — selector `[data-component="button"][type="submit"]` mismatches actual DOM (`data-action="prompt-submit"`) | HARNESS_BUG | open | — |

### F1 — `pgrep` pattern for debug builds

**Symptom:** Every test using `app_state` raised `RuntimeError: GPD failed to launch within 10.0s (matching pids: none)`, though GPD Dev was running.

**Root cause:** `_PGREP_PATTERN = f"{_APP_NAME}.app/Contents/MacOS/{_APP_NAME}"` doubles the bundle name, but Tauri's `tauri.conf.json` has `productName: "GPD Dev"` and `mainBinaryName: "GPD"`. The binary inside `GPD Dev.app` is named `GPD`, so `pgrep -f "GPD Dev.app/Contents/MacOS/GPD Dev"` matches nothing. Release builds accidentally worked because `productName == mainBinaryName == "GPD"`.

**Fix:** Match on the `MacOS/` directory prefix — unique enough, naming-scheme-agnostic.

### F2 — `invoke_via_mcp` never awaited Promises

**Symptom:** Every ipc test returned `{}` for every command.

**Root cause:** The helper wrapped invocations in an async IIFE `(async () => await invoke(...))()`. The vendored `tauri-plugin-mcp` guest-js evaluates submitted code with `new Function('return (${code})')()` and synchronously stringifies the return value. `JSON.stringify(promise)` yields `"{}"` — so every invocation appeared to succeed with an empty dict.

**Fix (`c96b9cd`):** switched to a slot-poll pattern. The submit call stashes the settled result on `window.__gpd_ipc_slot_<n>` and returns `null`; a subsequent `execute_js` polls `JSON.stringify(window[slot])` until `{ok: true, value: ...}` or `{ok: false, err: ...}` appears. Nine unit tests cover submit/poll/settle/error/deadline semantics.

**Why the unit tests missed it:** the MagicMock used in `test_helpers_ipc.py` fed back plausible stringified JSON, bypassing the vendored plugin's Promise-stringify behavior entirely. A live-bridge integration test would have caught it.

### F3 — `install_git_macos` happy path opened a modal dialog

**Symptom:** First alphabetical ipc test invoked `install_git_macos({})` on Darwin → `xcode-select --install` → webview bridge died → every subsequent ipc test timed out with `MCPError: Timeout waiting for JS execution`. The cascade masked F2 (since we never got to a successful invoke).

**Fix (`c96b9cd`):** skip Darwin branch in `test_install_git_macos_platform_gated`; extend similar skips to `install_tectonic` (multi-min network) and `install_cli` (writes `~/.opencode/bin`). The `test_ipc_negative.py` sweep's `_UNSAFE_FOR_NEGATIVE_SWEEP` set was already correct but only governed the parametrized bogus-arg sweep, not dedicated file-specific tests.

### F4 — Stale selector `[data-action="workspace-new-session"]`

**Symptom:** `test_sidebar_new_session_selector_is_in_dom` deterministically failed every smoke iteration (5/5 before fixes, 5/5 after): `AssertionError: sidebar selector not in DOM: False`.

**Root cause:** `gpd_tests/helpers/selectors.py:6` defines `SIDEBAR_NEW_SESSION = '[data-action="workspace-new-session"]'`. Grep of `packages/app/src/` and `packages/desktop/src/` confirms the attribute has never shipped. The convention IS used elsewhere (`prompt-submit`, `settings-language`, etc.) but not for the sidebar new-session trigger. Git log `-S` across all branches shows the selector first appeared in the Phase 1 test-suite commit (`9dc8aed`) as an aspirational assertion.

**Fix path (open):** either (a) delete the test, or (b) replace the selector with one that actually matches the sidebar's new-session button. `packages/app/src/components/titlebar.tsx:275` renders a `<Button icon="new-session">` — adding `data-action="new-session"` to that button would make the test meaningful. Prefer (b) since it's a useful DOM contract.

### F5 — Stale debug binary drove error-string drift

**Symptom:** 2 tex_compiler tests (`test_compile_tex_rejects_missing_source`, `test_parse_tex_log_rejects_missing_file`) failed deterministically with error-message regexes that didn't match.

**Root cause:** The running Tauri sidecar binary was built pre-`64e39c1` ("copy(wave-3): friendly error messages"), while source + tests were post-`64e39c1`. The source said `"LaTeX source file not found: ... hasn't been moved"` but the running binary still emitted `"TeX root file does not exist"`. Tests were correct; binary was stale.

**Fix:** `bun run tauri build --debug` from `packages/desktop/` — rebuild picked up the new error strings. Both tests then passed.

### F6 — Python `.format()` template bug

**Symptom:** `test_detect_tex_root_honors_magic_comment` raised `KeyError: 'stub'` at fixture-build time, before any IPC call.

**Root cause:** `TEX_WITH_MAGIC_ROOT_TEMPLATE.format(root=root.name)` applied to a template containing `\input{stub}` — Python's `str.format` treats `{stub}` as a positional substitution and raises `KeyError`.

**Fix (`7f7e7cb`):** escape as `\input{{stub}}` so `.format()` leaves the literal brace intact.

### F7 — Stale debug binary lacked `check_project_accessible`

**Symptom:** `test_check_project_accessible_happy_path` and `test_command_rejects_bogus_arg_shape[check_project_accessible]` failed every run with `IPCError: Command check_project_accessible not found`.

**Root cause:** The command was added in commit `c14fa7c` at 17:08 today; the running debug binary's mtime was `15:54` (pre-commit). Tests assumed live source; binary was stale. The same rebuild that fixed F5 also fixed these.

**Harness hardening (open, task #91):** add a session-start probe against one sentinel newcomer command to fail fast with "rebuild GPD" rather than surfacing as N per-command regressions.

### F8 — `wait_quit(timeout=)` kwarg name cascade

**Symptom:** 3 lifecycle tests all failed — 1 `FAILED` (test_multiple_sessions_persist) + 2 `ERRORs` (setup of the others).

**Root cause:** `tests/lifecycle/test_session_list_persistence.py:14` called `app_state.wait_quit(timeout=15)` but the real signature is `wait_quit(*, timeout_s=10.0)`. The TypeError raised AFTER `app_state.quit()` was already called — so session-scoped `app_state` was left in a broken state (GPD quit, never relaunched). Every subsequent lifecycle test ERRORed at fixture setup because `http` fixture's pgrep returned no pid. In a second pytest invocation all 3 errored at session-setup on `state.launch()`.

**ERROR vs FAILED signal:** ERROR = setup/fixture raised; FAILED = test body ran and raised. The cascade pattern (first test FAILED, rest ERRORed) confirmed CL-C's diagnosis — if the rediscover gap had been the proximate cause, we'd have seen all 3 FAIL in their bodies at the first post-relaunch `http.xxx()` call.

**Fix (`5ab4699`):** renamed the kwarg to `timeout_s=15`.

### F9 — `HTTPClient` has no `rediscover(pid)` (open, task #76)

**Symptom:** With F8 fixed, the 3 lifecycle tests still fail — now in their bodies rather than cascading from a fixture bug.

**Root cause:** The `http` fixture is function-scoped so it constructs a fresh `HTTPClient` per test with the then-current sidecar port+creds. But mid-test, after `app_state.quit()` + `app_state.launch()`, the sidecar respawns at a new PID with new `OPENCODE_SERVER_PASSWORD` and a new listening port. The existing `HTTPClient` still points at the dead sidecar's address/credentials. First post-relaunch `http.sessions()` fails with connection refused or 401. `test_sidecar_respawns_after_sigkill` works around this with a retry loop, but that pattern doesn't generalize.

**Fix path:**
```python
class HTTPClient:
    def rediscover(self, pid: int) -> None:
        from .opencode_http import discover_sidecar_port, discover_sidecar_credentials
        port = discover_sidecar_port(pid=pid)
        user, pw = discover_sidecar_credentials(pid)
        self._client.close()
        self._client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            auth=(user, pw),
            timeout=self._timeout_s,
        )
```
Then lifecycle tests call `http.rediscover(app_state.sidecar_pid())` after `app_state.wait_launched()` returns.

### F10 — `test_loading_redirects_to_home_within_deadline` — invalid premise

**Symptom:** Test waits for `current_url()` to move off `tauri://localhost/loading` within a deadline; it never does (3/3 runs fail with `last url='tauri://localhost/loading'`).

**Root cause:** `/loading` is a **separate Tauri window** that hosts a splash-screen UI, not a transient SPA route. `packages/desktop/src/entry.tsx` routes by pathname: `/loading` imports `./loading`, else imports `./`. `packages/desktop/src/loading.tsx` only emits a `loadingWindowComplete` event for the Rust host (consumed at `src-tauri/src/lib.rs:633`) so the main window can be shown. No `window.location` mutation, no router `navigate()`. `navigator.py:22–32` already documents this ("MUST NOT wait for `current_url() == route_loading()`"), but the test author didn't read that comment.

**Fix path:** delete the test. There's no "loading→home redirect" to assert. A replacement surfaces-level test could: `mcp.list_windows()` → assert both `main` (visible) and `loading` (visible=false / destroyed) windows.

### F11 — `test_settings_opens_via_cmd_comma_and_closes_on_escape` composite flake

**Symptom:** In the first sweep this was 2/27 pass (1 fail + 2 skips); in the post-fix sweep it's 0/3 (deterministic fail).

**Root cause (three composite sources):**
1. **No settle-wait between `ax.activate()` and the `osascript` keystroke.** Cmd+, can land before GPD becomes frontmost; the keystroke hits whatever app owned focus before the activate.
2. **`command.tsx:358` early-returns if `dialog.active`.** If a prior `steals_focus` test left any modal open, the Cmd+, handler is a no-op. There's no native menu-bar accelerator for Cmd+, in `packages/desktop/src/menu.ts`, so the SolidJS keydown handler is the only path.
3. **MCP execute-js timeouts intermittently** on unrelated paths, observed in the same surfaces XMLs.

**Fix path:** (a) harness: `time.sleep(0.15)` between `ax.activate()` and the keystroke; (b) harness: pre-check `dialog.active` and dismiss any open modal; (c) optional product-side improvement: add a native `MenuItem::Preferences` with `Cmd+,` accelerator in `menu.ts` — macOS users expect it and it'd provide a dialog-state-independent path.

### F12 — `test_send_button_disabled_on_empty_input` — selector mismatch

**Symptom:** Test asserts `true` from a DOM probe that checks if every `button[data-component="button"][type="submit"] , button[data-component="icon-button"][type="submit"]` is disabled. The query returns false because no matching buttons exist.

**Root cause:** The real send button is in `packages/app/src/components/prompt-input.tsx:1424`:
```jsx
<button data-action="prompt-submit" type="submit" disabled={...}>
```
— `data-action="prompt-submit"`, not `data-component="button"`. Same pattern as F4: a speculative attribute convention the product never adopted. The `disabled` prop wiring itself is correct (`disabled={store.mode !== "normal" || (!working() && blank())}` — line 1426).

**Fix path:** change the selector to `button[data-action="prompt-submit"][type="submit"]`. Rerun; expect pass.

---

## Architecture audit

Six audit agents ran in parallel in Phase X1, each producing a section under `sections/`. Full sections retained there; summary:

| Section | File | Words | Headline |
|---|---|---|---|
| Smoke + flows | `sections/audit-smoke-flows.md` | 1,915 | 10 smoke files (14 tests) + 9 flows files (10 tests). 6 red flags — triple-gated tests, silently-skipped tests, permanent xfails |
| Surfaces + regression + broad | `sections/audit-surfaces-regression.md` | 1,743 | 6 surfaces (11 tests) + 1 regression (1 test) + 6 broad (11 tests). 8 red flags — `pages/menu.py` dead; regression is 1 test; broad is 100% read-only |
| IPC + lifecycle | `sections/audit-ipc-lifecycle.md` | 1,712 | 7 ipc files cover 28/28 catalog commands. 3 lifecycle files. `HTTPClient.rediscover` gap flagged (now F9) |
| Unit tests | `sections/audit-unit.md` | 1,446 | 120 tests, 5 modules with no unit tests, `dom_probe.eval_json/int` + `os_input.move` untested |
| Harness architecture | `sections/audit-harness.md` | 2,096 | 2 layering violations (helpers→driver privates), 7 dead-code items |
| Infra | `sections/audit-infra.md` | 2,308 | CI never runs `ipc`/`lifecycle`/`broad`/`harness_selftest` markers. Plan doc drift. Triple build duplication |

---

## Cross-cutting observations

1. **Marker-driven CI gap.** ~88 tests (ipc + lifecycle + broad + harness_selftest) never run in CI. Extend `gpd-tests-gui.yml` with a second job that applies `-m "ipc or lifecycle or broad"` with destructive-skip flags.
2. **Speculative-selector debt.** F4 and F12 are the same pattern: tests written with hypothetical `data-*` attributes that never shipped. Someone (human or agent) should grep every `data-*` selector in `gpd_tests/helpers/selectors.py` against the product tree and either rename or add the attribute.
3. **Stale-binary risk.** 5 of the 10 original failures were operational (sidecar rebuilt would fix them). A session-start probe against one newcomer sentinel command (task #91) would flag this in 2 seconds instead of 5+ minutes.
4. **Unit-test ergonomics vs coverage.** F2 slipped through `test_helpers_ipc.py` because the MagicMock fed back plausible stringified JSON. Unit tests for components that cross the JS bridge need integration-shaped coverage too.
5. **Page-object dead-code debt.** `pages/menu.py`, `drivers/ax.py::MenuItem`, `helpers/navigator.py::route_session`, `helpers/dom_probe.py::eval_{json,int}`, `helpers/i18n.py::t`, `tests/flows/conftest.py::clean_auth_json` — all unused. One PR of deletions.
6. **Two layering violations:** `helpers/sheet.py` → `drivers/ax.py::_osascript`, `pages/app_state.py` → `drivers/mcp.py::_discover_socket_path`. Promote to public API.
7. **Triple-gated tests never run.** `test_onboarding.py` (real_backend + fresh_app + PYTEST_RUN_DESTRUCTIVE_FLOWS) and `test_release_no_mcp.py` (release-build opt-in + bundle-id check) — either wire them in a nightly job or delete them.
8. **`/loading` misconception.** F10 shows that `navigator.py` documents the fact (`/loading` is a window, not a route) but the test was written as though it were a route. Cross-reading existing docs would prevent this class of bug.
9. **Plan doc drift.** `docs/superpowers/plans/2026-04-20-test-harness-triage-methodology.md` still says `scripts/triage.py` is "NOT YET BUILT." Both `scripts/triage.py` and `tests/harness_selftest/` exist.
10. **Triage Gate 4 works.** The `pytest_runtest_makereport` hook we added correctly writes triage hints on failure — an end-to-end check during this run confirmed hint files are generated with product-code commit lists.

---

## Next steps

In priority order:

1. **Land `HTTPClient.rediscover(pid)`** (task #76) + update `http` fixture / lifecycle tests. Unblocks 3 broken tests.
2. **Fix or delete the 4 selector/premise tests** (F4, F10, F11, F12). Two lines per fix.
3. **Add build-skew detector** (task #91). Prevents stale-binary false alarms.
4. **Extend CI** to cover ipc + lifecycle + broad markers.
5. **Delete dead code** (one PR for all of the items from cross-cutting #5).
6. **Promote two layering violations to public API** (cross-cutting #6).
7. **Decide fate of triple-gated tests** (cross-cutting #7) — wire, delete, or document as manual-only.
8. **Update the triage plan doc** (cross-cutting #9) — remove "NOT YET BUILT" labels.
9. **Fix CI "Verify debug bundle" step** (aarch64 target path). Currently blocks fork CI smoke/surfaces/regression jobs.

**Not required:**
- No REAL_BUG or REGRESSION_ON_BRANCH findings surfaced. Product code under test is solid on this branch.
