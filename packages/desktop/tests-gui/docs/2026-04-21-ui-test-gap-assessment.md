# UI Test Gap Assessment
**Date:** 2026-04-21  
**Method:** 10 parallel read-only agents covering all test directories, frontend source, IPC layer, CLI commands, keyboard shortcuts, and harness infrastructure  
**Baseline:** 234 test functions across 64 files in 10 directories

---

## Baseline Coverage Summary

| Directory | Files | Tests | Purpose |
|---|---|---|---|
| `smoke` | 10 | 14 | Basic launch, sidebar, menus, first-run |
| `surfaces` | 14 | 42 | Routes, dialogs, prompt input, session components |
| `flows` | 21 | 73 | End-to-end journeys (sessions, providers, settings) |
| `ipc` | 8 | 62 | Tauri command contracts |
| `broad` | 6 | 11 | macOS menu-bar sweeps via Accessibility API |
| `security` | 1 | 5 | Path traversal, injection, XSS boundaries |
| `lifecycle` | 3 | 3 | Quit + relaunch persistence |
| `stress` | 4 | 14 | High-volume sessions, error recovery, provider failover |
| `regression` | 1 | 1 | Accelerator parser regression |
| `harness_selftest` | 1 | 9 | Test infrastructure invariants |

---

## GAP 1 — IPC Commands (8 of 30 Untested)

| Command | Status | Notes |
|---|---|---|
| `read_third_party_notices()` | **UNTESTED** | Zero coverage |
| `read_license()` | **UNTESTED** | Zero coverage |
| `open_path()` | **PARTIAL** | Error path only; happy path skipped as "disruptive" |
| `repair_gpd_venv()` | **SKIPPED** | Destructive; needs at minimum a shape/precondition test |
| `await_initialization()` | **PARTIAL** | Shape only; Channel arg never exercised |
| `kill_sidecar()` | **SKIPPED** | Destructive; lifecycle test could exercise safely |
| `install_git_macos()` | **PARTIAL** | Platform gate only |
| `install_cli()` happy path | **PARTIAL** | Opt-in flag only; happy path mutates system |

**Quick wins:** `read_third_party_notices` and `read_license` are pure reads — trivially testable in `tests/ipc/` with no side effects. `open_path` error paths (missing path arg, non-existent app name) can be expanded.

---

## GAP 2 — UI Surfaces with Zero Test Coverage

### 7 Dialogs — Never Tested

| Dialog | Interactions missing |
|---|---|
| `dialog-edit-project` | Open, rename, save, cancel |
| `dialog-equation-editor` | Open, enter LaTeX, live preview, Insert/Discard buttons |
| `dialog-release-notes` | Open, next/prev pagination, disable notifications, close |
| `dialog-select-directory` | Open, breadcrumb navigation, create folder, select, cancel |
| `dialog-select-file` | Open, navigate, filter by type, multi-select, cancel |
| `dialog-select-model-unpaid` | Open, upgrade prompt display, limited model list |
| `dialog-select-server` | Open, server list, add/configure/remove, health indicator |

### 7 Session Docks and Panes — No Interaction Tests

| Component | Interactions missing |
|---|---|
| `session-followup-dock` | Toggle, send followup suggestion, edit suggestion |
| `session-revert-dock` | Toggle, restore from prior state |
| `session-todo-dock` | Toggle, mark todo complete (`data-action` exists but untested) |
| `session-progress` | Progress display, cancel in-flight operation |
| `tex-build-pane` | Compile button, error list navigation |
| `tex-error-list` | Click error to jump to source, filter warnings |
| `tex-pdf-viewer` | PDF load, zoom, SyncTeX click-to-source |

### 5 Sidebar Actions — No Tests

| Action | `data-action` value |
|---|---|
| Clear project notifications | `project-clear-notifications` |
| Project context menu delete | `project-delete-menu` |
| Project context menu close | `project-close-menu` |
| Toggle workspace expansion | `project-workspaces-toggle` |
| Archive session via menu | `session-menu-archive` |

### 3 Settings Panels — Tab Navigation Only, No Content Tests

| Panel | Missing coverage |
|---|---|
| `settings-keybinds` | Recording new bindings, conflict detection, reset to default |
| `settings-models` | Enable/disable individual models, set as default, pricing display |
| `settings-dependencies` | Version display, install status, install/repair buttons |

---

## GAP 3 — Keyboard Shortcuts (37 total; only 1 with end-to-end keyboard→outcome test)

> **Bug found:** `⇧⌘S` is bound to both `session.new` AND `theme.scheme.cycle`. The collision is unresolved and untested.

### Untested shortcuts by priority

