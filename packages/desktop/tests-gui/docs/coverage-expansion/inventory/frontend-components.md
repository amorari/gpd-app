# Frontend components inventory

Audit of every `.tsx` component in `packages/app/src/components/` (top-level + subdir modules that render UI) and every page in `packages/app/src/pages/`. Data-only `.ts` siblings (helpers, state, pure utilities, `*.test.ts`) are excluded — they are unit-test territory, not interaction-surface.

**Testability rubric (1-5):**
1. No stable attribute at all; deep CSS-only, text/class-only
2. Stable class but not unique, or role/aria via `@opencode-ai/ui` primitive only
3. Has ARIA `aria-label` or Kobalte role markers (accessible but i18n-fragile)
4. Has `data-action` or `data-component` anchor
5. Covered today by a passing tests-gui test

## Components (packages/app/src/components/)

| File | Role | Public props | Interactive elements | Stable selectors today | Testability (1-5) | Notes |
|---|---|---|---|---|---|---|
| debug-bar.tsx | Live perf overlay (fps / mem / LCP) | — | cells w/ tooltips; toggle via keyboard shortcut | `aria-label={t("debugBar.ariaLabel")}` | 3 | Hidden by default; activated via shortcut. No unique anchor. |
| dialog-confirm-delete-project.tsx | Two-button confirm for project deletion | `{ project: LocalProject, onDeleted? }` | Cancel / Confirm buttons, form submit | Dialog title i18n key `dialog.confirmDelete.title` | 2 | Buttons lack `data-action`. Suggest `data-action="confirm-delete-project-{cancel,confirm}"`. |
| dialog-connect-provider.tsx | Provider auth flow (OAuth / API key / env) | `{ provider: string }` | TextField(s), Submit, Back `IconButton`, providers `List` | `aria-label={t("common.goBack")}`; Dialog title | 3 | Kobalte List + aria back; step transitions untagged. |
| dialog-custom-provider.tsx | Add a custom (OpenAI-compatible) provider | `{ back: "providers" \| "close" }` | Many `TextField`s, add/remove model + header rows, submit | `aria-label={t("common.goBack")}`, `aria-label={t("provider.custom.models.remove")}`, `aria-label={t("provider.custom.headers.remove")}` | 3 | Has unit test (`dialog-custom-provider.test.ts`). Form fields unanchored. |
| dialog-edit-project.tsx | Rename/icon/startup edit for a project | `{ project: LocalProject }` | Name TextField, color swatches, icon drop/clear, startup TextField, save | `aria-label={t("dialog.project.edit.color.select", ...)}` | 3 | Color swatches have per-swatch aria; main fields unanchored. |
| dialog-fork.tsx | Pick user-message fork point | — | Searchable `List` of user messages | Dialog title `command.session.fork`; list `[data-slot=list-scroll]` | 2 | No per-item `data-action`. Relies on Kobalte. |
| dialog-gpd-skills.tsx | Browse/insert `/gpd-*` slash commands | — | Searchable `List`, category groups, select inserts into prompt | Dialog title i18n; list default | 2 | No stable anchor for an individual skill row. |
| dialog-manage-models.tsx | Toggle per-model visibility & per-provider bulk toggle | — | Search field, provider-level `Switch`, per-model `Switch`, Connect provider button | — | 2 | No unique anchor for rows. |
| dialog-open-or-create-project.tsx | Two-mode open-existing vs create-new project | `{ onResolved, onOpenExisting }` | Two big `button`s in choice mode; name + parent picker + submit in create mode | — | 2 | **Covered by `tests/surfaces/test_dialog_open_or_create_project.py`.** Buttons lack `data-action`. |
| dialog-release-notes.tsx | Paged highlight walkthrough | `{ highlights: Highlight[] }` | Next/GetStarted/Disable buttons, page dots, arrow keys | — | 1 | Pure class-based. Button text i18n. |
| dialog-select-directory.tsx | Cross-platform directory chooser | `{ title?, multiple?, onSelect }` | Search/path `TextField`, sortable folder `List` | — | 1 | No data-attrs; recent/folders groups. |
| dialog-select-file.tsx | Command palette: files + sessions + commands | `{ mode?, onOpenFile? }` | Search, categorized `List` with keybind chips | — | 2 | Rich but unanchored; relies on fuzzysort. |
| dialog-select-mcp.tsx | Enable/disable MCP servers | — | Search, list row, `Switch` per server | — | 2 | No per-server anchor. |
| dialog-select-model-unpaid.tsx | Free-tier model picker + upgrade CTA | `{ model?: ModelState }` | Free models `List`, providers `List`, View-all button | — | 2 | — |
| dialog-select-model.tsx | Full model picker (also popover variant) | `{ provider?, model? }` | Search, grouped model `List`, Connect-provider, Manage | `aria-label={t("command.provider.connect")}`, `aria-label={t("dialog.model.manage")}`; also `data-action="prompt-model"` on caller trigger | 3 | Aria on internal IconButtons. Popover trigger in prompt-input is `data-action`. |
| dialog-select-provider.tsx | Pick a provider to connect (popular vs other) | — | Search, grouped provider `List` w/ tags | — | 2 | Group titles i18n; no per-item anchor. |
| dialog-select-server.tsx | Manage sidecar/remote server connections | — | TextField(s), buttons (connect, form toggle, back), server rows | `aria-label={t("common.goBack")}` | 3 | Mostly form-based. |
| dialog-settings.tsx | Tabbed settings shell (General / Shortcuts / Providers / Models / Deps) | — | `Tabs.Trigger` × 5, close `IconButton` | `aria-label={t("ui.common.close")}` | 3 | **Covered by `tests/surfaces/test_dialog_settings.py`.** Tab triggers lack `data-action`; content relies on i18n. |
| file-tree.tsx | Project file tree w/ expand, git status, diff | `{ ...FileTree props }` | Collapsible dirs, clickable files, skeletons | `data-component="filetree"`, `data-component="file-icon"` | 4 | Has `data-component`; row-level actions unanchored. |
| link.tsx | Platform-aware `<a>` wrapper (opens externally) | `{ href, ...anchor }` | Anchor click | — | 1 | Trivial. |
| model-tooltip.tsx | Model metadata tooltip body | `{ model, latest?, free? }` | Pure render | — | 1 | Pure display. |
| prompt-input.tsx | Primary composer (contenteditable, attach, submit, model/variant/agent pickers) | `PromptInputProps` | Contenteditable, submit btn, attach btn, model/variant/agent triggers, GPD skills trigger | `data-component="prompt-input"`, `data-action="prompt-submit"`, `data-action="prompt-attach"`, `data-action="prompt-model"`, `data-action="prompt-gpd-skills"`, `data-component="prompt-agent-control"`, `data-component="prompt-model-control"`, `data-component="prompt-variant-control"`, `data-component="prompt-gpd-skills-control"`, plus `aria-label`s | 5 | Richest anchors of any component. Partially covered. |
| session-context-usage.tsx | Token/cost circle + tooltip | `{ variant?, placement? }` | Button opens context tab | `aria-label={t("context.usage.view")}` | 3 | — |
| settings-dependencies.tsx | Diagnostic table of runtime deps (uv, tectonic, …) | — | Refresh/Install hint links, expand rows | — | 1 | Status rendered via tags/classes. |
| settings-general.tsx | General settings tab (language, theme, fonts, notifications, sounds, updates, WSL/Wayland) | — | Select/Switch/Button controls for each setting | Many `data-action="settings-*"` (`settings-language`, `settings-color-scheme`, `settings-theme`, `settings-ui-font`, `settings-code-font`, `settings-auto-accept-permissions`, `settings-feed-reasoning-summaries`, `settings-feed-shell-tool-parts-expanded`, `settings-feed-edit-tool-parts-expanded`, `settings-notifications-agent`, `settings-notifications-permissions`, `settings-notifications-errors`, `settings-sounds-agent`, `settings-sounds-permissions`, `settings-sounds-errors`, `settings-updates-startup`, `settings-release-notes`, `settings-wsl`, `settings-wayland`) | 5 | Partially covered via settings dialog test. Best-tagged settings panel. |
| settings-keybinds.tsx | Keybinding capture/reset UI | — | Search, group collapsibles, per-row capture input, reset button | — | 2 | Group headers i18n-based. |
| settings-list.tsx | Trivial container | `{ children }` | — | — | 1 | Presentational only. |
| settings-models.tsx | Models list with visibility toggles (settings tab) | — | Search field, `Switch` per model | `data-component="connected-providers-section"` (sibling) | 2 | Row-level anchors missing. |
| settings-providers.tsx | Providers tab: connected list + add-more grid | — | Add-provider buttons, connected rows, tag filters | `data-component="connected-providers-section"`, `data-component="custom-provider-section"` | 4 | Row actions (edit/remove) unanchored. |
| status-popover-body.tsx | Popover content: server + MCP status tabs | `{ shown }` | `Tabs`, server rows, MCP switches, restart buttons | `data-component="tabs"` | 3 | Inner controls unanchored. |
| status-popover.tsx | Titlebar status trigger + popover shell | — | Trigger button (health dot) | `aria-label={t("status.popover.trigger")}` | 3 | Good aria. |
| terminal.tsx | Xterm host (keyboard input, resize, copy) | `TerminalProps` | Canvas host for xterm | `data-component="terminal"` | 4 | Used by a selector in `helpers.ts`. |
| titlebar.tsx | Top window chrome: nav, sidebar toggle, fullscreen, new session | — | Back/Forward `IconButton`, sidebar toggle, new-session trigger, fullscreen | Multiple `aria-label`s (`sidebar.menu.toggle`, `common.goBack`, `common.goForward`, `command.session.new`, `command.sidebar.toggle`) + `"Exit Fullscreen"` | 3 | **A staged patch `F4-titlebar-data-action-new-session.patch` exists** — raise to 4 on merge. |
| welcome-screen.tsx | First-run API-key gate | `{ onComplete }` | API-key TextField, Get-started Button | `t("welcome.title")`, `welcome.apiKey.placeholder`, `welcome.getStarted` used as text anchors | 3 | Tests-gui references `TEXT_WELCOME_*` constants for assertions. |
| file-edit/edit-hotspot.tsx | Inline edit hit-target overlay | `{ lineNumber, … }` | Click/keyboard activation | `data-component="edit-hotspot"`, `aria-label={t("file.edit.hotspot.label", ...)}` | 4 | — |
| file-edit/hotspot-layer.tsx | Absolute-positioned layer of hotspots | `HotspotLayerProps` | Container only | — | 2 | Positioning layer. |
| file-edit/line-editor.tsx | In-line textarea for a single line edit | `LineEditorProps` | Textarea, save, cancel | `data-component="line-editor"` | 4 | — |
| prompt-input/context-items.tsx | Attached context chips row | `ContextItemsProps` | Remove-chip button | `aria-label={props.t("prompt.context.removeFile")}` | 3 | — |
| prompt-input/drag-overlay.tsx | Drop-zone overlay during DnD | `PromptDragOverlayProps` | Visual only | — | 1 | — |
| prompt-input/image-attachments.tsx | Inline image thumbnails | `PromptImageAttachmentsProps` | Remove button | `aria-label={props.removeLabel}` | 3 | — |
| prompt-input/slash-popover.tsx | Slash-command + `@`-attach popover | `PromptPopoverProps` | Keyboard-driven list | — | 2 | Caller (`prompt-input.tsx`) has a `data-action` trigger. |
| server/server-row.tsx | Row + health dot for a configured server | `ServerRowProps` | Row click; status indicator | — | 2 | — |
| session/session-context-tab.tsx | Context-breakdown panel content | — | Tab contents | — | 1 | Data display. |
| session/session-header.tsx | Header for an open session tab (file search, open-in, terminal/review/tree toggles) | — | Search, copy-path, open-in, menu, toggle buttons | Many `aria-label` (`session.header.searchFiles`, `session.header.open.copyPath`, `session.header.open.ariaLabel`, `session.header.open.menu`, `command.terminal.toggle`, `command.review.toggle`, `command.fileTree.toggle`) | 3 | Strongest aria coverage in the session shell. |
| session/session-new-view.tsx | Empty-state for a new session | `NewSessionViewProps` | Prompt-input region, CTAs | — | 2 | Mostly delegates. |
| session/session-sortable-tab.tsx | Draggable file tab w/ close | `{ tab, onTabClose }` | Drag handle, close `IconButton` | `aria-label={t("common.closeTab")}` | 3 | Per-tab identity by text only. |
| session/session-sortable-terminal-tab.tsx | Draggable terminal tab | `{ terminal, onClose? }` | Drag, close | `aria-label={t("terminal.close")}` | 3 | — |

