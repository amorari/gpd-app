# Audit: Surfaces + Regression + Broad

Scope: `tests/surfaces/` (Phase 2), `tests/regression/` (Phase 4), `tests/broad/` (Phase 5), plus page objects in `gpd_tests/pages/` consumed by these suites.

## Surfaces (Phase 2)

Surfaces tests drive the SPA router and assert minimal "this surface rendered" signals per top-level route/dialog. They don't exercise business flows — only structural presence. All tests are marked `@pytest.mark.surfaces`.

### Test files + what they validate

| File | Test | Validation |
|---|---|---|
| `test_home.py` | `test_home_route_reachable` | `Navigator.go(route_home())` lands on `/` and `current_url()` matches. |
| `test_home.py` | `test_sidebar_new_session_selector_present_on_home` | `[data-action="workspace-new-session"]` is in the DOM on `/`; guards against a vacuous-true when sidebar shell hasn't rendered by also requiring non-empty body text. Skips gracefully if welcome overlay is blocking. |
| `test_loading.py` | `test_loading_redirects_to_home_within_deadline` | `/loading` redirects to `/` within 10s (fire-and-forget; uses `mcp.navigate` directly because `/loading` is not a stable SPA route). |
| `test_project.py` | `test_project_route_reachable` | Navigates to `route_project(tmp_path)`; asserts `encode_dir_token` appears in `current_url()`. |
| `test_project.py` | `test_project_route_navigation_back_to_home_works` | Round-trip nav project → home; asserts URL equals `route_home()`. |
| `test_project.py` | `test_session_created_for_project_dir_appears_in_session_list` | HTTP-only: `http.create_session(directory=tmp)` registers project implicitly, session id retrievable via `GET /session`. |
| `test_session.py` | `test_session_route_reachable` | `/session` is in `current_url()` after navigating to `route_session_in_project(token)`. |
| `test_session.py` | `test_composer_placeholder_present` | Composer input with `placeholder == TEXT_PROMPT_PLACEHOLDER` exists. Skips if overlay hides it. |
| `test_session.py` | `test_send_button_disabled_on_empty_input` | All `button[type=submit]` (both `button` and `icon-button` data-component variants) are `disabled` or `aria-disabled=true` on empty composer. |
| `test_dialog_settings.py` | `test_settings_opens_via_cmd_comma_and_closes_on_escape` | `@pytest.mark.steals_focus`. Activates GPD via AX, sends ⌘, via `osascript`, polls for a `"General"` tab, then presses ESC and re-asserts the tab is gone. |
| `test_dialog_open_or_create_project.py` | `test_open_or_create_project_dialog_opens_from_home` | Finds a home button matching `/open.*create|create.*project|new project/i`, clicks it, polls body text for the combined-picker strings (`open or create`, `open existing folder`, `create new folder`). |

### Page objects invoked

None. The surfaces suite does **not** consume `gpd_tests/pages/` at all. Instead it uses:
- `gpd_tests.helpers.navigator.Navigator` + `route_home` / `route_project` / `route_session_in_project` / `route_loading` / `encode_dir_token`
- `gpd_tests.helpers.dom_probe.DOMProbe` + `ProbeSkip`
- `gpd_tests.helpers.selectors.SIDEBAR_NEW_SESSION`, `TEXT_PROMPT_PLACEHOLDER`
- `http` (from root conftest) for the non-routing `GET /session` test
- `ax` + `os_input` (from root conftest) for the ⌘, + ESC settings test

The local `tests/surfaces/conftest.py` provides `nav` and `dom` fixtures that wrap `Navigator(mcp)` and `DOMProbe(mcp)` — but **neither fixture is ever used**; every test instantiates `Navigator`/`DOMProbe` inline. This is dead code.

### Known gaps

