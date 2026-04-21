# Session 6 Handoff — 2026-04-21

## What was done this session

### CI diagnosis

All 4 open PRs (#7/#8/#9/#10) had failing CI on both `Unit tests` and `Harness self-test invariants`.
Root cause: `tauri_commands.json` was stale relative to `origin/gpd`. After the PRs were created,
`gpd` received new commands (`read_third_party_notices`, `read_license` in `lib.rs`) and line
shifts in `gpd_setup.rs` and `lib.rs`. The `check-compliance`/`check-standards` failures are
upstream team-membership checks that don't affect our fork's mergeability — expected, not actionable.

### Fixture regenerated + PRs merged

1. Regenerated `tauri_commands.json` on `gpd`:
   - +2 new commands: `read_third_party_notices`, `read_license` (both in `lib.rs`)
   - Line shift: `repair_gpd_venv` in `gpd_setup.rs` (123 → 138)
   - Line shift: `wsl_path` in `lib.rs` (270 → 298)

2. Cherry-picked all 4 PR branches onto `gpd` (linear history, one commit each, all clean):
   - `fix(config): handle write error in PATCH /config` — PR #7
   - `fix(server): return 404 for invalid IDs` — PR #8
   - `test(rust): unit tests for markdown.rs + dependencies.rs` — PR #9
   - `fix(frontend): session list + deep link` — PR #10

3. Original PR branches closed with comments.

### xfail markers removed (9 tests)

All product-bug xfails tied to the merged PRs are now removed:

| File | Tests |
|------|-------|
| `test_config_providers.py` | `test_patch_config_noop_round_trip_preserves_shape`, `test_provider_enable_disable_round_trip` |
| `test_permission_question.py` | `test_permission_reply_to_missing_id_returns_error`, `test_question_reply_to_missing_id_returns_error`, `test_question_reject_missing_id_returns_error` |
| `test_session_endpoints.py` | `test_get_session_diff_without_message_rejected`, `test_revert_with_fake_message_rejected` |
| `test_session_components.py` | `test_session_delete_via_ui_removes_from_list` |
| `test_deep_link.py` | `test_deep_link_session_routes_to_session` |

### Project workspace tests fixed

`test_project_create_via_session_then_list_get_delete` and `test_project_update_roundtrip_restores_original`
were xfailed because `GET /project` returned only `['global']` for sessions in non-git temp dirs.

Fix applied:
- Added `git_project_dir` fixture to `conftest.py` (runs `git init` + empty commit on `tmp_path`)
- Both tests now use `git_project_dir` instead of `tmp_path`
- Both `xfail` markers removed

### Unit tests verified locally

```
374 passed, 0 failed  (unit mark)
8 passed, 1 skipped   (harness_selftest mark)
```

All committed and pushed to `origin/gpd` at `a8f781e0d`.

---

## Current state

### Branch: `gpd` (`origin/gpd`)

HEAD: `a8f781e0d`
Ahead of `upstream/gpd` by 28 commits.

```bash
git log --oneline upstream/gpd..origin/gpd
```

### Remaining xfails (5, all by-design)

These are **not product bugs** — they require G5 UI data-action anchors that don't exist yet:

```
tests/surfaces/test_dialogs_group_b.py::test_connect_provider_dialog_*
tests/surfaces/test_dialogs_group_b.py::test_custom_provider_dialog_*
tests/surfaces/test_dialogs_group_b.py::test_manage_models_dialog_*
tests/surfaces/test_dialogs_group_b.py::test_select_mcp_dialog_*
tests/surfaces/test_dialogs_group_a.py::test_select_provider_dialog_*
```

Plus 2 in `test_file_edit_components.py` and 1 in `test_session_components.py` (UI anchor pending).

Do not remove these — they'll xpass only when the frontend adds `data-component`/`data-action` attributes.

### Upstream PRs still open (psi-oss/gpd-app)

- upstream#7 — config 500 fix
- upstream#8 — sidecar 404s
- upstream#9 — frontend session delete + deep link

Watch for review comments. When upstream merges any, cherry-pick onto `origin/gpd`.

---

## Immediate next step: rebuild + full test run

The 9 de-xfailed tests test sidecar and frontend behavior fixed in PRs #7/#8/#10.
They will only pass once GPD Dev.app is rebuilt from the new source.

```bash
# 1. Rebuild (always tauri build, never cargo build directly)
cd packages/desktop && bun run tauri build --debug

# 2. Set app path
export GPD_APP_PATH="$(pwd)/src-tauri/target/debug/bundle/macos/GPD Dev.app"

# 3. Launch
open -a "$GPD_APP_PATH"

# 4. Full non-backend suite
cd tests-gui
uv run pytest -m "not real_backend and not steals_focus and not restart and not lifecycle" \
  -v --tb=short 2>&1 | tee /tmp/gpd-full-run.log

# 5. Run just the 9 formerly-xfailed tests in isolation first
uv run pytest \
  tests/flows/test_config_providers.py::test_patch_config_noop_round_trip_preserves_shape \
  tests/flows/test_config_providers.py::test_provider_enable_disable_round_trip \
  tests/flows/test_permission_question.py::test_permission_reply_to_missing_id_returns_error \
  tests/flows/test_permission_question.py::test_question_reply_to_missing_id_returns_error \
  tests/flows/test_permission_question.py::test_question_reject_missing_id_returns_error \
  tests/flows/test_session_endpoints.py::test_get_session_diff_without_message_rejected \
  tests/flows/test_session_endpoints.py::test_revert_with_fake_message_rejected \
  tests/surfaces/test_session_components.py::test_session_delete_via_ui_removes_from_list \
  tests/flows/test_deep_link.py::test_deep_link_session_routes_to_session \
  -v --tb=short --no-header
```

**Expected result**: 0 unexpected failures, 5 xfailed (UI anchors), everything else passes.

Also run the 2 project workspace tests:
```bash
uv run pytest \
  tests/flows/test_project_workspace.py::test_project_create_via_session_then_list_get_delete \
  tests/flows/test_project_workspace.py::test_project_update_roundtrip_restores_original \
  -v --tb=short
```
These require a live app (they hit the sidecar HTTP API).

---

## Key file map

| What | Where |
|------|-------|
| pytest harness config | `packages/desktop/tests-gui/pyproject.toml` |
| shared fixtures (mcp, http, git_project_dir) | `packages/desktop/tests-gui/conftest.py` |
| tauri commands fixture | `packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json` |
| extractor script | `packages/desktop/tests-gui/scripts/extract_tauri_commands.py` |
| timing helpers + `wait_until` | `packages/desktop/tests-gui/gpd_tests/helpers/timings.py` |
| sidecar HTTP client | `packages/desktop/tests-gui/gpd_tests/drivers/opencode_http.py` |
| CI workflow | `.github/workflows/gpd-tests-gui.yml` |
| sidecar config handler | `packages/opencode/src/server/instance/config.ts` |
| sidecar permission handler | `packages/opencode/src/server/instance/permission.ts` |
| sidecar question handler | `packages/opencode/src/server/instance/question.ts` |
| sidecar session handler | `packages/opencode/src/server/instance/session.ts` |
| frontend session event reducer | `packages/app/src/context/global-sync/event-reducer.ts` |
| frontend deep link handler | `packages/app/src/pages/layout.tsx` |