(Pure TS in `components/` — `dirty-tracker.ts`, `eligibility.ts`, `dialog-custom-provider-form.ts`, `file-tree` predicates, `titlebar-history.ts`, `prompt-input/*.ts`, `session/session-context-*.ts` — are covered in place by their sibling `*.test.ts` files; they are not interactive surfaces.)

## Pages (packages/app/src/pages/)

| File | Role | Public props | Interactive elements | Stable selectors today | Testability (1-5) | Notes |
|---|---|---|---|---|---|---|
| directory-layout.tsx | Per-directory wrapper that mounts sync/SDK/Data providers | `ParentProps` | None direct | — | 1 | Infrastructure; observable via children. |
| error.tsx | Fatal-init error screen (with diagnostics + API-key retry) | `ErrorPageProps` | TextField (API key), retry `Button`, copy-diag `Button` | — | 2 | Would benefit from `data-action="error-retry"` / `"error-copy-diag"`. |
| home.tsx | Empty-projects / recent-projects landing | — | Server-picker Button, open-or-create Button, per-recent Button | Dialog anchors on spawned dialogs only | 2 | **Covered by `tests/surfaces/test_home.py`.** No `data-action` on "open-or-create" button. |
| layout.tsx | Global chrome: sidebar, project list, workspace list, getting-started, command palette host | `ParentProps` | Project menu, workspace menu, clear-notifications, close-menu, delete-menu, sidebar nav, getting-started panel | `data-action="project-menu"`, `data-action="project-workspaces-toggle"`, `data-action="project-clear-notifications"`, `data-action="project-close-menu"`, `data-action="project-delete-menu"`, `data-component="getting-started"`, `data-component="getting-started-actions"`, `data-component="sidebar-nav-desktop"`, `data-component="sidebar-nav-mobile"`, `data-component="sidebar-rail"`, `aria-label` on more-options + nav | 5 | Richest page. Partially covered via `test_sidebar.py` + project tests. |
| session.tsx | Session route: timeline, composer, file tabs, review/tex/terminal panels | `ParentProps`-equivalent | Timeline, composer region, resize handles, tab panels | `data-component="session-prompt-dock"`, `data-component="session-followup-dock"`, `data-component="session-revert-dock"`, `data-component="session-todo-dock"`, `data-action="session-todo-toggle"`, `data-action="session-todo-toggle-button"`, `data-component="session-progress"`, `data-component="session-progress-bar"`, `data-component="popover-content"`, `data-component="tex-build-pane"`, `data-component="tex-pdf-viewer"`, `data-component="tex-error-list"`, `data-component="tabs-drag-preview"` | 5 | Partially covered by `tests/surfaces/test_session.py`. |
| layout/deep-links.ts | Pure URL/deep-link parser | — | — | — | n/a | Pure TS; not a surface. |
| layout/inline-editor.tsx | Inline name editor controller (projects / workspaces) | — | Controlled `<input>` | — | 2 | Used inside sidebar rows. |
| layout/sidebar-items.tsx | Item renderers (project icon, session row, new-session, skeleton) | Multiple small props types | Archive `IconButton`, session row click | `aria-label={t("common.archive")}` | 3 | — |
| layout/sidebar-project.tsx | Draggable project row w/ context menu | `{ project, ... }` | Project switch, workspaces toggle, clear notifications, close, delete | `data-action="project-switch"`, `data-action="project-workspaces-toggle"`, `data-action="project-clear-notifications"`, `data-action="project-close-menu"`, `data-action="project-delete-menu"`, `aria-label={displayName(...)}` | 5 | Covered in tests-gui selectors module. |
| layout/sidebar-shell.tsx | Fixed sidebar rail (home / open-project / settings / reset / help) | Multiple label-callback props | Home, Open-project, Settings, Reset, Help buttons | `data-component="sidebar-rail"`, many `aria-label`s | 4 | — |
| layout/sidebar-workspace.tsx | Workspace row + draggable session list | `{ ... }` | Workspace menu, new-session button, toggle | `data-action="workspace-menu"`, `data-action="workspace-new-session"`, `data-action="workspace-toggle"`, `data-component="workspace-item"`, `aria-label={t("common.moreOptions")}`, `aria-label={t("command.session.new")}` | 5 | Covered via selectors + smoke. |
| session/composer/session-composer-region.tsx | Docked composer host (prompt + followup + question + revert + todo) | `{ ... }` | Containers for docks | `data-component="session-prompt-dock"` | 4 | — |
| session/composer/session-followup-dock.tsx | Followup prompt UI | `{ ... }` | Inline prompt submit | `data-component="session-followup-dock"`, `aria-label={...}` | 4 | — |
| session/composer/session-permission-dock.tsx | Inline permission prompt | `{ ... }` | Allow/Deny buttons | — | 2 | No `data-action`. |
| session/composer/session-question-dock.tsx | Agent question / multi-choice | `{ request, onSubmit }` | Choice buttons | `aria-label={t("ui.tool.questions") + i}` | 3 | — |
| session/composer/session-revert-dock.tsx | Revert-to-message confirmation | `{ ... }` | Confirm/cancel | `data-component="session-revert-dock"`, `aria-label={...}` | 4 | — |
| session/composer/session-todo-dock.tsx | Inline todo checklist for a session | `{ ... }` | Toggle-todo button, collapse button | `data-component="session-todo-dock"`, `data-action="session-todo-toggle"`, `data-action="session-todo-toggle-button"`, `aria-label={...}` | 5 | Tagged end-to-end. |
| session/file-tabs.tsx | Scrollable file-tab row w/ more-menu | `FileTabContent` + scroll helpers | Tab click, "more" menu | `aria-label={props.moreLabel}` | 3 | — |
| session/message-timeline.tsx | Chat timeline, expandable parts, progress | `{ ... }` | Expand/collapse parts, more-options menu, progress indicator | `data-component="session-progress"`, `data-component="session-progress-bar"`, `data-component="popover-content"`, `aria-label={t("common.moreOptions")}` | 4 | — |
| session/review-tab.tsx | VCS diff / review panel | `SessionReviewTabProps` | File rows, hunk controls | — | 2 | No `data-action`. |
| session/session-side-panel.tsx | Review + files side panel w/ tabs | `{ ... }` | Tab triggers, close buttons, open-file | `data-component="tabs-drag-preview"`, `aria-label={t("session.panel.reviewAndFiles")}`, close & open-file aria | 3 | — |
| session/terminal-panel.tsx | Terminal pane host (+ new-terminal button) | — | New-terminal `IconButton`, tabs | `aria-label={t("terminal.title")}`, `aria-label={t("command.terminal.new")}` | 3 | — |
| session/tex-build-pane.tsx | LaTeX build log pane | `{ ... }` | Recompile / jump-to-error buttons | `data-component="tex-build-pane"` | 4 | — |
| session/tex-error-list.tsx | Parsed TeX errors list | `{ ... }` | Click-to-jump rows | `data-component="tex-error-list"` | 4 | — |
| session/tex-pdf-viewer.tsx | PDF preview w/ prev/next | `{ ... }` | Prev / Next / page controls | `data-component="tex-pdf-viewer"`, `aria-label={t("tex.pdf.prev")}`, `aria-label={t("tex.pdf.next")}` | 4 | — |
| session/use-session-commands.tsx | Command registrations hook | `SessionCommandContext` | No DOM | — | n/a | Hook, not a surface. |
| session/use-tex-compiler.tsx | TeX compile state handle | `{ ... }` | No DOM | — | n/a | Hook. |

