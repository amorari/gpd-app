# Session 4 Handoff — 2026-04-21 (evening)

## What was accomplished this session

| Task | Status |
|------|--------|
| PR #3 CI monitoring — sidecar-never-appeared failure investigated | ✅ Investigated (PR #3 then eliminated) |
| Wrote comprehensive test coverage expansion plan | ✅ Done |
| Created `docs/superpowers/plans/2026-04-21-test-coverage-expansion.md` | ✅ Done |

---

## Current branch state

- Branch: `feature/gui-test-suite`
- Latest commit: `352fb9cb3 fix(ci): use mainBinaryName GPD not GPD Dev in bundle verify step`
- Uncommitted: `docs/superpowers/` (new, untracked — the plan)
- PR #3 was eliminated this session

---

## The test coverage expansion plan

**File:** `docs/superpowers/plans/2026-04-21-test-coverage-expansion.md`

This is a 20-task plan organized in two parallel waves. **Nothing has been implemented yet — all tasks are TODO.**

### Summary of what needs to be built

**Wave 1 — 10 agents in parallel (write test files):**

| Agent | Task | Output file |
|-------|------|-------------|
| A1 | TypeScript context unit tests | `packages/app/src/context/permission-auto-respond.test.ts`, `model-variant.test.ts`, `command.test.ts` |
| A2 | Rust backend pure logic unit tests | `#[cfg(test)]` modules in `markdown.rs`, `dependencies.rs` |
| A3 | Extended security tests | `tests/security/test_security_extended.py` |
| A4 | Session lifecycle edge cases | `tests/flows/test_session_edge_cases.py` |
| A5 | IPC coverage gaps | `tests/ipc/test_ipc_coverage_gaps.py` |
| A6 | Surfaces expansion | `tests/surfaces/test_surfaces_expansion.py` |
| E1 | **E2E: 20-turn high-volume session** | `tests/stress/test_e2e_high_volume.py` |
| E2 | **E2E: 5 concurrent sessions** | `tests/stress/test_e2e_concurrent_stress.py` |
| E3 | **E2E: Provider/model switch mid-session** | `tests/stress/test_e2e_provider_failover.py` |
| E4 | **E2E: Error recovery stress** | `tests/stress/test_e2e_error_recovery.py` |

**Wave 2 — 10 agents in parallel (validate + fix + commit each file)**

### Key coverage gaps the plan targets

| Area | Gap |
|------|-----|
| Rust backend | **0 unit tests** — markdown.rs, dependencies.rs pure functions untested |
| TypeScript contexts | permission-auto-respond.ts, model-variant.ts, command.ts have 0 tests |
| E2E stress | **None exist** — no high-volume, concurrency, or failover tests |
| Security | Only 1 test file; missing null-byte, unicode traversal, type confusion, oversized args |
| Session lifecycle | Happy-path only; missing 20-session listing, double-delete, concurrent cycles |

---

## How to execute the plan next session

### Option A: Subagent-driven (recommended)

Use `superpowers:subagent-driven-development`. Dispatch agents for Tasks 1–6 and 7–10 simultaneously (Wave 1), then validate.

### Option B: Inline execution

Use `superpowers:executing-plans`. Read the plan at `docs/superpowers/plans/2026-04-21-test-coverage-expansion.md` and work through tasks with checkpoints.

### Where tests go

All new Python tests go under `packages/desktop/tests-gui/tests/`:
- `tests/stress/` — new directory (needs `__init__.py`)
- `tests/flows/test_session_edge_cases.py`
- `tests/security/test_security_extended.py`
- `tests/ipc/test_ipc_coverage_gaps.py`
- `tests/surfaces/test_surfaces_expansion.py`

TypeScript tests go alongside their source files in `packages/app/src/context/`.

Rust tests are appended to existing `.rs` files as `#[cfg(test)]` modules.

---

## Context on the plan's E2E stress tests

The E2E stress tests (Tasks 7–10) are the most novel additions. They require:
- `@pytest.mark.real_backend` + `anthropic_key` fixture for LLM-involving tests
- The cheapest model (`claude-haiku-4-5-20251001`) is used throughout to minimize cost
- `tests/stress/` needs a `__init__.py` created before writing any test files

The complete test code for all 4 E2E stress tests is already written in the plan — no source reading required for those tasks.

---

## PR / CI state

| Item | State |
|------|-------|
| PR #3 | Eliminated |
| PR #2 (`fix/xss-markdown-unsafe-html`) | **Merged** |
| `feature/gui-test-suite` | Up to date with origin, no uncommitted changes (plan file is untracked) |
| CI workflow | `gpd-tests-gui.yml` — fails at "Launch GPD Dev" (sidecar-never-appeared) on GitHub-hosted runners |

---

## Sidecar-never-appeared CI root cause (for reference)

The "Launch GPD Dev" step polls `pgrep -f "opencode-cli.*serve"` for 15s (30×0.5s). On GitHub-hosted macos-15 runners, `open "${APP_PATH}"` returns immediately but the sidecar (opencode-cli) may take longer than 15s to start cold. The fix would be to either:
1. Increase the poll loop from 30 iterations (15s) to 60 (30s) or 120 (60s)
2. Add a fallback that checks for the sidecar HTTP endpoint (`curl -s http://localhost:PORT/health`) instead of pgrep

This is a separate issue from test coverage expansion — it's a CI infra fix and can be done independently.

---

## Next session checklist

- [ ] Commit `docs/superpowers/plans/2026-04-21-test-coverage-expansion.md` to `feature/gui-test-suite`
- [ ] Execute the plan using `superpowers:subagent-driven-development` (Wave 1: dispatch 10 agents)
- [ ] Commit all new test files to `feature/gui-test-suite`
- [ ] Optionally: fix the sidecar launch poll loop in `gpd-tests-gui.yml` (increase from 30 to 120 iterations)
