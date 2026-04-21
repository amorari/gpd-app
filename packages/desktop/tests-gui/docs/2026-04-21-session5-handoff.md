# Session 5 Handoff — 2026-04-21

## What was done this session

### Structural audit → fixes → merge

1. Audited all commits on `feature/gui-test-suite` for structural fragility. Found 10 categories of issues.
2. Implemented fixes across 6 git worktrees in parallel (WI-1 through WI-9):
   - `install-gpd/install`: `chmod 600` profile after writing `GPD_API_KEY`
   - `bootstrap.ts`: removed 50ms timer race in `waitForPaint()`; wrapped `setGlobalStore("ready", true)` in `batch()`
   - `app.tsx`: JSX comment on `<SetupGate>` — must not use Router primitives inside it
   - `conftest.py`: `MCPTimeout | ConnectionRefusedError` in MCP retry; `reset.run()` failure → `pytest.skip`; `refresh_launched_pid()` before `wait_launched()`
   - `opencode_http.py`: platform-aware sidecar credential discovery (`ps -E` Darwin / `/proc` Linux)
   - `seeded_project` fixture: `yield + finally` to prevent session leak
   - `test_ipc_negative.py`: catalog load in try/except → skip instead of collection error
   - `test_harness_invariants.py`: added `test_tauri_commands_fixture_is_fresh`
   - `wait_until`: added `backoff_factor` param
   - `test_abort_flow.py`: replaced `time.sleep(2.5)` with `wait_until` poll for first tokens

3. Full test run result after all fixes:
   ```
   561 passed, 0 unexpected failures, 35 skipped
   16 xfailed (11 product-bug tracking, 5 pending UI anchors)
    1 xpassed (sidebar new-session selector — xfail marker removed)
   199s
   ```

4. Merged everything → `origin/gpd` via PR #6. Rebased `gpd` onto `upstream/gpd`.

### Product bug fixes (open PRs)

Found 11 xfailed tests tracking real product bugs. Fixed 9 of them:

| PR | Repo | Fix | Fixes tests |
|----|------|-----|-------------|
| [amorari#7](https://github.com/amorari/gpd-app/pull/7) / [upstream#7](https://github.com/psi-oss/gpd-app/pull/7) | both | `PATCH /config` 500 → proper error handling | `test_patch_config_*` ×2 |
| [amorari#8](https://github.com/amorari/gpd-app/pull/8) / [upstream#8](https://github.com/psi-oss/gpd-app/pull/8) | both | Sidecar 404 for nonexistent permission/question/session IDs | `test_*_missing_id_*` ×3, `test_get_session_diff_*`, `test_revert_with_fake_*` |
| [amorari#10](https://github.com/amorari/gpd-app/pull/10) / [upstream#9](https://github.com/psi-oss/gpd-app/pull/9) | both | DOM reactivity on session delete + deep link routing to sessions | `test_session_delete_via_ui`, `test_deep_link_session_routes_to_session` |

Also:
- [amorari#9](https://github.com/amorari/gpd-app/pull/9): Rust unit tests for `markdown.rs` (6 tests) and `dependencies.rs` (9 tests) — GPD-fork only, not upstreamed

### Branch/PR cleanup

- Cherry-picked `fix(layout): auto-register project when navigating to /:dir URL directly` onto `gpd`
- Closed stale PR #3 (`sync/gui-test-suite-onto-gpd`) — all its commits were already in `gpd`

---

## Current state

### Branch: `gpd` (fork's main, `origin/gpd`)

Ahead of `upstream/gpd` by 21 commits. All structural fixes + layout fix + merged PR #6 are in here.

To see the delta from upstream:
```bash
git log --oneline upstream/gpd..origin/gpd
```

### Branch: `feature/gui-test-suite`

The original development branch. Has no common git ancestor with `origin/gpd` (the fork was rebased at some point). All useful content from this branch has been cherry-picked into `gpd`. This branch can be archived.

---

## Next steps

### Immediate (merge PRs)

1. **Merge amorari#7** (`fix(config): PATCH /config 500`) then remove xfail from:
   - `tests/flows/test_config_providers.py::test_patch_config_noop_round_trip_preserves_shape`
   - `tests/flows/test_config_providers.py::test_provider_enable_disable_round_trip`

2. **Merge amorari#8** (`fix(server): 404 for invalid IDs`) then remove xfail from:
   - `tests/flows/test_permission_question.py::test_permission_reply_to_missing_id_returns_error`
   - `tests/flows/test_permission_question.py::test_question_reply_to_missing_id_returns_error`
   - `tests/flows/test_permission_question.py::test_question_reject_missing_id_returns_error`
   - `tests/flows/test_session_endpoints.py::test_get_session_diff_without_message_rejected`
   - `tests/flows/test_session_endpoints.py::test_revert_with_fake_message_rejected`

3. **Merge amorari#10** (`fix(app): session delete + deep link`) then remove xfail from:
   - `tests/surfaces/test_session_components.py::test_session_delete_via_ui_removes_from_list`
   - `tests/flows/test_deep_link.py::test_deep_link_session_routes_to_session`

4. **Merge amorari#9** (`test(rust): markdown + dependencies unit tests`)

After all four merges: rebuild GPD Dev.app, rerun the full suite — expected result is **0 xfailed product-bug tests, 0 failed**.

### Remaining xfailed tests (2, by-design)

Two tests are still xfailed after the above merges and are **not bugs** — they reflect a design decision:

```
tests/flows/test_project_workspace.py::test_project_create_via_session_then_list_get_delete
tests/flows/test_project_workspace.py::test_project_update_roundtrip_restores_original
```

Root cause: `GET /project` returns only `['global']` when sessions are created in non-git temp dirs. This is intentional — the sidecar only registers git-rooted directories as named projects. The tests need to be rewritten to use a git-initialized temp directory:

```python
import subprocess

@pytest.fixture
def git_project_dir(tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "--allow-empty", "-m", "init"],
                   check=True, capture_output=True)
    return tmp_path
```

Replace `tmp_path` with `git_project_dir` in both tests and remove their `xfail` markers.

### Upstream PR reviews

PRs have been submitted to `psi-oss/gpd-app`. Watch for review comments:
- upstream#7 — config 500 fix
- upstream#8 — sidecar 404s
- upstream#9 — frontend session delete + deep link

When upstream merges any of these, cherry-pick the resulting merge commit back onto `origin/gpd` and rebase if needed.

---

## How to rebuild and retest

```bash
# Rebuild GPD Dev.app (always use tauri build, never cargo build directly)
cd packages/desktop && bun run tauri build --debug

# Set app path
export GPD_APP_PATH="$(pwd)/src-tauri/target/debug/bundle/macos/GPD Dev.app"

# Launch
open -a "$GPD_APP_PATH"

# Run the full non-backend suite
cd tests-gui
uv run pytest -m "not real_backend and not steals_focus and not restart and not lifecycle" \
  -v --tb=short 2>&1 | tee /tmp/gpd-full-run.log

# Run just the previously-failing tests
uv run pytest \
  tests/flows/test_config_providers.py::test_patch_config_noop_round_trip_preserves_shape \
  tests/flows/test_config_providers.py::test_provider_enable_disable_round_trip \
  tests/flows/test_permission_question.py \
  tests/flows/test_session_endpoints.py::test_get_session_diff_without_message_rejected \
  tests/flows/test_session_endpoints.py::test_revert_with_fake_message_rejected \
  tests/surfaces/test_session_components.py::test_session_delete_via_ui_removes_from_list \
  tests/flows/test_deep_link.py::test_deep_link_session_routes_to_session \
  -v --tb=short --no-header
```

---

## Key file map

| What | Where |
|------|-------|
| pytest harness config | `packages/desktop/tests-gui/pyproject.toml` |
| shared fixtures (mcp, http, reset) | `packages/desktop/tests-gui/conftest.py` |
| timing helpers + `wait_until` | `packages/desktop/tests-gui/gpd_tests/helpers/timings.py` |
| sidecar HTTP client | `packages/desktop/tests-gui/gpd_tests/drivers/opencode_http.py` |
| app lifecycle (launch/quit/wait) | `packages/desktop/tests-gui/gpd_tests/pages/app_state.py` |
| CI workflow | `.github/workflows/gpd-tests-gui.yml` |
| sidecar permission handler | `packages/opencode/src/server/instance/permission.ts` |
| sidecar question handler | `packages/opencode/src/server/instance/question.ts` |
| sidecar session handler | `packages/opencode/src/server/instance/session.ts` |
| sidecar config handler | `packages/opencode/src/server/instance/config.ts` |
| frontend SSE event reducer | `packages/app/src/context/global-sync/event-reducer.ts` |
| frontend deep link parser | `packages/app/src/pages/layout/deep-links.ts` |
| frontend deep link handler | `packages/app/src/pages/layout.tsx` (handleDeepLinks) |
