# GPD Coverage Expansion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking. Every phase fans out multiple implementer subagents in parallel, each operating in its own worktree.

**Goal:** Maximize test coverage of the GPD app from the `tests-gui/` harness alone — no product-code changes. Starting baseline: 56.6% Python harness coverage, 20.6% Rust, ~230 passing tests covering a small slice of the real user-visible surface.

**Scope guardrails (hard):**
- All work lives under `packages/desktop/tests-gui/`. No edits to `packages/app/`, `packages/desktop/src/`, `packages/desktop/src-tauri/src/`, or `packages/opencode/`.
- If a test requires a product-side affordance (data attribute, accessible label, IPC command), stage the proposed product change as a patch under `packages/desktop/tests-gui/docs/gpd-app-patches/<phase>-<slug>.patch` and mark the test `xfail(strict=False)` with a pointer to the patch. Patches go in separate gpd-app PRs later.
- No destructive-by-default tests. Anything that writes to `~/.config/gpd`, `~/.local/share/opencode`, `~/.opencode/bin`, or mutates running sessions must be guarded by an opt-in env var and live behind a dedicated marker.
- Use the `real_backend` marker for anything that hits a live LLM; skip by default.

**Target outcomes:**
- Python harness coverage ≥85% (from 56.6%).
- Rust `cfg(debug_assertions)` command coverage ≥50% (from ~21%, measured against `src-tauri/src/*.rs` via `cargo-llvm-cov`).
- Every Tauri `#[tauri::command]` has at least one **real-behavior** test (not just shape-of-error) where it's safe.
- Every sidecar HTTP route group has at least one round-trip test.
- Every critical user journey (new project, multi-turn chat, abort, compile LaTeX, settings mutation, session deletion, project switching) has an end-to-end test.
- Flakiness cron baseline established — no test >10% flake rate.

**Tech stack:** Python 3.13 + pytest + uv + httpx + AppleScript + cliclick + coverage.py + cargo-llvm-cov.

**Rough effort:** 40-60 hours across 10 phases, heavily parallelized.

---

## Execution model

Each phase has N parallel tasks plus 1 orchestration task. Orchestration (the controller) reads the phase's task list, dispatches implementer subagents concurrently with `isolation: worktree`, monitors completions, and runs a verification sweep after the phase finishes.

**Parallelism rules:**
- Tasks within a phase must touch disjoint file sets. Each phase's task list is curated so agents don't collide.
- Each task is one commit on the worktree branch, auto-merged into `feature/gui-test-suite`.
- Between phases: full unit suite + a targeted live sweep must be green before moving on.
- Coverage instrumentation runs after each phase; the delta drives the next phase's priorities.

---

## Phase G1 — Inventory & Surface Map (parallel audits)

Five agents in parallel produce an authoritative inventory of what the product exposes and what we currently cover.

**Files:**
- New: `packages/desktop/tests-gui/docs/coverage-expansion/inventory/frontend-components.md`
- New: `packages/desktop/tests-gui/docs/coverage-expansion/inventory/sidecar-routes.md`
- New: `packages/desktop/tests-gui/docs/coverage-expansion/inventory/tauri-commands-deep.md`
- New: `packages/desktop/tests-gui/docs/coverage-expansion/inventory/keyboard-and-menus.md`
- New: `packages/desktop/tests-gui/docs/coverage-expansion/inventory/user-journeys.md`

### Task G1.1: Frontend-component inventory
Read every `*.tsx` under `packages/app/src/components/` and `packages/app/src/pages/` (43+ components + 5 pages). For each: name, public props (if any exported interface), interactive elements (buttons, inputs, dialogs), existing `data-action` or stable selectors, and an explicit "testability score" (1-5) based on whether there's a stable DOM anchor. Output a table.

### Task G1.2: Sidecar HTTP route inventory
Enumerate every route handler across `packages/opencode/src/server/**/*.ts`. Known route groups from earlier grep: `/control`, `/project`, `/pty`, `/config`, `/experimental`, `/session`, `/permission`, `/question`, `/provider`, `/mcp`, `/tui`, `/httpapi`, `/workspace`, `/global`. For each: method, path, params, request body shape, response shape, auth requirements, streaming vs unary. Cross-reference `tests-gui/gpd_tests/drivers/opencode_http.py` to mark covered vs not.

