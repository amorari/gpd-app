# Keyboard & menu inventory (G1.4)

Authoritative map of every native-menu item and every web-layer keybind in GPD. Sources:

- `packages/desktop/src/menu.ts` — Tauri native macOS menu.
- `packages/app/src/context/command.tsx` — command registry, `parseKeybind`, `matchKeybind`, global `keydown` listener.
- `packages/app/src/pages/layout.tsx` (~L1066-1265) — `layout` registration (navigation, project, settings, theme, language).
- `packages/app/src/pages/session/use-session-commands.tsx` (~L375-574) — `session` registration (session lifecycle, file/tab, context, view, terminal, message, model, mcp, agent, permissions).
- `packages/app/src/components/titlebar.tsx` — `common.goBack`/`.goForward` + direct F11 listener.
- `packages/app/src/components/prompt-input.tsx` — `file.attach`, `prompt.mode.*`.

`command.tsx` normalization: `","` → `"comma"`, `"+"` → `"plus"`, `" "` → `"space"`; `mod+…` resolves `mod` to `meta` on macOS (so `mod+comma` = ⌘,).

---

## Native menu (`packages/desktop/src/menu.ts`)

PredefinedMenuItems (Cocoa defaults — About, Hide, HideOthers, ShowAll, Quit, Separator, Undo, Redo, Cut, Copy, Paste, SelectAll, CloseWindow) inherit macOS-standard accelerators and are **not dispatched through `trigger(...)`** — they're handled entirely by AppKit. Only the custom `MenuItem.new({ action, … })` entries route through the web-layer trigger.

