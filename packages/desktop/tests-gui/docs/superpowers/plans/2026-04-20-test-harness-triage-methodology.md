# Test Harness Triage Methodology

> **Purpose:** answer "is this failure a real bug, a harness bug, or noise?" for every failing GUI test, deterministically.

## The four-gate protocol

Run gates in order. First gate that produces a label ends triage.

### Gate 1 — Reproducibility

Run the failing test in isolation 5 times.

- Shell: `for i in 1 2 3 4 5; do uv run pytest <nodeid> -q || true; done`
- Pass-rate between 20% and 80% → **FLAKY**. Stop.
- Deterministic pass or deterministic fail → proceed.

### Gate 2 — Manual oracle

Developer performs the test's intent by hand and observes.

- Product behaves as test expects but test still fails → **HARNESS_BUG**. Stop.
- Product misbehaves → proceed.

### Gate 3 — Cross-artifact check

Re-run the test against a known-good reference.

- `export GPD_APP_PATH=/Applications/GPD.app` (release) → re-run.
- Or: `git worktree add .wt-upstream origin/gpd` → re-run there.
- Passes on reference, fails on branch → **REGRESSION_ON_BRANCH** (find with `git bisect`). Stop.
- Fails on reference too → proceed.

### Gate 4 — Product-side evidence

Look at GPD source + logs for the thing under test.

- Feature renamed / moved / removed upstream → **PRODUCT_DRIFT_TEST_STALE** (update test).
- Product logs or code show clear misbehavior → **REAL_BUG** (file ticket).

## Labels and actions

| Label | Action owner | Effort |
|---|---|---|
| `FLAKY` | Test author — add retry or fix timing | S |
| `HARNESS_BUG` | Test author — fix selector/assertion | S–M |
| `REGRESSION_ON_BRANCH` | Whoever introduced it (via `git bisect`) | M |
| `PRODUCT_DRIFT_TEST_STALE` | Test author — update to match new reality | S |
| `REAL_BUG` | Product team (Linear ticket) | varies |

## Supporting infrastructure (to build)

1. **`scripts/triage.py <nodeid>`** — NOT YET BUILT — tracked as an open task. Planned to automate gates 1 and 3: runs the test N times against current build, then N times against `/Applications/GPD.app` release. Emits label to stdout. Target: cut per-failure debug time from ~10 min to ~2 min.

2. **Harness self-tests** at `tests/harness_selftest/` — NOT YET BUILT — tracked as an open task. Planned as a tiny suite (<10 tests) that exercise the harness against invariants GPD can never break (e.g., "MCP `ping` responds", "DOMProbe returns true for `!!document.body`"). Intended to run FIRST; if any fail, the harness itself is broken and all other failures are suspect. Single-digit seconds.

3. **Mutation branch** `feature/gui-test-harness-mutations` — a branch with 5–10 deliberately-introduced product bugs (wrong menu label, broken socket path, disabled send button, etc.). `pytest` on that branch MUST report each mutation. If the harness misses a mutation, it's under-asserting → fix the test, not the product. Run monthly; a calibration exercise.

## Applied once (illustrative)

5 failures from the full-suite run on 2026-04-20:

| Failure | Predicted label | Evidence path |
|---|---|---|
| `test_new_session` → LiteLLM 401 | `REAL_BUG` | Gate 2: paste key into GPD UI manually, observe same 401 |
| `test_app_menu_has_expected_items` → no Settings | `PRODUCT_DRIFT_TEST_STALE` | Gate 4: grep GPD source for Settings menu registration |
| `test_file_menu_close_window_is_enabled` → disabled | `HARNESS_BUG` | Gate 2: activate GPD frontmost → item enables |
| `test_sidebar_new_session_selector` → `'false'` | `HARNESS_BUG` (timing) or `REGRESSION` | Gate 1: repeat 5× |
| `test_dialog_settings` → ⌘, timeout | `HARNESS_BUG` | Gate 4: test sources `"GPD"`, bundle is `"GPD Dev"` |

## Invariant

Every green-suite claim MUST come bundled with: (a) a harness-selftest run that passed first, and (b) no FLAKY or HARNESS_BUG labels produced by the triage tool. Otherwise the green is unverified.