(Pure helper/state modules under `pages/session/*.ts`, `pages/layout/*.ts`, `pages/session/composer/session-composer-state.ts`, `session-request-tree.ts`, `session-model-helpers.ts`, `message-gesture.ts`, `message-id-from-hash.ts`, `handoff.ts`, `file-tab-scroll.ts`, `helpers.ts`, `terminal-label.ts`, `layout/helpers.ts`, `layout/deep-links.ts`, and matching `*.test.ts` files are unit-testable and excluded from the surface table.)

## Summary statistics

- Total interactive `.tsx` surfaces audited: **56** (35 top-level components + 8 prompt-input / file-edit / session / server submodules that render UI + 5 top-level pages + 8 `pages/session/**.tsx` + composer docks + sidebar submodules).
- Testability ≥4: **23** (41%).
- Testability ≤2 (needs data attributes added): **21** (38%).
- Already covered today by a passing tests-gui test (score = 5 partial/full): **9** — `prompt-input.tsx`, `settings-general.tsx` (via dialog-settings), `dialog-settings.tsx`, `dialog-open-or-create-project.tsx`, `layout.tsx` (sidebar parts), `sidebar-workspace.tsx`, `sidebar-project.tsx`, `session.tsx` (timeline/todo), `session-todo-dock.tsx`.
- Observed `data-action` values in product code: `new-session`, `project-menu`, `project-switch`, `project-workspaces-toggle`, `project-clear-notifications`, `project-close-menu`, `project-delete-menu`, `workspace-menu`, `workspace-new-session`, `workspace-toggle`, `prompt-submit`, `prompt-attach`, `prompt-model`, `prompt-gpd-skills`, `session-todo-toggle`, `session-todo-toggle-button`, plus the `settings-*` family (19 keys, see settings-general row).
- Observed `data-component` values: `filetree`, `file-icon`, `terminal`, `prompt-input`, `prompt-agent-control`, `prompt-model-control`, `prompt-variant-control`, `prompt-gpd-skills-control`, `edit-hotspot`, `line-editor`, `connected-providers-section`, `custom-provider-section`, `tabs`, `sidebar-rail`, `sidebar-nav-desktop`, `sidebar-nav-mobile`, `getting-started`, `getting-started-actions`, `workspace-item`, `session-prompt-dock`, `session-followup-dock`, `session-revert-dock`, `session-todo-dock`, `session-question-dock` (via closest selector only), `session-progress`, `session-progress-bar`, `popover-content`, `tex-build-pane`, `tex-pdf-viewer`, `tex-error-list`, `tabs-drag-preview`.