- `/project` and `/session` surface tests only check URL substrings, not that the project view actually renders anything (no data-component / title assertion).
- `test_composer_placeholder_present` and `test_sidebar_new_session_selector_present_on_home` both **skip** (don't fail) when a welcome overlay is up. On a freshly-onboarded runner the surfaces suite is mostly green trivially.
- Settings dialog test is the only one that actually exercises a keybinding path through the real menu — the other dialog test clicks a DOM button. Parity on invocation paths is inconsistent.
- No surface test for: deep-link URLs, 404/unknown route, multi-window surfaces, command palette, provider-picker dialog, theme switcher dialog.
- `test_open_or_create_project_dialog_opens_from_home` uses a loose regex to find the button; if that string shifts the test silently skips (doesn't fail) on "button not found". Masks real regressions.
- `DOMProbe` is re-instantiated inside every test even though `conftest.py` defines a `dom` fixture that does the same thing.

## Regression (Phase 4)

Single-file directory; captures specific past bugs with pinpoint log-assertion tests rather than behavioral tests.

### Test files + what they validate

| File | Test | Validation |
|---|---|---|
| `test_empty_accelerator_token.py` | `test_no_empty_accelerator_token_on_fresh_launch` | Reads the most recent `opencode-desktop_*.log` under `~/Library/Logs/inc.psi.gpd{,.dev,.beta}/` and asserts `"Found empty token while parsing accelerator"` is absent. Skips if no log dir exists. Depends on `app_state` fixture for launch ordering. |

### What regressions they're designed to catch (inferred from test docstring / assertions)

- A Tauri accelerator string that loses its `Cmd`/`Ctrl`/etc. modifier (e.g. `accelerator: ""` or `key: ""` without a chord) — Tauri's parser emits the needle on startup. Docstring explicitly flags this as "confirmed via `strings` on the compiled GPD app", so the bug was caught empirically and pinned.

### Known gaps

- **Only one regression** in the directory. Phase 4's charter was "pinpoint tests for past bugs" — as more are fixed they should land here, but nothing else has been added.
- The assertion is log-based rather than behavioral: an accelerator could be registered to a no-op and this test would still pass. Only catches the *parser-error* spelling of the bug.
- No regression test for the Tauri removal work (2370dc5) or TeX/preview fixes (0fb3e62) — recent commits suggest opportunities that weren't taken.
- Skips silently when log dir is missing. A CI runner on a clean profile would report green without actually asserting anything.

## Broad (Phase 5)

AX-driven sweep over the macOS menu bar. Every test uses `gpd_tests.drivers.ax.AXClient` (injected via the `ax` fixture) and is marked `@pytest.mark.broad`. Tests assert *concepts* (using candidate lists like `["New Conversation", "New Session"]`) so i18n/copy sweeps don't wreck the suite.

### Test files + what they validate

| File | Test | Validation |
|---|---|---|
| `test_menu_sweep.py` | `test_every_top_level_menu_has_at_least_one_item` | All GPD-owned top-level menus (excluding system "Apple") have ≥1 item. |
| `test_menu_sweep.py` | `test_top_level_menu_set_is_reasonable` | `{File, Edit, View, Help}` all present; one of `{GPD, GPD Dev, GPD Beta}` is present as app menu. |
| `test_menu_app_items.py` | `test_app_menu_present` | Finds app menu by candidate name. |
| `test_menu_app_items.py` | `test_app_menu_has_expected_items` | Matches "About …" and "Quit …" concept groups. |
| `test_menu_app_items.py` | `test_app_menu_quit_is_enabled` | Quit entry is in `enabled_items_of`. |
| `test_menu_file_items.py` | `test_file_menu_has_expected_items` | Groups: new-conversation, open-project, close-window. At least one per group. |
| `test_menu_file_items.py` | `test_file_menu_close_window_is_enabled_when_window_exists` | "Close Window" enabled; skips if not present. |
| `test_menu_edit_items.py` | `test_edit_menu_has_standard_clipboard_items` | Undo/Redo/Cut/Copy/Paste/Select All concepts all present. |
| `test_menu_view_items.py` | `test_view_menu_non_empty` | View has ≥1 item. |
| `test_menu_view_items.py` | `test_view_menu_has_at_least_one_typical_group` | At least one of: Toggle Sidebar, Toggle Command Prompt/Terminal, Back, Forward, Previous/Next Conversation. |
| `test_menu_help_items.py` | `test_help_menu_non_empty` | Help has ≥1 item (AppKit auto-gives Search). |

### Scope (menu items, shortcuts, windows, etc.)

- **Covered**: presence of top-level menus, existence + enabled-state of standard items in App / File / Edit / View / Help menus, candidate-based concept matching (i18n-tolerant).
- **Not covered**: actual keyboard shortcuts (no ⌘-accelerator round-trip test), invoking menu items (no `ax.click_item` calls — only presence/enabled queries), Window menu, context menus (right-click), Services menu, any secondary windows' menu state.
- No test asserts that the *accelerator* attached to a menu item works. This is complementary to the regression test, which only checks the parser-error log string.

### Page objects invoked

None directly. `gpd_tests/pages/menu.py` (`Menu` class with `top_level()`, `pairs()`, `enabled_pairs()` helpers) exists but is **never imported**. Tests talk to `AXClient` directly and re-implement their own filtering (e.g. `test_menu_sweep.py` inlines the "Apple" filter that `Menu.SYSTEM_MENUS` already encapsulates).

`tests/broad/conftest.py` is a docstring-only file (no fixtures).

### Known gaps (which menus/shortcuts aren't covered)

- **Window menu**: no test file. macOS apps typically expose Minimize, Zoom, Bring All to Front — none asserted.
- **Shortcuts/accelerators**: zero broad-suite coverage. `test_dialog_settings` in surfaces is the only ⌘-key roundtrip in the three audited dirs.
- **Context menus**: completely unaudited.
- **Menu item invocation**: every broad test is a read; none fire an action and assert a side effect. (e.g. Edit > Copy with a selection, File > Close Window and assert a window closed, View > Toggle Sidebar and assert visibility flipped.)
- **Menu enabled-state transitions**: "Close Window" enabled is checked, but only when a window exists. No test for the disabled state after all windows close.
- **Custom/dynamic items**: anything driven by workspace state (recent files, theme picker, provider submenu) is unaudited.
- `test_top_level_menu_set_is_reasonable` and `test_every_top_level_menu_has_at_least_one_item` partially overlap with `tests/smoke/test_menu_bar.py::test_top_level_menus_match_expected_set` — see redundancy flag below.

## Page object coverage matrix

| Page object class | File | Test files that use it | Coverage % guess |
|---|---|---|---|
| `AppState` | `gpd_tests/pages/app_state.py` | `conftest.py` (root: `app_state` + `fresh_app` fixtures), `tests_unit/test_app_state.py`, `tests/lifecycle/test_session_persistence.py`, `tests/lifecycle/test_session_list_persistence.py`, `tests/lifecycle/test_sidecar_respawn.py`, `tests/smoke/test_launch.py`, `tests/smoke/test_restart.py`, `tests/regression/test_empty_accelerator_token.py` (indirect via `app_state` fixture) | ~80% — public API (`is_running`, `gpd_pid`, `sidecar_pid`, `kill_stale`, `launch`, `quit`, `wait_launched`, `wait_quit`, `refresh_launched_pid`) broadly exercised; `sidecar_pid` ppid-fallback edge case (return-None branch) likely not hit. |
| `Onboarding` | `gpd_tests/pages/onboarding.py` | `tests/flows/test_onboarding.py`, `tests/smoke/test_first_run.py` (uses `sentinel_path` only), root `conftest.py` (uses `sentinel_path` only) | ~40% — only one test exercises `welcome_visible` / `enter_api_key` / `wait_for_home`; the `no-input` / `no-submit-target` error branches in `enter_api_key` are not covered. `sentinel_path` is what most callers use. |
| `Menu` | `gpd_tests/pages/menu.py` | **None** | **0% — page object is unused**. Broad tests re-implement `top_level()` filtering inline against `AXClient.top_level_menus()`. Candidate for deletion or adoption. |

## Test count summary

- **surfaces**: 6 files, 11 tests (1 conftest + 6 test files; 11 `test_*` functions total)
- **regression**: 1 file, 1 test
- **broad**: 6 files, 11 tests (1 conftest + 6 test files; 11 `test_*` functions total) — "menu_sweep" / "menu_app_items" / "menu_file_items" / "menu_edit_items" / "menu_view_items" / "menu_help_items"

Combined: **13 files, 23 tests** across the three audited suites.

## Red flags

1. **`gpd_tests/pages/menu.py` is dead code.** Zero imports anywhere in the repo. Either wire it into the broad suite (replace the inline Apple filter and AX iteration) or delete it.
2. **`tests/surfaces/conftest.py` `nav` and `dom` fixtures are unused.** Every surfaces test instantiates `Navigator(mcp)` / `DOMProbe(mcp)` inline. Migrate or delete.
3. **Broad ↔ smoke redundancy on top-level menu presence.**
   - `tests/smoke/test_menu_bar.py::test_top_level_menus_match_expected_set` asserts `{File, Edit, View, Help}` + app menu.
   - `tests/broad/test_menu_sweep.py::test_top_level_menu_set_is_reasonable` asserts the exact same thing.
   One of them should go; the broad version is stricter (also checks non-empty) so the smoke version is the deletion candidate.
4. **Smoke ↔ surfaces redundancy on sidebar selector.**
   - `tests/smoke/test_sidebar.py::test_sidebar_new_session_selector_is_in_dom` — selector in DOM.
   - `tests/surfaces/test_home.py::test_sidebar_new_session_selector_present_on_home` — same selector + non-empty body.
   The surfaces version is a strict superset.
5. **Regression suite is a directory of one.** Either commit to the pattern (every fixed Tauri/menu bug gets a pinpoint test) or fold the single test into smoke.
6. **Silent skips masquerade as passes.** `test_no_empty_accelerator_token_on_fresh_launch` skips when the log dir is missing; `test_open_or_create_project_dialog_opens_from_home` skips when the button isn't found. On a clean CI runner these contribute nothing while looking green. Add `pytest.fail` preconditions or mark them `xfail`-on-missing-prereq.
7. **No broad test invokes a menu item.** Every Phase 5 test is a query. The "does the accelerator actually do the thing" assertion is absent across all three suites (surfaces' ⌘, test is the lone exception and it lives in Phase 2).
8. **`test_project.py` fixture duplication.** `prepared_project_path` is defined identically in both `test_project.py` and `test_session.py`. Should live in `tests/surfaces/conftest.py`.