| Priority | Shortcut | Command | Blocker |
|---|---|---|---|
| 1 | `⌘⇧P` | Command palette | No modifier-key driver in harness |
| 2 | `⌘B` | Toggle sidebar | Only menu existence tested |
| 3 | `⌘K ⌘P` | Open file (chord) | Chord support missing in `os_input` |
| 4 | `⌃\`` | Toggle terminal | Allowlist-guard branch untested |
| 5 | `⇧⌘S` | **Collision**: `session.new` vs `theme.scheme.cycle` | Bug untested |
| 6 | `F11` | Fullscreen | Direct listener bypasses dialog guard |
| 7 | `⌘O` | Open project | Keyboard trigger not tested |
| 8 | `⌥↑` / `⌥↓` | Session previous/next | No test |
| 9 | `⌘[` / `⌘]` | Navigate back/forward | No test |
| 10 | `⇧⌘A` | Toggle auto-accept permissions | No test |
| — | `⌘⇧H` | Navigate home | No test |
| — | `⌥⌘↑` / `⌥⌘↓` | Project previous/next | No test |
| — | `⇧⌘⌫` | Archive session | No test |
| — | `⇧⌘W` | New workspace | No test |
| — | `⇧⌘T` | Cycle theme | No test |
| — | `⌘W` | Close tab (collides with native `⌘W`) | No test |
| — | `⇧⌘L` | Add selection to context | No test |
| — | `⇧⌘R` | Toggle review panel | No test |
| — | `⌘\` | Toggle file tree | No test |
| — | `⌃L` | Focus prompt input | No test |
| — | `⌃⌥T` | New terminal | No test |
| — | `⌥⌘[` / `⌥⌘]` | Previous/next message | No test |
| — | `⌘'` | Open model selector | No test |
| — | `⇧⌘D` | Cycle model variant | No test |
| — | `⌘;` | Open MCP dialog | No test |
| — | `⌘.` / `⇧⌘.` | Cycle agent forward/reverse | No test |
| — | `⌘U` | Attach file | No test |
| — | `⇧⌘X` / `⇧⌘E` | Shell mode / Normal mode | No test |
| — | `⌘-` / `⌘+` / `⌘0` | Webview zoom in/out/reset | No test |

**Root cause:** `os_input.press_key()` only supports single unmodified keys. Adding `press_chord("cmd", "shift", "p")` to the harness unlocks all of these.

---

## GAP 4 — User Flows

| Category | Coverage | Key untested sequences |
|---|---|---|
| Terminal operations | **0%** | Create terminal, rename tab, close tab, clear output, resize panel |
| File & context management | **0%** | Open/close file tabs, select lines → add to context, remove context items, click file ref in message |
| Error recovery | **0%** | Network disconnect → retry UI, sidecar crash → reconnect, API quota → retry, bad API key → correction |
| Concurrent actions | **0%** | Send in session A → switch to B → notification in A; abort + edit + resend; fork while generating |
| Menu-driven commands | **13%** | File→New Session via menu, View toggles (sidebar/terminal/file tree), session navigation via menus |
| Provider management | **22%** | Configure custom provider, switch provider mid-session, re-authenticate expired token |
| Dialog multi-step flows | **22%** | Edit project name/icon, file attach → browse → select → confirm, full model selection flow |
| Session interactions | **30%** | Revert/unrevert via UI, edit previous message + resend, view diff per message |
| Project workspace flows | **33%** | Create workspace, switch workspaces, export/import sessions |
| Settings persistence | **33%** | Multi-setting round-trip (theme + language + model) across restart |
| Onboarding | **50%** | Multi-provider setup, model selection after auth, OAuth provider flow |
| Settings UI content | **67%** | Keybind recording, model toggle, dependency install |

### Specific untested action sequences

1. `Settings → Enable provider A → Disable provider B → Switch model to A → New session → Verify model active`
2. `Home → Open project → Create session → Attach file → Send → Verify file context used`
3. `Message generating → Abort → Edit prior turn → Resend → Model responds`
4. `File open → Select lines → ⇧⌘L → Context chip appears in prompt input → Remove chip → Gone`
5. `Terminal "+" → Name it → Create → Type command → See output`
6. `Right-click project → Rename → Type name → Confirm → Sidebar updates`
7. `Type "/" in prompt → Suggestion popover → Arrow keys → Enter → Command applied`
8. `Type "@" in prompt → File/agent picker → Select → Appears in prompt`
9. `Network down → Send message → Error shown → Network back → Retry → Success`
10. `Settings → Keybinds tab → Click command → Record new key → Save → Test hotkey fires`
11. `Session A running → Switch to B → Message arrives in A → Notification → Click → Return to A`
12. `Menu File → New Session (not titlebar button — the actual menu item)`

