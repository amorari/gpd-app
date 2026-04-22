# Session 7 Handoff — UI Gap Coverage: 27 new tests, all reviews applied

**Branch:** `test/ui-gap-coverage`
**Date:** 2026-04-21
**Commits this session:** 2 (4fe51265a, 28381d6e9)

---

## What was done

### Starting point

The branch had one upstream merge and no new tests yet. The previous session (6) had cleared all 9 product-bug xfails from the existing suite. This session's mandate was: survey every untested UI surface, write a gap report, then implement new tests and adversarially review each file before committing.

### Gap assessment

`docs/2026-04-21-ui-test-gap-assessment.md` — 8 gap categories identified:

| Category | Gap |
|---|---|
| IPC commands | 8 of ~30 untested (read_license, read_third_party_notices, open_path, etc.) |
| UI surfaces | 7 dialogs at 0% coverage; sidebar actions; terminal panel; settings panel content |
| Keyboard shortcuts | 36 of 37 untested (harness limitation: no chord support) |
| User flows | Slash/@ popovers, send-button transitions, provider enable/disable, multi-setting persistence |
| Regression | Only 1 existing test; 2 critical paths unguarded |
| Prompt flows | All 0% |
| Settings panels | Content (not just tab navigation) at 0% |

### Tests written (27 total, 10 files)

| File | Mark | Tests | What it covers |
|---|---|---|---|
| `tests/ipc/test_bundled_resources.py` | `ipc` | 2 | `read_third_party_notices`, `read_license` IPC commands |
| `tests/regression/test_session_ui_sync.py` | `regression` | 1 | SSE-driven session row disappears after HTTP DELETE |
| `tests/regression/test_project_auto_register.py` | `regression` | 1 | `createEffect` auto-registers project on direct `/:dir` nav |
| `tests/surfaces/test_prompt_flows.py` | `surfaces` | 3 | Slash popover, @-mention popover, send-button state transitions |
| `tests/surfaces/test_terminal_panel.py` | `surfaces` | 3 | Panel toggle (live), new tab (xfail), close button (xfail) |
| `tests/surfaces/test_sidebar_actions.py` | `surfaces` | 3 | Session archive, project workspaces toggle, todo dock toggle (xfail) |
| `tests/surfaces/test_settings_panels_content.py` | `surfaces` | 8 | Keybinds list/record-mode/escape, models list/toggle, dependencies list/check-button/status-icon |
| `tests/surfaces/test_dialogs_group_c.py` | `surfaces` | 3 | dialog-edit-project, dialog-release-notes (xfail), dialog-select-server |
| `tests/flows/test_settings_provider_flows.py` | `flows`/`lifecycle`/`regression` | 3 | Multi-setting persistence across restart, provider enable/disable in UI, config PATCH 4xx regression |

### Adversarial reviews run (9 files reviewed)

Each implementation file was reviewed by a separate `code-reviewer` agent. All CRITICAL and MAJOR findings were applied before committing:

| Finding type | Count applied |
|---|---|
| CRITICAL | 10 |
| MAJOR | 13 |

Key patterns caught:

**`route_project` → SPA redirect timeout** — `route_project(path)` targets `/:dir`; the SPA immediately redirects to `/:dir/session`. `Navigator.go`'s URL-matcher cannot follow path redirects, so it times out. Fixed in 5 files by switching to `route_session_in_project(encode_dir_token(path))`.

**`not bool(None)` = confirmed-closed** — `_poll(lambda: not bool(fn()), ...)` treats `None` (bridge unavailable) as `True` (confirmed closed). Fixed in `test_prompt_flows.py` by using `lambda: fn() is False`.

**No `git init` in fixtures** — The sidecar only registers git directories as projects. Plain `tmp_path` directories are silently ignored, making session creation succeed but project registration fail. Fixed in 3 fixtures with `git init` + `git commit` using inline `user.email`/`user.name` config.

**`UnboundLocalError` on ProbeSkip** — `dialog_still_open` referenced after assignment inside a `try/except ProbeSkip` block; any non-ProbeSkip exception raised `UnboundLocalError`. Fixed by initialising the variable before `try`.

**Vacuous escape-cancels-record-mode test** — When record mode never entered, `in_record_mode=False` branch had `pass`, so the Escape test was asserted on a precondition that never held. Fixed by `pytest.skip()` instead.

**`span.text-14-regular` fallback tautology** — That class appears everywhere in the app (sidebar labels, model names). Removed; only `span.text-14-medium` is specific to dependency check rows.