## Coverage gap ranking (top 10)

Ranked by product visibility × current coverage gap. Each is a prime candidate for Phase G5 tests.

1. **dialog-connect-provider.tsx** — gate for every provider. Long multi-step form, zero tests. Score 3.
2. **dialog-custom-provider.tsx** — custom provider add/edit with validation fan-out. Has unit test for logic; no interaction test. Score 3.
3. **dialog-manage-models.tsx** — model-visibility bulk toggle, no anchors. Score 2.
4. **dialog-select-model.tsx** — core picker. Anchored trigger exists but inner list untested. Score 3.
5. **dialog-select-mcp.tsx** — MCP enable/disable. No anchors, changes sidecar state. Score 2.
6. **dialog-select-server.tsx** — multi-server / auth form, gatekeeper for remote sidecar. Score 3.
7. **dialog-select-file.tsx** — command-palette-like picker hitting files + sessions + commands. Score 2.
8. **dialog-select-directory.tsx** — used from Home and from dialog-open-or-create-project. No anchors. Score 1.
9. **settings-providers.tsx** — provider CRUD; enters secrets; row actions unanchored. Score 4 (section anchors) but row actions score 2.
10. **dialog-release-notes.tsx** — shown once per release; paged content + "never show again" persistence. Score 1.

Honourable mentions (would also benefit from tests): `settings-keybinds.tsx`, `terminal.tsx` (keyboard path), `session/review-tab.tsx`, `error.tsx`, `session/composer/session-permission-dock.tsx`.

