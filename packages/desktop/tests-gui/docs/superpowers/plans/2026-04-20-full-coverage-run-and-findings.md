# Full-Coverage Run + Findings Document Plan

**Goal:** Produce a master document that (1) catalogs every test in the GPD GUI test suite with coverage/architecture analysis, (2) runs the full live suite N times to collect pass/fail/flake data, (3) independently verifies each finding against the code to explain the root cause.

**Output:** `packages/desktop/tests-gui/docs/findings/2026-04-20-full-coverage-run.md` (new).

**Why this ordering:** Audit first (static) → run second (dynamic) → verify findings (static again, targeted). The audit gives us the shape of the suite so we can interpret run results; the runs tell us what's broken/flaky; the verification gives us explanations.

---

## Phase X1 — Static Audit (parallel agents → master doc sections)

Six agents run in parallel, each produces a markdown section. Sections composed into the findings doc.

| Agent | Scope |
|---|---|
| `audit-smoke-flows` | `tests/smoke/`, `tests/flows/` — what's covered, test shapes, fixtures, product surface hit |
| `audit-surfaces-regression` | `tests/surfaces/`, `tests/regression/`, `tests/broad/` |
| `audit-ipc-lifecycle` | `tests/ipc/`, `tests/lifecycle/` |
| `audit-unit` | `tests_unit/` — driver tests, helper tests, unit coverage matrix |
| `audit-harness` | `gpd_tests/drivers/`, `gpd_tests/helpers/`, `gpd_tests/pages/` — harness architecture |
| `audit-infra` | `scripts/`, `conftest.py`, `pytest.ini`, `.github/workflows/` — infra + CI + triage tooling |

Each agent writes a Markdown section to `packages/desktop/tests-gui/docs/findings/sections/<agent>.md`. Composed after all return.

## Phase X2 — Live-Run Readiness Check

1. Verify GPD Dev.app is launchable + sidecar responds (`mcp` + `http` fixtures green).
2. Snapshot current state for reset hygiene: ensure seed fixture will create auth.json + sentinel; flag if any state is dirty.
3. Baseline unit run to ensure no regression before live runs start.

## Phase X3 — Live Test Runs (serialized — shared GPD instance)

Run each marker group N times, collect JUnit XML per run. Use the E2 aggregator to bucket stable/flaky/broken.

| Marker group | N runs | Reasoning |
|---|---|---|
| unit | 5 | cheap, fast, good baseline flakiness signal |
| smoke | 5 | Phase 1 — core health checks, most load-bearing |
| surfaces | 3 | Phase 2 — page-object sweeps |
| flows (non real_backend) | 3 | Phase 3 — session/onboarding flows |
| ipc | 3 | new contract tests, priority |
| lifecycle | 2 | destructive (quit/relaunch) — expensive |
| regression | 3 | Phase 4 |
| broad | 3 | Phase 5 — big menu sweep |
| real_backend | 1 | if `GPD_TEST_ANTHROPIC_KEY` present, 1 run is enough for now |

All runs: `--junitxml=runs/<marker>-<iter>.xml`, `-v`, `continue-on-error` (we want failures, not aborts).

## Phase X4 — Finding Verification (parallel agents — one per failing test class)

For every test that failed ≥1 run, spawn an agent that:
1. Reads the test code.
2. Reads the touched product code (via catalog + git blame in the last 24h window).
3. Reads the harness code it depends on.
4. Attempts one local re-run; notes whether it reproduces deterministically or intermittently.
5. Classifies per the triage four-gate methodology: FLAKY / HARNESS_BUG / PRODUCT_DRIFT_TEST_STALE / REGRESSION_ON_BRANCH / REAL_BUG.
6. Writes a per-finding markdown file with evidence.

## Phase X5 — Compose Master Findings Document

Structure:

```markdown
# GPD GUI Full-Coverage Run & Findings (2026-04-20)

## Executive summary
- Test counts by marker
- Unit pass rate across N runs
- Integration pass rate per phase
- Top 5 findings by severity

## Architecture audit (from Phase X1)
[merged sections]

## Run results (from Phase X3)
- Flakiness aggregator output per marker group
- JUnit artifact links

## Findings (from Phase X4)
- Table: test id | classification | confidence | PR-reviewable summary
- One subsection per finding with root-cause analysis

## Next steps
- Prioritized fix list (bugs first, flakes next, stale tests last)
```

---

## Execution notes

- Audit agents + live runs start at the same time; audit agents finish quickly so their output lands in the findings doc while runs are still going.
- If GPD Dev isn't running, auto-launch it once (single operation, not per-run).
- Don't push mid-plan; push once the findings doc is committed.
- Rebase onto `origin/gpd` only if there's no merge conflict with in-flight work.