### Task G1.3: Tauri command deep-dive
Go beyond the B1 catalog. For each of the 28 commands, document: arg struct (from Rust source), Result<T, E> shapes, side effects (filesystem / network / process), idempotency, and whether it's safe to call in an unattended sweep. Categorize `SAFE`, `SAFE_WITH_FIXTURE`, `UNSAFE` (destructive), `INTERACTIVE` (opens UI).

### Task G1.4: Keyboard shortcuts & menu items
Read `packages/desktop/src/menu.ts` plus any SolidJS key-binding handlers (`packages/app/src/context/command.tsx` and friends). Produce a table of every accelerator + menu item + command. For each: what action it triggers, what should observably happen, whether that outcome is testable via MCP/AX/HTTP.

### Task G1.5: Critical user journeys
From the product docs (README, CHANGELOG, any design docs in `docs/`), compose a list of end-to-end journeys a real user performs. Minimum set: (a) first-run onboarding, (b) create project → chat → abort, (c) multi-turn chat → tool use → file edit, (d) compile LaTeX → read log → edit → recompile, (e) settings change → restart → settings persisted, (f) session fork & branching, (g) project switch, (h) delete session. Rank each by user-facing impact.

---

## Phase G2 — Coverage instrumentation deepening (parallel, 3 tasks)

Coverage baselines are per-file and per-line; we need per-assertion and per-command. Build the infra so later phases can measure their own impact.

### Task G2.1: Branch coverage in Python + target %
Configure `coverage.py` to report branch coverage per module. Add CI gate that fails if total coverage drops below the previous run's floor. Produce a coverage diff summary as a GitHub Actions job summary.