| Menu > Item | Accelerator | Action triggered | Observable outcome | Testable how? | Covered today? |
|---|---|---|---|---|---|
| GPD > About GPD | — (Predefined) | AppKit About panel | Modal about-window appears | AX item exists/enabled | YES (`test_menu_app_items.py`) |
| GPD > Check for Updates… | — | `runUpdater({alertOnFail:true})` | Native dialog / updater flow | AX item present + enabled when `UPDATER_ENABLED` | NO |
| GPD > Install CLI… | — | `installCli()` from `./cli` | Symlink/file created under `~/.opencode/bin` (destructive) | IPC-only w/ `PYTEST_OPTIN_MUTATE_SYSTEM=1` | NO (plan G4.3 staged) |
| GPD > Reload Webview | — | `window.location.reload()` | Webview reloads; app state reset | AX click → URL sentinel reverts | NO |
| GPD > Restart | — | `commands.killSidecar()` then `relaunch()` | Sidecar PID changes; app process re-inits | process poll (`test_restart.py`) | YES (partial, via `smoke/test_restart.py`) |
| GPD > Hide | ⌘H (Predefined) | Hide app | Window hidden | AX + NSApp state | NO |
| GPD > Hide Others | ⌥⌘H (Predefined) | Hide other apps | Other apps hidden | — (destructive) | NO |
| GPD > Show All | — (Predefined) | Show all apps | — | — | NO |
| GPD > Quit | ⌘Q (Predefined) | App terminates | process exits | `test_launch.py` tears down | partial |
| File > New Conversation | ⇧⌘S | `trigger("session.new")` → navigate `/${dir}/session` | Route → `/session` + composer focused | AX click or kbd → URL probe | PARTIAL (menu-item existence only) |
| File > Open Project… | ⌘O | `trigger("project.open")` → `chooseProject()` dialog | `dialog-open-or-create-project` appears | AX or kbd → DOM probe `[data-component="dialog"]` | PARTIAL (surface presence — `test_dialog_open_or_create_project.py`; no kbd trigger test) |
| File > Close Window | ⌘W (Predefined) | Close front window | Window closes | NSApp | NO (overlaps with `tab.close` mod+w in web layer — double-bound) |
| Edit > Undo | ⌘Z | AppKit standard | Context-dependent | AX item present | YES (`test_menu_edit_items.py`) |
| Edit > Redo | ⇧⌘Z | AppKit standard | Context-dependent | AX item present | YES |
| Edit > Cut | ⌘X | AppKit standard | Clipboard | AX item present | YES |
| Edit > Copy | ⌘C | AppKit standard | Clipboard | AX item present | YES |
| Edit > Paste | ⌘V | AppKit standard | Editor receives text | AX item present | YES |
| Edit > Select All | ⌘A | AppKit standard | Selection | AX item present | YES |
| View > Toggle Sidebar | ⌘B | `trigger("sidebar.toggle")` → `layout.sidebar.toggle()` | Sidebar width 0↔N | AX click or kbd → DOM probe sidebar visibility | PARTIAL (AX item only) |
| View > Toggle Command Prompt / Terminal | ⌃\` | `trigger("terminal.toggle")` → `view().terminal.toggle()` | Terminal dock appears/disappears | DOM probe `[data-action="terminal"]` | NO |
| View > Toggle File Tree | — (no accelerator in native menu; web-layer is `⌘\`) | `trigger("fileTree.toggle")` → `layout.fileTree.toggle()` | File tree panel toggles | DOM probe | NO |
| View > Back | — (web-layer: ⌘\[) | `trigger("common.goBack")` | History back | URL observation | NO |
| View > Forward | — (web-layer: ⌘\]) | `trigger("common.goForward")` | History forward | URL observation | NO |
| View > Previous Conversation | ⌥↑ | `trigger("session.previous")` | Route → prior session id | URL poll | NO |
| View > Next Conversation | ⌥↓ | `trigger("session.next")` | Route → next session id | URL poll | NO |
| Help > GPD Documentation | — | `openUrl("https://opencode.ai/docs")` | Default browser opens URL | AX item present (no browser-side assertion) | PARTIAL |
| Help > Support Forum | — | `openUrl(Discord invite)` | Browser opens | AX item present | PARTIAL |
| Help > Share Feedback | — | `openUrl(feature_request.yml)` | Browser opens | AX item present | PARTIAL |
| Help > Report a Bug | — | `openUrl(bug_report.yml)` | Browser opens | AX item present | PARTIAL |

**Covered today on native-menu (AX-existence-only):** 6 of 28 custom+predef entries have direct tests; remaining 22 lack behavioral coverage.

---

## App-layer shortcuts (`command.tsx` + hooks)

Global keydown listener (`command.tsx:358-379`) is the single dispatch path. Guards in order: (1) `suspended()`; (2) `dialog.active` — any open dialog early-returns (root cause of F11 flake); (3) when focus is in an editable target, only palette / Tab / modified-key / allowlisted (`terminal.toggle`, `terminal.new`, `file.attach`) bindings fire. Default palette keybind `mod+shift+p`, overridable via settings `command.palette`.

### Commands registered under `"layout"` (`pages/layout.tsx`)

| Accelerator | Command ID | Action | Guard | Observable outcome | Testable how? | Covered today? |
|---|---|---|---|---|---|---|
| ⌘⇧H | `navigation.home` | `navigate("/")` | — | URL = `/` | MCP URL probe | NO |
| ⌘B | `sidebar.toggle` | `layout.sidebar.toggle()` | — | Sidebar show/hide | DOM probe for sidebar container width/class | NO (menu item present only) |
| ⌘O | `project.open` | `chooseProject()` opens dialog | — | Dialog present | DOM probe `[data-component="dialog"]` title | NO (dialog presence test exists but not kbd trigger) |
| ⌥⌘↑ | `project.previous` | `navigateProjectByOffset(-1)` | `project.list().length > 1` | Route → `/${otherDir}/…` | URL poll | NO |
| ⌥⌘↓ | `project.next` | `navigateProjectByOffset(1)` | same | Route → next dir | URL poll | NO |
| (none) | `provider.connect` | `connectProvider()` (palette only) | — | `dialog-select-provider` opens | DOM probe | NO |
| (none) | `server.switch` | `openServer()` | — | `dialog-select-server` opens | DOM probe | NO |
| **⌘,** (`mod+comma`) | `settings.open` | `openSettings()` → `dialog-settings` | `!dialog.active` | Settings dialog w/ "General" tab | DOM probe for tab | **YES** (`test_dialog_settings.py` — flagged F11 flaky) |
| (none) | `gpd.resetKey` | Removes `gpd.key.saved`, reload | — | localStorage mutation + reload | DOM probe key absent | NO |
| ⌥↑ | `session.previous` | `navigateSessionByOffset(-1)` | — | Route → prev session id | URL poll | NO |
| ⌥↓ | `session.next` | `navigateSessionByOffset(1)` | — | Route → next session id | URL poll | NO |
| ⇧⌥↑ | `session.previous.unseen` | `navigateSessionByUnseen(-1)` | — | Route jumps to unseen | URL poll + session-state | NO |
| ⇧⌥↓ | `session.next.unseen` | `navigateSessionByUnseen(1)` | — | Route jumps to unseen | URL poll | NO |
| ⇧⌘⌫ | `session.archive` | `archiveSession(current)` | `!params.dir \|\| !params.id` | Session disappears; redirect | HTTP + URL | NO |
| ⇧⌘W | `workspace.new` | `createWorkspace(project)` | `!workspaceSetting()` | New workspace entry | sidebar probe | NO |
| (none; slash `workspace`) | `workspace.toggle` | Toggle workspaces display | `vcs !== "git"` | Sidebar workspace section visible/hidden | DOM probe | NO |
| ⇧⌘T | `theme.cycle` | `cycleTheme(1)` | — | `data-theme` or `[data-color-scheme]` attr changes | DOM probe `<html>` attr | PARTIAL (theme-switch flow test exists; no kbd path) |
| (none) | `theme.set.${id}` | commit preview | — | attr changes | same | NO |
| ⇧⌘S | `theme.scheme.cycle` | `cycleColorScheme(1)` | — | color-scheme attr | DOM probe | NO **(also bound to `session.new` — double-bound, see below)** |
| (none) | `theme.scheme.${scheme}` | commit preview | — | attr | DOM probe | NO |
| (none) | `language.cycle` | `cycleLanguage(1)` | — | `<html lang="">` / copy changes | DOM probe | NO |
| (none) | `language.set.${locale}` | `setLocale(locale)` | — | copy changes | DOM probe | NO |

### Commands registered under `"session"` (`use-session-commands.tsx`)

| Accelerator | Command ID | Action | Guard | Observable outcome | Testable how? | Covered today? |
|---|---|---|---|---|---|---|
| ⇧⌘S | `session.new` | navigate to `/${dir}/session` | — | URL path switches to fresh composer | URL probe | PARTIAL (menu-item-only) |
| (slash `undo`) | `session.undo` | `undo()` | no id / no user msgs | last user turn reverted | HTTP messages count | NO |
| (slash `redo`) | `session.redo` | `redo()` | no `revert.messageID` | revert pointer clears | HTTP | NO |
| (slash `compact`) | `session.compact` | compaction request | — | summary message added | HTTP | NO |
| (slash `fork`) | `session.fork` | fork session | no id / no msgs | new session id; shared prefix | HTTP | NO (plan G6.6) |
| (slash `share`) | `session.share` | share URL | `share.disabled` | share URL returned | HTTP | NO |
| (slash `unshare`) | `session.unshare` | unshare | no share URL | share URL gone | HTTP | NO |
| **⌘K ⌘P** (chord) | `file.open` | palette file-open | — | file opens in tab | DOM probe + palette | NO |
| ⌘W | `tab.close` | close current tab | `!closableTab()` | tab count decrements | DOM probe tabs | NO **(collides with native File>Close Window ⌘W — double-bound)** |
| ⇧⌘L | `context.addSelection` | add selection to context | `!canAddSelectionContext()` | prompt shows chip | DOM probe prompt | NO |
| ⌃\` | `terminal.toggle` | toggle terminal dock | editable-allowlist | terminal panel visible | DOM probe | NO |
| ⇧⌘R | `review.toggle` | toggle review panel | — | review panel visible | DOM probe | NO |
| ⌘\\ | `fileTree.toggle` | toggle file tree | — | file tree visible | DOM probe | NO |
| ⌃L | `input.focus` | focus composer input | — | active-element is composer | `document.activeElement` probe | NO |
| ⌃⌥T | `terminal.new` | open new terminal | editable-allowlist | new terminal tab | DOM probe | NO |
| ⌥⌘\[ | `message.previous` | scroll to prev user msg | no id | visible-msg index change | DOM probe | NO |
| ⌥⌘\] | `message.next` | scroll to next user msg | no id | visible-msg index change | DOM probe | NO |
| ⌘' | `model.choose` | open model dialog | — | `dialog-select-model` | DOM probe | NO |
| ⇧⌘D | `model.variant.cycle` | cycle model variant | — | variant label changes | DOM probe | NO |
| ⌘; | `mcp.toggle` | open MCP dialog | — | `dialog-select-mcp` | DOM probe | NO |
| ⌘. | `agent.cycle` | `local.agent.move(1)` | — | agent pill label changes | DOM probe | NO |
| ⇧⌘. | `agent.cycle.reverse` | `local.agent.move(-1)` | — | agent pill label changes | DOM probe | NO |
| ⇧⌘A | `permissions.autoaccept` | toggle auto-accept | — | titlebar indicator / setting toggles | DOM probe or HTTP config | NO |

### Commands registered under `"titlebar"` (`components/titlebar.tsx`)

| Accelerator | Command ID | Action | Guard | Observable outcome | Testable how? | Covered today? |
|---|---|---|---|---|---|---|
| ⌘\[ | `common.goBack` | navigate(backPath) | `history.index > 0` | URL path reverts | URL poll | NO |
| ⌘\] | `common.goForward` | navigate(forwardPath) | `index < stack.length - 1` | URL path advances | URL poll | NO |
| **F11** (direct `window.addEventListener("keydown")`, not via registry) | — (no Command ID) | `toggleFullscreen()` via Tauri `setFullscreen` | `platform === "desktop"` | window fullscreen toggles | Tauri window state | NO |

### Commands registered under `"prompt-input"` (`components/prompt-input.tsx`)

| Accelerator | Command ID | Action | Guard | Observable outcome | Testable how? | Covered today? |
|---|---|---|---|---|---|---|
| ⌘U | `file.attach` | open native file picker | `mode !== "normal"` | file chip appears in prompt | DOM probe | NO |
| ⇧⌘X | `prompt.mode.shell` | `setMode("shell")` | `mode === "shell"` | prompt-input gets shell styling | DOM probe | NO |
| ⇧⌘E | `prompt.mode.normal` | `setMode("normal")` | `mode === "normal"` | prompt styling resets | DOM probe | NO |

### Palette & implicit bindings

| Accelerator | Command ID | Action | Guard | Observable | Covered today? |
|---|---|---|---|---|---|
| ⇧⌘P (default) | `command.palette` | `showPalette()` via `run("file.open","palette")` | not suspended / no dialog | palette dialog opens | NO |

### Non-registry direct `keydown` handlers (component-local)

These bypass the global keymap (attached in `onMount`) and therefore the suspended/dialog.active guards. None are covered.

| Location | Keys | Purpose |
|---|---|---|
| `titlebar.tsx:142-150` | F11 | toggle fullscreen via Tauri |
| `prompt-input.tsx:1134-1275` | Backspace/Esc/Tab/Enter/!/↑/↓/Ctrl-N/Ctrl-P | composer editing, history nav, mention trigger, IME, shift-enter newline |
| `session.tsx:1042-1053` | Esc / PageUp / PageDown / Home / End | blur composer, scroll messages |
| `inline-editor.tsx:31` | Enter / Esc | commit/cancel inline edit |
| `session-question-dock.tsx:307-339` | Esc / Mod+Enter / Arrows / Home | answer-selection UX |
| `message-timeline.tsx:799-804` | Enter / Esc | message action dispatch |
| `dialog-select-server.tsx`, `dialog-release-notes.tsx`, `dialog-connect-provider.tsx`, `dialog-select-model-unpaid.tsx` | Esc / Enter / ←/→ | dialog-local navigation |
| `session-sortable-terminal-tab.tsx:81-86` | Enter / Esc | terminal-tab rename |
| `settings-keybinds.tsx:211-217` | Esc / Backspace / Delete | keybind-recorder UX |
| `session-todo-dock.tsx`, `session-revert-dock.tsx`, `session-followup-dock.tsx`, `file-tabs.tsx` | onKeyDown wired | dock / tab nav |

---

## Cross-reference

### Accelerators with **no native-menu path** (web-layer only)

⌘⇧H, ⌥⌘↑/↓, ⌘, ⇧⌘⌫, ⇧⌘W, ⇧⌘T, ⇧⌘S (also session.new — collision), ⌘K⌘P, ⌘W, ⇧⌘L, ⇧⌘R, ⌘\\, ⌃L, ⌃⌥T, ⌥⌘\[/\], ⌘', ⇧⌘D, ⌘;, ⌘. / ⇧⌘., ⇧⌘A, ⌘\[/\], ⌘U, ⇧⌘X / ⇧⌘E, ⇧⌘P (palette), F11 (direct listener).

### Menu items with **no accelerator** (click-only)

GPD > Check for Updates…, Install CLI…, Reload Webview, Restart. View > Toggle File Tree, Back, Forward. All Help items (Documentation, Support Forum, Share Feedback, Report a Bug).

### Double-bound accelerators (tests should assert BOTH paths)

1. **⇧⌘S** — native `File > New Conversation` triggers `session.new`; the `layout` registry binds the same `mod+shift+s` to `theme.scheme.cycle`. `keymap` Map uses first-insert-wins (`command.tsx:334`), so registration order determines which command fires on web layer. **BUG CANDIDATE**: menu path bypasses keymap so both may silently co-exist; tests must assert ⇧⌘S goes to `session.new`, not theme cycle.
2. **⌘W** — native `File > Close Window` (AppKit) vs web-layer `tab.close`. AppKit wins; web layer only fires if AppKit forwards.
3. **⌃\`** — native `View > Toggle Terminal` and web-layer `terminal.toggle` map to the same command (double-registered, not conflicting).
4. **⌘B** — native `Toggle Sidebar` and web-layer `sidebar.toggle` (same ID).
5. **⌘O** — native `Open Project…` and web-layer `project.open` (same ID).

### Web registry bindings unreachable via native menu

All `"session"` commands and most `"layout"` (home, archive, theme cycle, msg nav, model/agent/mcp dialogs, prompt-input modes, tab close, add-selection, review/file-tree, palette, input focus). **~44 of 52 web-layer keybinds have no native-menu backup.**

---

## Coverage gap ranking (top 10)

Ranked by user-impact × regression-likelihood. None have kbd→outcome tests.

1. **⌘⇧P — Command Palette**. Entry point to every command.
2. **⌘B — Toggle Sidebar**. Every-session layout reflow.
3. **⌘K ⌘P — File Open chord**. Exercises multi-combo parse path (`"mod+k,mod+p"` splits on `,`; only first combo honored — worth asserting).
4. **⌃\` — Toggle Terminal**. Covers the `EDITABLE_KEYBIND_IDS` allowlist branch in the keydown guard.
5. **⌘, — Settings**. Tested but flagged F11 flaky; replace sleep with deterministic DOM-wait.
6. **⇧⌘S — session.new vs theme.scheme.cycle collision**. Assert File > New Conversation triggers `session.new`.
7. **F11 — Fullscreen**. Direct listener, bypasses dialog guard; observable via Tauri `isFullscreen()`.
8. **⌘O — Open Project**. Dialog presence tested; kbd-trigger path is not.
9. **⌥↑ / ⌥↓ — Previous/Next Session**. Core navigation.
10. **⇧⌘A — Permissions auto-accept toggle**. Safety-relevant.

---

## Product-side improvements (candidate patches)

Stage under `packages/desktop/tests-gui/docs/gpd-app-patches/`.

1. **Native `MenuItem::Preferences` entry** mapped to `mod+comma`/`settings.open` so tests can click the menu item instead of posting a raw keystroke (today's F11 flake root cause); also gives an AX-existence anchor.
2. **Resolve the ⇧⌘S collision** — rename `theme.scheme.cycle` or reorder registration so `session.new` wins deterministically (current behavior depends on fragile `registrations` array insertion order).
3. **Add AX-visible accelerators** (`CmdOrCtrl+,`, Back/Forward, Toggle File Tree — currently accelerator-less in menu.ts L124-137) so tests can match the AX accelerator attribute.
4. **Tag titlebar fullscreen button** with `data-action="fullscreen"` so F11 outcome can be observed without racing `currentDesktopWindow()`.
5. **Stable `data-action` anchors** on sidebar, file-tree, terminal panel roots so DOM probes stop relying on `:has()` / text heuristics.
6. **Publish `data-action="command-palette"`** on the opened palette root so ⌘⇧P open/close can be asserted.

---

## Quick stats

- Native menu entries: **28** (custom MenuItem + Predefined), **18 custom actions routed via `trigger(...)`**, 10 AppKit predefined.
- Web-layer commands registered: **~50** (counting `theme.set.*` and `language.set.*` as one each yields ~45; counting each locale/theme commit command individually adds ~10-15 more).
- Distinct keybound accelerators: **37** (34 via registry + F11 direct + ⌘⇧P palette implicit + ⌘K⌘P chord).
- Tests today that exercise a **keybind → outcome** chain: **1** (`test_settings_opens_via_cmd_comma_and_closes_on_escape`, flagged flaky).
- Tests today that assert **menu-item presence / enabled state**: **8** (`test_menu_app_items`, `test_menu_edit_items`, `test_menu_file_items`, `test_menu_view_items`, `test_menu_help_items`, `test_menu_sweep`, `test_menu_bar`, `test_sidebar`).
- Effective keybind-path coverage: **1 / 37 ≈ 2.7 %**.
- Menu-presence coverage: **~25 / 28 ≈ 89 %** (existence only; no behavioral assertion beyond `test_restart.py`).