## Product-side improvements suggested

For every component currently rated ≤2, the following single-line additions would raise it to ≥3 and unblock a Phase G5 subagent. Each will become a staged patch under `docs/gpd-app-patches/G5-<slug>.patch`.

Each patch is ~1 line per attribute; staging order mirrors the top-10 coverage-gap ranking above. LOC total ~55.

| Component | Suggested attribute(s) |
|---|---|
| dialog-confirm-delete-project | `data-action="confirm-delete-project-cancel"`, `"confirm-delete-project-confirm"` |
| dialog-fork | root `data-component="dialog-fork"`; row `data-action="dialog-fork-item"` + `data-message-id` |
| dialog-gpd-skills | root `data-component="dialog-gpd-skills"`; row `data-action="gpd-skill-select"` + `data-skill` |
| dialog-manage-models | row `data-action="manage-model-toggle"` + `data-model-id`/`data-provider-id`; header `"manage-provider-toggle"` |
| dialog-open-or-create-project | `data-action="open-existing-project"`, `"create-new-project"`, `"create-project-submit"` |
| dialog-release-notes | root `data-component="dialog-release-notes"`; `data-action="release-notes-{next,close,disable,page}"` + `data-index` |
| dialog-select-directory | root `data-component`; `data-action="select-directory-{path,item}"` |
| dialog-select-file | root `data-component`; row `data-action="select-file-item"` + `data-entry-type` |
| dialog-select-mcp | root `data-component`; row `data-action="mcp-toggle"` + `data-name` |
| dialog-select-provider | root `data-component`; row `data-action="provider-select"` + `data-id` |
| dialog-select-model-unpaid | root `data-component`; free-row `data-action="select-free-model"` + `data-model-id` |
| settings-dependencies | root `data-component`; row `data-action="dependency-check"` + `data-id`; `"dependencies-rescan"` |
| settings-keybinds | root `data-component`; row `data-action="keybind-capture"` + `data-command-id`; `"keybinds-reset-all"` |
| settings-models | row switch `data-action="settings-model-toggle"` + ids |
| home | `data-action="home-open-or-create"`, `"home-recent-project"` + `data-directory`, `"home-server-picker"` |
| error | `data-action="error-{retry,copy-diag,api-key}"` |
| file-edit/hotspot-layer | `data-component="hotspot-layer"` |
| prompt-input/drag-overlay | `data-component="prompt-drag-overlay"` |
| prompt-input/slash-popover | root `data-component`; option row `data-action="prompt-slash-option"` + `data-kind` |
| server/server-row | row `data-action="server-row"` + `data-url` |
| session-permission-dock | root `data-component`; `data-action="permission-{allow,deny}"` |
| session/review-tab | root `data-component`; file row `data-action="review-file"` + `data-path` |
