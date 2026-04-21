# Session 8 Handoff — Tests written but not yet executed

**Branch:** `test/ui-gap-coverage`
**Date:** 2026-04-21

---

## What happened this session

Short session. The prior session (7) wrote 27 new tests across 9 files, applied all adversarial-review findings, and committed everything. This session established that **none of those 27 tests have been run against a live GPD build**.

Code review caught logic bugs, wrong selectors, and structural issues. It cannot catch:
- Selectors that look correct but don't match the actual rendered DOM
- Timing too tight or too loose for the real app
- `route_session_in_project` signature or behavior differing from assumptions
- HTTP response shapes differing from what tests expect
- Tests that always skip for environmental reasons not anticipated

---

## Immediate next step: run the tests

Suggested order (fail fast, triage by group):

```bash
# 1. Fastest — no UI, pure IPC
pytest -m ipc -v

# 2. Regression — two focused tests
pytest -m regression -v

# 3. Surfaces that don't steal focus (no settings dialog)
pytest -m "surfaces and not steals_focus" -v

# 4. Settings panel tests (steal focus, open dialog)
pytest -m steals_focus -v

# 5. Flows and lifecycle (provider toggle, multi-setting persistence, quit/relaunch)
pytest -m "flows or lifecycle" -v
```

For each failure: determine whether it is a test bug (fix in the test file) or a real product regression (file a bug / add xfail with reason).

---

## Files that need live validation

| File | Main risk |
|---|---|
| `tests/ipc/test_bundled_resources.py` | Low — pure IPC, well-defined contract |
| `tests/regression/test_session_ui_sync.py` | Medium — `[data-session-id]` selector, SSE timing |
| `tests/regression/test_project_auto_register.py` | Medium — `[data-project]` / href / prompt-input fallback selector |
| `tests/surfaces/test_prompt_flows.py` | High — slash/@ popover selectors are heuristic; input event dispatch may not trigger popover |
| `tests/surfaces/test_terminal_panel.py` | Medium — aria-hidden property fallback, height probe |
| `tests/surfaces/test_sidebar_actions.py` | High — project-menu dropdown, workspaces toggle; git repo fixture |
| `tests/surfaces/test_settings_panels_content.py` | High — record-mode CSS class, model switch selectors, dependencies endpoint timing |
| `tests/surfaces/test_dialogs_group_c.py` | High — server-button heuristic, edit-project trigger chain |
| `tests/flows/test_settings_provider_flows.py` | High — lifecycle test requires quit/relaunch; provider DOM check uses textContent |

---

## After tests pass

Once the suite is green (or failures are triaged), the backlog from the gap report:

1. **Add `press_chord()` to the harness** — ~20 lines in `gpd_tests/helpers/os_input.py` wrapping `osascript keystroke`. Unlocks 36 keyboard shortcut tests.
2. **Tier 2 test files** (from gap report):
   - `get_config` / `patch_config` field-level round-trip
   - Workspace CRUD via HTTP + DOM verification
   - SSE `session.updated` event regression test
   - Home-screen empty state
   - `open_path` IPC command