---

## GAP 5 — Security and Stress

### Security gaps

- No UI-level XSS tests for form fields (project name, session name, settings inputs containing user data)
- No test verifying API keys are masked/hidden in settings UI and not logged
- No test for invalid server URL rejection in the `set_default_server_url` UI path
- No test for session isolation (switching sessions doesn't leak prior session's UI state)
- No UI test for the permission auto-accept toggle (`⇧⌘A`)

### Stress gaps (all absent from UI level)

- Rapid submit button clicks to verify no duplicate message submission
- Rapid modal open/close cycles (modal stack corruption)
- Rapid model/provider switching (10+ times quickly)
- Large session list (100+ sessions) rendering and scroll performance
- Long message history (100+ messages) scroll performance
- Large file picker (1000+ files) responsiveness
- Sidecar crash mid-operation → UI detection + recovery

### Lifecycle gaps

- Startup with corrupted settings store → falls back to defaults (not hangs)
- Startup with missing sidecar binary → clear error displayed
- Startup with blocked port → fallback or clear error
- App shutdown during active TeX compilation → clean process termination
- App shutdown during message streaming → recoverable session state
- App shutdown with unanswered permission prompts → clean on restart
- Force-kill → relaunch → session state recovery

---

## GAP 6 — Regression Coverage (1 test only)

Only one regression test exists (`test_empty_accelerator_token`). Recent fixed bugs with zero regression coverage:

| Fix (commit) | Missing regression test |
|---|---|
| Session deleted → UI list not updated (7ca2a79) | Delete session via API → SSE event → sidebar list updates |
| Deep link `gpd://session/{id}` navigation (7ca2a79) | Deep link routes to correct session |
| Project auto-registration on direct URL nav (bdc28df) | Navigate to `/:dir` directly → project appears in sidebar |
| 50ms timer race in `waitForPaint` (922feca) | Paint state consistent after navigation |
| Config PATCH returning 500 (f36fa46) | Invalid PATCH returns proper error code, not 500 |

---

## GAP 7 — GPD CLI Commands (0 UI-level tests)

None of the 22 top-level CLI commands are exercised from the UI. The commands most naturally reachable from the desktop app:

| Command | UI entry point |
|---|---|
| `session list` / `session delete` | Terminal panel → run gpd commands |
| `export [sessionID]` | File → Export flow |
| `import <file>` | File → Import flow |
| `agent list` / `agent create` | Agent picker in prompt input |
| `mcp list` / `mcp add` | Settings → MCP dialog |
| `providers list` | Settings → Providers panel |
| `models [provider]` | Model selector dialog |
| `stats` | Terminal → `gpd stats` |

---

## GAP 8 — Test Harness Capabilities Needed

Several gap categories are blocked not by missing tests but by missing harness infrastructure:

| Missing capability | Tests blocked | Estimated effort |
|---|---|---|
| `os_input.press_chord("cmd", "b")` — modifier key chords | All 37 keyboard shortcut tests | Medium |
| Right-click / context menu driver | Sidebar project/session context menus | Medium |
| `DOMReady.wait_for_selector(sel)` — existence + visibility waiter | Reduces boilerplate in 30+ tests | Low |
| `OperationWaiter.wait_for_session_ready(sid)` | All real-backend flow tests | Low |
| Native file picker stub (`NSOpenPanel`) | 5+ xfail tests, file attach flow | High |
| Drag-and-drop driver | Session reordering, file drop | High |
| 9 staged `data-action` patches landed in frontend | 9 currently-xfail surface tests | Low (frontend) |

### The 9 staged patches (already exist in `docs/gpd-app-patches/`)

- `G5-dialog-connect-provider-data-actions.patch`
- `G5-dialog-custom-provider-data-actions.patch`
- `G5-dialog-manage-models-data-actions.patch`
- `G5.5-session-rename-data-action.patch`
- `G6-openorcreate-data-actions.patch`
- (and 4 others)

Landing these unblocks the 9 xfail tests in `tests/surfaces/` with no new test code needed.

---

## Prioritized Recommendations

### Tier 1 — Quick wins, zero harness changes needed

These can be written today against the existing harness:

1. `read_third_party_notices` + `read_license` IPC tests — pure reads, add to `tests/ipc/`
2. Settings keybinds panel content — list renders, click command enters record mode, Escape cancels
3. Settings models panel — enable/disable toggle, set-as-default button
4. Settings dependencies panel — version display, install status, install/repair buttons
5. `session-todo-dock` toggle — `data-action="session-todo-toggle"` exists, untested
6. `session-menu-archive` — data-action exists; archive session, verify removed from list
7. `project-clear-notifications` — create session with activity, clear, verify badge gone
8. **Regression:** session delete → UI sync — delete via HTTP, verify SSE event removes from sidebar
9. **Regression:** project auto-registration — navigate to `/:dir` directly, verify sidebar registers it
10. `dialog-edit-project` — open via `ax.click_menu_item`, rename, save, verify HTTP updated

### Tier 2 — Require `press_chord()` added to `os_input` first

11. `⌘B` sidebar toggle — press chord, verify sidebar hidden/shown
12. `⌃\`` terminal toggle — press chord, verify terminal dock appears
13. `⌥↑` / `⌥↓` session navigation — press chord, verify URL changes
14. `⌘[` / `⌘]` back/forward — navigate two routes, go back, verify URL
15. `⇧⌘S` collision test — press shortcut, assert which command actually fires (documents bug)
16. `⌘'` model selector — press chord in session, verify dialog opens
17. `⌘;` MCP toggle — press chord, verify dialog opens
18. `⇧⌘A` auto-accept toggle — press chord, verify permissions setting flips
19. `⌘⇧P` command palette — press chord, verify palette opens

### Tier 3 — New flow tests (harness-ready, just need writing)

20. Terminal creation flow — click `+`, verify new terminal tab, type command, see output
21. File context management — open file, select lines, `⇧⌘L`, verify chip in prompt, remove chip
22. Prompt slash command flow — type `/`, popover appears, arrow keys, Enter, command applied
23. Prompt `@` mention flow — type `@`, picker opens, select, appears in prompt
24. Abort + edit + resend flow — start real-backend message, abort, edit prior turn, resend
25. Session fork UI flow — open fork dialog, confirm, verify parent/child in session list
26. Project rename flow — right-click via `ax`, select Edit, change name, verify sidebar + HTTP
27. Multi-setting persistence across restart — set theme + language + model, quit, relaunch, verify all three
28. Provider enable → model switch → new session → verify model active in session header
29. Deep link navigation — fire `gpd://session/{id}`, verify app routes to correct session
30. `dialog-release-notes` — open via Help menu, verify content, close

### Tier 4 — Require new harness infrastructure

31. **Native file picker stub** — land `G6-openorcreate-data-actions.patch` + Python stub; test full new-project journey
32. **Context menu driver** — add `os_input.right_click(x, y)` + AX traversal; test all right-click actions
33. **Drag-and-drop** — add cliclick drag; test session reordering in sidebar
34. **`dialog-equation-editor`** — depends on context menu or toolbar trigger; depends on driver above
35. **Sidecar crash mid-operation** — kill sidecar via `os.kill(sidecar_pid, SIGKILL)` during message send, verify UI detects + reconnects
36. **Startup with corrupted settings store** — corrupt `settings.json` before launch, verify clean fallback
37. **Shutdown with active TeX compilation** — start compile, call `app_state.quit()`, verify no orphan `pdflatex`

---

## Summary Numbers

| Category | Total | Tested | Gap |
|---|---|---|---|
| IPC commands | 30 | 22 | **8 untested** |
| UI dialogs | 18 | 11 | **7 with zero coverage** |
| Session docks/panes | 7 | 0 | **7 with zero coverage** |
| Sidebar actions | ~10 | 5 | **5 untested** |
| Keyboard shortcuts | 37 | 1 | **36 untested** |
| Settings panel tabs (content) | 6 | 3 | **3 content-untested** |
| User flow categories | 12 | — | **4 at 0%, 6 below 35%** |
| Regression tests for known bugs | ~6 | 1 | **5 missing** |
| Security scenarios (UI-level) | ~10 | 0 | **~10 missing** |
| Stress scenarios (UI-level) | ~15 | 0 | **~15 missing** |

---

## Appendix: Key Source Locations

| Area | Path |
|---|---|
| GUI test root | `packages/desktop/tests-gui/` |
| Test helpers | `packages/desktop/tests-gui/gpd_tests/` |
| Frontend components | `packages/app/src/components/` |
| Frontend pages | `packages/app/src/pages/` |
| Keyboard commands | `packages/app/src/pages/session/use-session-commands.tsx` |
| Global command registry | `packages/app/src/context/command.tsx` |
| Tauri IPC handlers | `packages/desktop/src-tauri/src/` |
| CLI commands | `packages/opencode/src/cli/cmd/` |
| Staged frontend patches | `packages/desktop/tests-gui/docs/gpd-app-patches/` |