**`aria-hidden` DOM property vs. attribute** — SolidJS sets `aria-hidden` via the DOM property (`element.ariaHidden`) when the JSX value is a boolean expression. `getAttribute('aria-hidden')` then returns `null`. Fixed in `test_terminal_panel.py` by adding `p.ariaHidden` property fallback.

**`[data-provider-id]` doesn't exist** — That attribute is not rendered by `settings-providers.tsx`. Entire Strategy A replaced by Strategy B (connected-section textContent check).

**`[data-component="dropdown-menu"]` never matches** — Kobalte's DropdownMenu root renders no DOM element. Fixed by keeping only `[role="menu"]`.

**`sidecar_pid()` can return `None`** — Passed unguarded to `rediscover(pid: int)`. Fixed with explicit None check + `pytest.fail`.

**`pytest.fail` inside xfail** — Absorbed as XFAIL, hiding whether the test ever ran. Changed to `pytest.skip()` so PTY-unavailability is separately counted.

---

## Branch state

```
test/ui-gap-coverage
├── 28381d6e9  fix(tests): fix [data-component="dropdown-menu"] selector in dialogs_group_c
├── 4fe51265a  test(gui): add 27 new UI tests across 9 files + gap assessment doc
└── 2db3bf99e  merge: pull upstream fix (Windows liveness probe)
```

All files are committed. Branch is clean.

---

## Known gaps / not yet implemented

### Harness limitations (blocked)

- **Keyboard shortcuts** — `os_input.press_key()` accepts only single unmodified keys; no chord support (e.g. `⌘N`). 36 of 37 shortcuts cannot be tested without either a `press_chord()` helper or `osascript keystroke` wrappers. This is a harness gap, not a product gap.
- **Native file pickers** — `NSOpenPanel` cannot be automated without test hooks injected at the Tauri layer. Blocks file-attach flow tests.
- **Todo dock** — No HTTP endpoint to inject todos into an idle session. `test_session_todo_dock_toggle` is permanently xfail until an injection endpoint is added.
- **Release notes dialog** — Triggered only by `HighlightsProvider` on version change. Help menu item is commented out in `menu.ts`. `test_dialog_release_notes_opens_and_closes` is permanently xfail.
- **Terminal PTY** — ghostty-web WASM unavailable in headless CI. `test_terminal_new_tab_can_be_created` and `test_terminal_tab_has_close_button` are xfail.

### Tier 2 gaps (not yet implemented)

These were in the gap report but were not implemented in this session:

- `open_path` IPC command test (opens native file manager)
- `get_config` / `patch_config` round-trip at field level
- Session archive smoke test via HTTP (separate from sidebar archive test)
- Project clear-notifications action
- Workspace CRUD via HTTP + DOM verification
- SSE stream test for `session.updated` events
- Home-screen empty state (no projects configured)
- `⌘K` command palette (requires chord support)

### Review findings not applied (low priority)

- `_safe_delete` / `_dom_has_session_row` are copy-pasted across 4 files → should live in `gpd_tests/helpers/session_helpers.py` (MINOR refactor, no correctness impact)
- `_poll_until` in `test_settings_panels_content.py` duplicates `wait_until` from `timings.py` (the ProbeSkip-skip-on-first-failure is intentional but aggressive)
- `test_dialog_select_server` server-button heuristic could click the wrong button (wrong click → title check fails → skip, not false-pass; acceptable)

---

## Patterns established this session

### Route navigation
Never use `route_project(path)` with `Navigator.go()` — the SPA redirects `/:dir` → `/:dir/session` and `nav.go` times out. Use:
```python
Navigator(mcp).go(route_session_in_project(encode_dir_token(path)), timeout_s=8.0)
```

### Popover close verification
Never use `not bool(fn())` in a poll lambda. Use `fn() is False`:
```python
closed = _poll(lambda: _slash_popover_visible(probe) is False, timeout_s=2.0)
```

### Git fixtures
Any test that creates sessions or registers projects must use a real git repo:
```python
subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
subprocess.run(
    ["git", "-c", "user.email=test@test.com", "-c", "user.name=Test",
     "commit", "--allow-empty", "-m", "init"],
    cwd=str(p), check=True, capture_output=True,
)
```

### Session cleanup in prompt/flow tests
Any test that creates a session must clean up in `finally`:
```python
sid = http.create_session(directory=path)["id"]
try:
    ...
finally:
    try:
        http.delete_session(sid)
    except Exception:
        pass
```

### SolidJS aria-hidden
SolidJS renders `aria-hidden={boolExpr}` via the DOM property, not `setAttribute`. Use property fallback:
```javascript
const v = el.getAttribute('aria-hidden');
if (v !== null) return v;
return (el.ariaHidden !== undefined) ? String(el.ariaHidden) : null;
```