### Task G2.2: Rust `cargo-llvm-cov` targeted-filter harness
`cargo-llvm-cov` can filter by path and function. Build a thin wrapper `scripts/rust_coverage_filter.sh` that takes a command name and reports coverage only for its handler (useful when reviewing a single Tauri-command test's impact). Also add a `--json` flag so other scripts can consume results.

### Task G2.3: Coverage-delta bot
Write `scripts/coverage_delta.py` that compares the current coverage.xml against the previous one (committed as `docs/coverage-expansion/baselines/coverage-*.xml`). Outputs newly-covered lines + newly-uncovered lines. Used as a per-phase verification check.

---

## Phase G3 — Sidecar HTTP round-trip tests (parallel, 6 tasks, one per route-group cluster)

Based on G1.2 output, add real round-trip tests for every route group currently thin or absent. Each task is one test file.

### Task G3.1: `/session/*` deep coverage
Create/expand `tests/flows/test_session_endpoints.py`: create, get-by-id, list with directory filter, list unscoped, update metadata, delete, attempt-delete-nonexistent, delete-twice, fork, get messages, get individual message, delete message. Real HTTP, no LLM calls.

### Task G3.2: `/config/*` and `/provider/*`
Create `tests/flows/test_config_providers.py`: get config, update config, list providers, provider enable/disable, model selection, auth key storage (mock the actual key — we're testing the storage contract, not a real key).

### Task G3.3: `/project/*` and `/workspace/*`
Create `tests/flows/test_project_workspace.py`: workspace CRUD, project CRUD, project switch, workspace-level state persistence across restart.

### Task G3.4: `/mcp/*` and `/experimental/*`
Create `tests/flows/test_mcp_experimental.py`: MCP list servers, MCP invoke server tool, experimental flags read, experimental flag mutation. Guard destructive mutations behind opt-in.

### Task G3.5: `/permission/*` and `/question/*`
Create `tests/flows/test_permission_question.py`: permission prompt lifecycle (ask, respond, observe state), question routing.

### Task G3.6: `/global/*` and `/control/*`
Create `tests/flows/test_global_control.py`: health (already exists — keep short), version, shutdown (opt-in), log routing.

---

## Phase G4 — Tauri IPC deep tests (parallel, 4 tasks)

The current ipc tests are happy-path shape checks. Expand to real behavior on the commands that are safe.

### Task G4.1: `project_fs` deep behavior
Happy-path tests for every command: create→read→write→list→delete a project dir under tmp_path. Test path-traversal rejection (`../etc/passwd`, symlinks). Real file I/O under fixture-managed tmp dir.

### Task G4.2: `tex_compiler` deep behavior
End-to-end: write a tiny .tex → invoke `compile_tex` → read the produced PDF bytes → invoke `parse_tex_log` on the generated log → assert the log parser extracts expected warnings. Tolerate absence of `tectonic` via skip.

### Task G4.3: `server` / `cli` / `markdown` deep behavior
Round-trip tests for server port + config fetch, cli install (skipped on live machines unless `PYTEST_OPTIN_MUTATE_SYSTEM=1`), markdown rendering of a canonical fixture including tables, code blocks, math, and images.

### Task G4.4: `lib.rs` state mutations with restore
For `set_display_backend` and any other state-mutation command: read-before → set → read-after → restore. Already partially done in B6; deepen and add error-path tests (invalid values).

---

## Phase G5 — Frontend component interaction tests (parallel, 8 tasks)

Driven by G1.1's testability table. For every component rated 3+ (has stable anchors), add surfaces-level interaction tests.

### Task G5.1: Dialog components (group A)
`dialog-select-model`, `dialog-select-provider`, `dialog-settings`. Open → interact → close → observe state.

### Task G5.2: Dialog components (group B)
`dialog-connect-provider`, `dialog-custom-provider`, `dialog-manage-models`, `dialog-select-mcp`.

### Task G5.3: Dialog components (group C)
`dialog-open-or-create-project`, `dialog-edit-project`, `dialog-confirm-delete-project`, `dialog-fork`.

### Task G5.4: `prompt-input` deep coverage
Text entry, attach file, agent switch, model switch, model-variant switch, submit, cancel. All via MCP execute_js + data-action selectors.

### Task G5.5: `session` components
Session list rendering, session item click, session rename, session delete, session metadata.

### Task G5.6: `file-edit` components
Open file, edit, save, discard. Against a temp fixture.

### Task G5.7: `titlebar` & `sidebar`
Title bar actions (minimize, close, new session). Sidebar workspace list, project switch.

### Task G5.8: `settings-*` components
`settings-general`, `settings-agents`, `settings-commands`, `settings-gpd`, `settings-mcp`, `settings-providers`. Read-only assertions of what's rendered; change a value and verify persistence via sidecar.

---

## Phase G6 — End-to-end user journeys (parallel, 6 tasks)

From G1.5's ranked list. Each journey is one test file that composes multiple product interactions.

### Task G6.1: First-run onboarding (fresh_app + real_backend)
Wire the triple-gated `test_onboarding.py` into a non-destructive variant that still validates the flow: fresh tier-2 reset → welcome screen → paste API key → land on home → verify sentinel + auth.json both written. Remove the `PYTEST_RUN_DESTRUCTIVE_FLOWS` gate once we've proven the reset is idempotent.

### Task G6.2: New-project journey
Open app → create project via dialog → navigate to home of new project → verify the workspace list shows it → delete.

### Task G6.3: Multi-turn chat with tool use
Extends existing `test_tool_use_flow`: send 3 prompts where 2nd requires the assistant to read a file and the 3rd to write one. Verify both happen against a tmp_path under the session's directory.

### Task G6.4: LaTeX compile-edit-recompile
Create `.tex` under tmp project → `compile_tex` → read log → edit source → recompile → assert diff in output. Guard behind `tectonic` availability.

### Task G6.5: Settings persistence across restart
Change theme → quit → relaunch → verify theme persists. Already partially covered by `test_theme_switch.py`; extend to include provider selection and language.

### Task G6.6: Session fork & branching
Create session → send 2 prompts → fork from after prompt 1 → verify both sessions share the first message but diverge after.

---

## Phase G7 — New test types (parallel, 4 tasks)

### Task G7.1: Visual-regression baseline
Capture baseline screenshots for welcome, home, session, settings dialog. Store under `tests/visual/baselines/macos15-arm64/*.png`. Add a `@pytest.mark.visual` test per baseline using PIL pixel-diff with a tolerance config.

### Task G7.2: Property-based fixtures
Use `hypothesis` for session-message payload generation: random assistant-text fragments, random agent names, random model IDs. Run a property-based test against `messages()` to assert `extract_text` never crashes and always returns a string.

### Task G7.3: Mutation-test scaffolding
Add `mutmut` or `mutatest` config. Don't run full mutation testing (too expensive); instead, wire it up so a specific CI job can target a single module and report survived mutants.

### Task G7.4: Security-focused IPC tests
Path traversal (`../`, absolute outside project root), symbolic-link attacks, command injection into TeX compiler (e.g. `\input{|rm -rf /}`), script injection into markdown renderer. Add to a new file `tests/security/test_ipc_boundaries.py` with marker `@pytest.mark.security`.

---

## Phase G8 — Activate dormant tests & extend CI

### Task G8.1: Unlock `test_onboarding.py`
Collapse the triple-gate into a single gate (real_backend), and add a nightly CI job that runs it. The `fresh_app` reset logic is safe; `PYTEST_RUN_DESTRUCTIVE_FLOWS` is redundant.

### Task G8.2: Release-build smoke
Add a weekly CI job that builds a release bundle, launches it, and runs the `test_release_no_mcp.py` suite. Produces the artifact so humans can inspect it.

### Task G8.3: Nightly real-backend real-flow job
Build on the flakiness cron. A separate job runs the full `real_backend` marker with the live LLM key (gated on a secret). Produces cost-per-run report.

### Task G8.4: Harness-selftest CI job
Wire `tests/harness_selftest/` into CI so every green claim is paired with a harness-selftest pass.

---

## Phase G9 — Close coverage gaps surfaced by G2 runs

Driven by `scripts/coverage_delta.py` outputs. Fan out N agents (one per module with coverage <70%) to write targeted tests. Coverage reports from G2 tell us exactly which branches are uncovered.

**Candidate modules (from Phase A baseline):**
- `pages/menu.py` (0%) — delete if confirmed dead (already flagged)
- `pages/onboarding.py` (0%) — covered by live tests but not by unit suite; add unit tests for `sentinel_path`, helpers
- `pages/app_state.py` (20.7%) — unit tests for `launch`/`quit`/`kill_stale`/`wait_launched` with mocked subprocess
- `drivers/opencode_http.py` (49%) — unit tests for remaining methods (`abort`, `rediscover`, etc.)
- `drivers/os_input.py` (53.4%) — unit tests for each `press_key` / `move` / `type_text` branch, mocked subprocess

## Phase G10 — Final verification & documentation

### Task G10.1: Full 50-iteration live sweep
Run every marker group 10× instead of 3-5×. Aggregate via the flakiness script. Any test flaking ≥20% gets auto-quarantined with a comment.

### Task G10.2: Coverage final baseline
Regenerate Python + Rust coverage reports. Commit them under `docs/coverage-expansion/baselines/2026-04-<day>/`. Update `docs/findings/2026-04-20-full-coverage-run.md` with the final numbers.

### Task G10.3: Write master results doc
New file: `docs/coverage-expansion/2026-04-<day>-expansion-results.md`. Sections: before/after coverage numbers, new test counts per marker, discovered bugs (expected: mostly harness, some real product regressions), per-phase summary, pending gpd-app PR patches.

### Task G10.4: Update README + CLAUDE.md
Reflect the new markers, the new CI jobs, the new coverage floor.

---

## Risk register

| Risk | Mitigation |
|---|---|
| Product code genuinely lacks stable DOM anchors for many components | Stage patches under `docs/gpd-app-patches/`; xfail tests pointing at them |
| Sidecar endpoints have undocumented response shapes | Phase G1.2 reads source directly; deep tests only assert the shape we observe |
| Visual baselines differ by macOS version | Keep baselines in OS-version-specific subdirs; fall back to tolerance on unknown envs |
| LLM costs for real_backend jobs | Cap with a token-budget env var; track per-run cost |
| CI runtime balloons | Parallelize across macos-15 runners; aggressive skipping of destructive paths; share the debug bundle across jobs once the artifact-based sharing is working |
| Test flakiness goes up before down | Run the flakiness cron nightly from the start; quarantine, don't delete |

---

## Phase execution order

```
G1 (parallel 5) → G2 (parallel 3) → G3 (parallel 6) → G4 (parallel 4)
                                                              ↓
G10 (parallel 4) ← G9 (parallel N) ← G8 (parallel 4) ← G7 (parallel 4) ← G5 (parallel 8) → G6 (parallel 6)
```

G6 can run concurrently with G5 once G1+G2 land. G7-G9 depend on G3-G6 having test data to measure against.

Between every phase:
1. `uv run pytest tests_unit -q` → all green.
2. Targeted live sweep of the phase's new markers → no new BROKEN.
3. Coverage delta snapshot — commit under `docs/coverage-expansion/baselines/`.

Between G5 and G6: pause for human review of the auto-applied changes.

---

## Checkbox-tracked execution

### Phase G1 (parallel)
- [ ] G1.1 frontend-components inventory
- [ ] G1.2 sidecar-routes inventory
- [ ] G1.3 tauri-commands-deep inventory
- [ ] G1.4 keyboard & menus inventory
- [ ] G1.5 user journeys inventory
- [ ] G1.v verify all 5 files exist + have ≥500 words

### Phase G2 (parallel)
- [ ] G2.1 branch coverage + CI gate
- [ ] G2.2 rust_coverage_filter.sh + --json
- [ ] G2.3 coverage_delta.py + tests
- [ ] G2.v run full coverage once, commit baseline under `docs/coverage-expansion/baselines/`

### Phase G3 (parallel)
- [ ] G3.1 /session deep
- [ ] G3.2 /config + /provider
- [ ] G3.3 /project + /workspace
- [ ] G3.4 /mcp + /experimental
- [ ] G3.5 /permission + /question
- [ ] G3.6 /global + /control
- [ ] G3.v live sweep of new flows tests

### Phase G4 (parallel)
- [ ] G4.1 project_fs deep behavior
- [ ] G4.2 tex_compiler deep behavior
- [ ] G4.3 server/cli/markdown deep behavior
- [ ] G4.4 lib.rs state-mutation + restore
- [ ] G4.v live sweep of new ipc tests

### Phase G5 (parallel 8)
- [ ] G5.1 dialogs group A
- [ ] G5.2 dialogs group B
- [ ] G5.3 dialogs group C
- [ ] G5.4 prompt-input deep
- [ ] G5.5 session components
- [ ] G5.6 file-edit components
- [ ] G5.7 titlebar & sidebar
- [ ] G5.8 settings-* components
- [ ] G5.v live sweep of surfaces

### Phase G6 (parallel, concurrent with G5)
- [ ] G6.1 onboarding (ungate)
- [ ] G6.2 new project journey
- [ ] G6.3 multi-turn with tool use
- [ ] G6.4 LaTeX compile-edit-recompile
- [ ] G6.5 settings persistence across restart
- [ ] G6.6 session fork & branching
- [ ] G6.v live sweep

### Phase G7 (parallel)
- [ ] G7.1 visual baselines
- [ ] G7.2 hypothesis property tests
- [ ] G7.3 mutmut scaffolding
- [ ] G7.4 security-boundary tests

### Phase G8 (parallel)
- [ ] G8.1 onboarding ungate + nightly CI
- [ ] G8.2 release-build weekly CI
- [ ] G8.3 real-backend nightly CI + cost report
- [ ] G8.4 harness-selftest CI job

### Phase G9 (parallel N)
- [ ] G9.1 delete menu.py if confirmed dead
- [ ] G9.2 unit tests for onboarding helpers
- [ ] G9.3 unit tests for app_state launch/quit/kill_stale/wait_launched
- [ ] G9.4 unit tests for opencode_http remaining methods
- [ ] G9.5 unit tests for os_input branches
- [ ] G9.v Python coverage ≥85% achieved

### Phase G10
- [ ] G10.1 50-iteration flakiness sweep
- [ ] G10.2 final coverage baseline
- [ ] G10.3 expansion-results master doc
- [ ] G10.4 README + CLAUDE.md updated

---

## Success criteria

This plan is DONE when:

- Python harness coverage is ≥85% (branch+line).
- Rust coverage of debug-build-only code is ≥50%.
- Every Tauri `#[tauri::command]` has a real-behavior test or a documented SAFE_WITH_FIXTURE / UNSAFE / INTERACTIVE classification.
- Every sidecar route group has a round-trip test.
- The six ranked user journeys from G1.5 each have a dedicated test file.
- The flakiness cron reports <10% flake rate on all markers for 3 consecutive nightlies.
- `docs/coverage-expansion/2026-04-<day>-expansion-results.md` exists with full numbers.
- Any discovered product bug is captured as a patch under `docs/gpd-app-patches/` and the related test is xfail.

---

## Results section (fill in as phases complete)

### Phase G1 results
_TBD_

### Phase G2 results
_TBD_

### Phase G3 results
_TBD_

### Phase G4 results
_TBD_

### Phase G5 results
_TBD_

### Phase G6 results
_TBD_

### Phase G7 results
_TBD_

### Phase G8 results
_TBD_

### Phase G9 results
_TBD_

### Phase G10 results
_TBD_

---

## Discovered product issues (to be submitted as PRs to gpd-app)

_Each entry: patch path, 1-line description, linked test id that will pass once applied._

_None yet._
