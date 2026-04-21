# GPD Critical User Journeys — Inventory (Phase G1.5)

**Scope:** End-to-end journeys a real GPD user performs, ranked by user-facing impact × frequency. Sources consulted:

- `README.md`, `docs/CHANGES.md`, `docs/GPD_DESKTOP_CHEATSHEET.md`, `docs/GPD_DESKTOP_TESTING.md`, `docs/INTERESTING_FINDINGS.md`, `docs/RELEASING.md`
- Product flow: `packages/app/src/entry.tsx` → `app.tsx` (ConnectionGate → SetupGate → Router) → `pages/home.tsx` → `pages/directory-layout.tsx` → `pages/session.tsx`
- Component surfaces: `packages/app/src/components/welcome-screen.tsx`, `dialog-open-or-create-project.tsx`, `dialog-fork.tsx`, `dialog-settings.tsx`, `dialog-select-model.tsx`, `dialog-select-provider.tsx`, `dialog-confirm-delete-project.tsx`, `prompt-input.tsx`, `titlebar.tsx`, session-specific `tex-build-pane.tsx`, `tex-pdf-viewer.tsx`, `use-tex-compiler.tsx`, `session-new-view.tsx`
- Existing harness tests: `tests/flows/test_onboarding.py`, `test_multi_turn_flow.py`, `test_tool_use_flow.py`, `test_abort_flow.py`, `test_provider_switch.py`, `test_theme_switch.py`, `test_new_session.py`, `test_concurrent_sessions_flow.py`, `test_deep_link.py`

The route topology that structures every journey below:

```
/                                              (Home — project list / open-or-create)
/:dir                                          (DirectoryLayout — SDK/Sync for a project)
/:dir/session                                  (SessionIndex → redirect to /:dir/session/)
/:dir/session/:id?                             (Session — chat, terminal, review, TeX panes)
```

All routes live under `SetupGate` — the app will short-circuit to `WelcomeScreen` until a `gpd` provider entry exists in `auth.json` (detected via `providers.connected()` plus a `localStorage` fast-path flag `gpd.key.saved`).

---

## Journey 1: First-run onboarding

**Pitch:** A professor opens GPD for the first time, pastes a PSI API key into the welcome screen, and lands on an empty home with a working sidecar + provider.

**Actors:** user; GPD desktop shell; Tauri sidecar (opencode); `gpd_setup` first-run provisioning (uv, venv, commands/agents sync); LLM provider registry (no real LLM call to complete the flow, but the key is written to `auth.json`).

**Steps:**
1. User launches GPD.app (or `bun tauri dev`).
2. Shell performs first-run provisioning (venv at `~/.config/gpd/.venv/`, commands, agents, marker `~/.config/gpd/.gpd-initialized`).
3. `ConnectionGate` reports healthy; `SetupGate` finds no `gpd` provider → renders `WelcomeScreen`.
4. User types API key in the password `TextField` (label `welcome.apiKey.label`) and clicks "Get started".
5. `handleApiKeySaved` calls `globalSDK.client.auth.set({ providerID: "gpd", auth: { type: "api", key } })`, writes `localStorage["gpd.key.saved"] = "true"`, calls `global.dispose()`.
6. `SetupGate` re-renders children (Router) → Home.
7. System observable: sentinel file present, `auth.json` has `gpd` entry, home title visible, `Providers` list includes "gpd" as connected.

**Entry state assumptions:** fresh first-run (tier-2 reset: no sentinel, no auth.json, no WebKit storage, no `~/.config/gpd`).

**Dependencies:** `real_backend` (key is written; optional silent round-trip to validate); `fresh_app` reset fixture; `PYTEST_OPTIN_MUTATE_SYSTEM` only if the test also repopulates `~/.config/gpd`; network for uv bootstrap; no tectonic.

**Priority score (9/10):** First impression, 100% of new users hit this exactly once — but non-recurring.

**Suggested test file name:** `tests/flows/test_journey_first_run_onboarding.py`

**Testability notes:** test exists (gated behind `PYTEST_RUN_DESTRUCTIVE_FLOWS=1`). Phase G8.1 plans the ungate. The welcome screen has no `data-action` anchors — selectors rely on placeholder / aria-label. Suggested patch: add `data-action="welcome-api-key-input"` + `data-action="welcome-submit"`. Stage under `docs/gpd-app-patches/G6-welcome-data-actions.patch`.

---

## Journey 2: New project → first chat → abort mid-turn

**Pitch:** From an empty home, user creates a brand-new project directory, sends a prompt, realizes they want to stop the assistant, aborts, and sees the session persist in partial form.

**Actors:** user; GPD; sidecar (`/project`, `/session`, `/session/:id/abort`); LLM (streaming assistant response).

**Steps:**
1. Home renders "empty.title" state (no projects yet) with `home.openOrCreate` button.
2. User clicks the button → `DialogOpenOrCreateProject` opens.
3. User chooses "create" → picks a parent directory via `platform.openDirectoryPickerDialog` → enters a project name → `submitCreate` → `platform.createProjectDirectory(parent, name)` (Tauri IPC `project_fs::create_project_directory`).
4. On success, `openProject(created)` → `layout.projects.open` → `server.projects.touch` → `navigate(`/${base64(root)}`)`.
5. DirectoryLayout mounts SDK/Sync contexts, Session route redirects to `session/` (NewSessionView).
6. User types a prompt in `PromptInput`, hits submit → `sendFollowupDraft` creates a session and starts streaming.
7. Mid-stream the user clicks the abort IconButton (or keybind) → `sdk.session.abort` POSTs to the sidecar.
8. System observable: abort response 2xx; streamed `AssistantMessage` shows `finishReason=abort`; partial text persists; session listed in left sidebar with the truncated message.

**Entry state assumptions:** onboarded; zero projects in db (or at least no project named X); tmp parent directory the harness owns.

**Dependencies:** `real_backend` (to get an actual streaming response to abort); no tectonic; network; harness must own a writable tmp parent dir (cleanup required).

**Priority score (10/10):** Abort is cited repeatedly in CHANGES.md as critical UX; new-project is every user's 1st action after onboarding. Highest composite impact.

**Suggested test file name:** `tests/flows/test_journey_new_project_chat_abort.py`

**Testability notes:** existing `test_abort_flow.py` covers abort only, not the full create→chat→abort chain. `DialogOpenOrCreateProject` has no `data-action` anchors; create vs choose paths live in `mode()`. Suggested patch: add `data-action="openorcreate-create"`, `data-action="openorcreate-name-input"`, `data-action="openorcreate-submit"` under `docs/gpd-app-patches/G6-openorcreate-data-actions.patch`.

---

## Journey 3: Multi-turn chat with tool use (read + write a file)

**Pitch:** Inside an existing project, user sends three prompts. Turn 2 asks the assistant to read a file; turn 3 asks it to edit/write one. User observes both tool calls succeed and produce the expected filesystem diff.

**Actors:** user; GPD; sidecar (`/session/:id/message`, `/session/:id/part` streams); LLM; tool-call plane (`read`, `write`, `edit` tools).

**Steps:**
1. User opens an existing project, clicks New Session or starts typing.
2. Turn 1 — "Write me a hello world Python script": assistant proposes content, `write` tool creates `hello.py`.
3. Turn 2 — "Read hello.py and explain what it does": assistant invokes `read` tool, returns summary.
4. Turn 3 — "Add a second greeting for Italian": assistant invokes `edit` tool, mutates file.
5. System observable: final file bytes match expectation; SSE stream emits `tool-part` with `state=completed`; message timeline has 3 user messages + 3 assistant turns with tool-part children; git diff in review tab shows both edits.

**Entry state assumptions:** onboarded; git-initialized tmp project; provider configured; no permission prompts (GPD ships with `"permission": "allow"`).

**Dependencies:** `real_backend`; network; harness-owned tmp project dir under a parent the sidecar can cd into; cleanup required.

**Priority score (10/10):** This is the product's primary value prop. Every session of real use involves multi-turn + tool use.

**Suggested test file name:** `tests/flows/test_journey_multi_turn_tool_use.py`

**Testability notes:** Existing `test_tool_use_flow.py` covers a single tool invocation. Extension needed: sequence 3 prompts, assert diffs against tmp_path, tolerate model non-determinism in tool argument phrasing. Response text assertion must be tolerant. No new patches required — the harness already has SSE and filesystem checks.

---

## Journey 4: LaTeX compile → inspect log → edit source → recompile

**Pitch:** User writes or opens a `.tex` file in a project, invokes compile from the TeX build pane, reads the error/log panel, edits the source inline, recompiles, and observes the updated PDF in the viewer.

**Actors:** user; GPD; Tauri IPC (`compile_tex`, `parse_tex_log`); tectonic binary; file-edit component.

**Steps:**
1. User opens a project containing a `main.tex` (or creates one via file-edit component).
2. Session side panel / terminal tab group includes TeX build pane (`tex-build-pane.tsx` + `use-tex-compiler.tsx`).
3. User clicks "Compile" button → IPC `compile_tex` runs tectonic, emits PDF bytes + log path.
4. If errors: `tex-error-list.tsx` shows parsed warnings/errors (`parse_tex_log`).
5. User clicks an error, `file-edit` opens at the offending line; they fix it, save.
6. User clicks Compile again → log now clean, `tex-pdf-viewer.tsx` renders the updated PDF.
7. System observable: compile_tex exit code 0 on second pass; parse_tex_log returns zero errors; output PDF hash differs from pass 1; error-list count drops from N→0.

**Entry state assumptions:** onboarded; project contains `main.tex` fixture; tectonic installed and discoverable via PATH; Rust side-effect commands are enabled.

**Dependencies:** `tectonic` binary; `@pytest.mark.tex`; harness-owned tmp project; no LLM needed.

**Priority score (9/10):** GPD's whole pitch is "physics research workspace" — LaTeX is core. But a given user may not use it every session, unlike chat.

**Suggested test file name:** `tests/flows/test_journey_tex_compile_edit_recompile.py`

**Testability notes:** `tex-build-pane` and `tex-error-list` have no `data-action` anchors yet. Harness currently has `ipc/test_tex_compiler.py` for single-shot compile; no end-to-end. Suggested patches: `data-action="tex-compile-button"`, `data-action="tex-error-item"`, and a debug hook to assert the currently-rendered PDF hash (e.g. `__gpd.debug.currentPdfHash()`). Stage under `docs/gpd-app-patches/G6-tex-observability.patch`.

---

## Journey 5: Settings change → quit → relaunch → verify persistence

**Pitch:** User opens the settings dialog, flips theme + picks a different default provider + changes interface language, quits the app, relaunches, and every change is preserved.

**Actors:** user; GPD; sidecar `/config`, `/provider`; ThemeProvider; LanguageProvider; localStorage + opencode.json.

**Steps:**
1. User opens settings via keybind or titlebar → `DialogSettings` renders Tabs (General, Shortcuts, Server, Providers, Models).
2. In General: toggle theme, switch language (en↔zh), toggle a boolean.
3. In Providers: enable/disable a provider, set default model.
4. Close dialog (persist happens on each change; Providers writes to auth.json via sidecar).
5. App quit (`appState.quit()` in harness).
6. Relaunch.
7. System observable: ThemeProvider applies the new theme on mount; LanguageProvider uses the stored locale; Providers list mirrors state; settings dialog re-opens showing same values.

**Entry state assumptions:** onboarded; at least 2 providers available in registry; tier-3 state preserved (we DON'T reset between quit/relaunch).

**Dependencies:** no `real_backend` required (provider list can be served from local registry); harness needs `app_state.quit()` + `app_state.launch()` with state preservation; `PYTEST_OPTIN_MUTATE_SYSTEM` guard because writes land in `~/.config/gpd/opencode.json`.

**Priority score (8/10):** Every returning user depends on this silently. High impact, medium frequency per session (once per change) but affects every session after.

**Suggested test file name:** `tests/flows/test_journey_settings_persistence.py`

**Testability notes:** Existing `test_theme_switch.py` covers theme in a single run. This journey adds: (a) quit + relaunch round-trip, (b) multi-setting at once, (c) cross-setting isolation (changing theme doesn't reset provider). `DialogSettings` Tabs uses `<Tabs.Trigger value="general">` — stable values are good. Need a post-relaunch assertion helper `settings_snapshot()` on `opencode_http` driver to read current state, plus a `persist_mutations()` fixture marker. Stage: `docs/gpd-app-patches/G6-settings-snapshot-ipc.patch` if needed.

---

## Journey 6: Session fork & branching

**Pitch:** User in a multi-turn session decides to explore an alternate path from earlier in the conversation. They open the fork dialog, pick an anchor user message, and land in a new session that shares history up to that point but diverges after.

**Actors:** user; GPD; sidecar `/session/:id/fork`.

**Steps:**
1. User has a session with ≥3 user turns (and their assistant responses).
2. User invokes fork via keybind or titlebar-history → `DialogFork` renders a list of forkable user messages (the `createMemo` in dialog-fork.tsx walks `sync.data.message[sessionID]`).
3. User clicks an item → `sdk.session.fork({ id, at: messageID })` → receives a new session id → `navigate(\`/\${base64(dir)}/session/\${newId}\`)`.
4. User types a different follow-up in the forked session.
5. System observable: new session id differs; messages up to and including anchor match the original; subsequent messages diverge; original session is untouched (immutable).

**Entry state assumptions:** onboarded; existing session with ≥3 turns.

**Dependencies:** `real_backend` to produce the initial 3 turns cheaply (can be mocked via canned assistant responses if the harness has a `recorded_backend`); no tectonic.

**Priority score (7/10):** Power-user feature, but appears in UI frequently. Impact high when used.

**Suggested test file name:** `tests/flows/test_journey_session_fork.py`

**Testability notes:** `DialogFork` renders via `List` with dynamic items — need stable selectors per fork target. Suggested patch: `data-action="fork-item"` with `data-message-id` attribute. Also: harness `opencode_http.fork_session(session_id, at_message)` method is missing — stage under `docs/gpd-app-patches/G6-fork-observability.patch`. Assertion helper to diff two sessions' message trees belongs in `gpd_tests/assertions/sessions.py`.

---

## Journey 7: Project switch + workspace-level state isolation

**Pitch:** User has two projects open (e.g. A = LaTeX paper, B = numerical experiment). They switch between them via the sidebar; each project preserves its own session list, terminal tabs, file tabs, and settings scope.

**Actors:** user; GPD; sidebar-workspace component; sidecar `/workspace`, `/project`.

**Steps:**
1. User has project A at `/:dirA` open with sessions [s1, s2], file tabs [f1].
2. User clicks project B in the sidebar workspace list (`sidebar-workspace.tsx` + `sidebar-project.tsx`).
3. `layout.projects.open(B)` + `navigate('/:dirB')` — DirectoryLayout remounts with B's SDK/Sync providers.
4. User sees B's sessions [s3], no terminal tabs from A, no file tabs from A.
5. User clicks project A again → state snaps back.
6. System observable: session list matches the project; file tabs / terminal panes not leaking across; url reflects the base64-encoded worktree.

**Entry state assumptions:** onboarded; ≥2 projects created; each has ≥1 session.

**Dependencies:** no `real_backend` needed (can be seeded via HTTP fixtures); harness-owned parent dir; cleanup.

**Priority score (7/10):** Frequent in heavy-user workflow, less so for casual. Isolation bugs here are high-severity because leaked context is scary.

**Suggested test file name:** `tests/flows/test_journey_project_switch_isolation.py`

**Testability notes:** Sidebar items need stable selectors — currently inferred from path. Suggested patch: `data-action="sidebar-project"` with `data-worktree-path`. Also need `opencode_http.list_sessions(dir=...)` scoped filter — partially present (confirm in G3.3). Stage: `docs/gpd-app-patches/G6-sidebar-project-data-actions.patch`.

---

## Journey 8: Delete session + confirm + verify gone

**Pitch:** User long-lived-session's noise is cluttering the list; they delete it via context menu, confirm, and the session disappears both client-side and on disk.

**Actors:** user; GPD; sidecar `DELETE /session/:id`; sidebar-items component.

**Steps:**
1. User right-clicks (or menu-button) on a session in the sidebar → exposes Delete.
2. Confirmation flow (either inline confirm or `DialogConfirmDeleteProject`-style — need to verify; see testability notes).
3. User confirms → `sdk.session.delete(id)` → session removed from `sync.data.session`.
4. If user was currently viewing the deleted session → navigate to session index or home.
5. System observable: sidebar no longer shows the id; DB row removed (`sqlite3 opencode-gpd.db`); DELETE /session/:id returns 2xx; second DELETE returns 404; no orphan message rows.

**Entry state assumptions:** onboarded; ≥1 session to delete; harness-owned.

**Dependencies:** no `real_backend`; destructive write to the session table — not global state, but opt-in guard recommended; tmp project.

**Priority score (7/10):** Common hygiene action. Data-loss risk if broken is high; low frequency but high user-trust weight.

**Suggested test file name:** `tests/flows/test_journey_delete_session.py`

**Testability notes:** need to confirm what the confirm affordance is — likely inline in sidebar, not a dedicated dialog. Suggested patch if missing: add `data-action="session-item-menu"` + `data-action="session-delete"` + `data-action="session-delete-confirm"`. Stage under `docs/gpd-app-patches/G6-session-delete-data-actions.patch`. Also need `opencode_http.delete_session` driver method (verify in G1.2). A post-delete assertion via sidecar `GET /session/:id` → 404 is the canonical check.

---

## Journey 9: Model / agent / provider switch mid-conversation

**Pitch:** User is chatting with `claude-sonnet-4-6`, decides the task needs Gemini / Opus, swaps the model (and/or agent) via the prompt-input picker, and the next turn uses the new selection without losing context.

**Actors:** user; GPD; sidecar `/provider`, `/config`; `ModelSelectorPopover` + `DialogSelectModel` + agent selector in `prompt-input`.

**Steps:**
1. User sends turn 1 with model M1.
2. User clicks the model-name button in the prompt-input tray → popover lists available models (filtered by connected providers).
3. User selects M2; ring updates.
4. User sends turn 2 → sidecar attaches `model=M2` to the send request.
5. Observable: assistant response's `providerID`/`modelID` metadata reflects M2; the prior context (messages) is preserved in the send.
6. (Optional) User also swaps agent (`build` ↔ `plan` ↔ custom) or provider — same flow.

**Entry state assumptions:** onboarded with ≥2 providers connected (e.g. gpd covers claude + gemini + gpt via LiteLLM).

**Dependencies:** `real_backend` to observe the actual `providerID` in the streamed message; or unit-level test against `messages()` shape.

**Priority score (8/10):** Mentioned repeatedly in CHANGES.md, power-user frequent, impacts cost & quality.

**Suggested test file name:** `tests/flows/test_journey_model_switch_mid_conversation.py`

**Testability notes:** `prompt-input.tsx` + `dialog-select-model.tsx` expose the picker but no `data-action` anchors. Existing `test_provider_switch.py` covers provider-level, not model-level. Suggested patch: `data-action="prompt-model-picker"`, `data-action="model-option"` with `data-model-id`. Stage under `docs/gpd-app-patches/G6-model-picker-data-actions.patch`.

---

## Journey 10: Attachment / file upload to prompt

**Pitch:** User drags an image (or selects a file via the attach button), types a prompt referencing it, submits, and the assistant receives it as a `FileAttachmentPart` / `ImageAttachmentPart`.

**Actors:** user; GPD; LLM (multimodal-capable); `PromptImageAttachments` + `PromptDragOverlay` + `ACCEPTED_FILE_TYPES` pipeline.

**Steps:**
1. User drags a PNG into the prompt-input area → `PromptDragOverlay` highlights → drop.
2. Image is added as `ImageAttachmentPart`; thumbnail shown in `PromptImageAttachments`.
3. User types "describe this diagram" → submit.
4. Observable: outgoing message parts include the image; assistant response references visual content; attachment can be removed via its X button.
5. Additional variant: attach a file via the `+` icon (`ACCEPTED_FILE_TYPES` filter) producing a `FileAttachmentPart`.

**Entry state assumptions:** onboarded; vision-capable model selected; tmp image fixture.

**Dependencies:** `real_backend` (multimodal); tmp image file.

**Priority score (6/10):** Less frequent than plain chat, but critical for physics figures/plots/papers.

**Suggested test file name:** `tests/flows/test_journey_prompt_attachment.py`

**Testability notes:** drag events are simulation-heavy through MCP; the "+" attach button is likely testable directly. `PromptDragOverlay` needs a data-action or we drive via file-input synthetic event. Stage: `docs/gpd-app-patches/G6-attachment-data-actions.patch` if drag simulation proves brittle.

---

## Journey 11: Deep-link handoff (additional)

**Pitch:** External app triggers GPD via `gpd://` deep link to open a project at a session; GPD focuses the window, routes to the correct `/:dir/session/:id`.

**Actors:** user; external app; GPD's `window.__OPENCODE__.deepLinks` registry; `deep-links.ts` in layout.

**Steps:**
1. External trigger posts a `gpd://…` URL.
2. Tauri delivers to window; frontend consumes via the deep-links handler.
3. Router navigates to the encoded session.
4. Observable: URL matches; correct session mounts; no stale previous-session state.

**Priority score (5/10):** Medium — useful for editor integrations. Existing `test_deep_link.py` is a starting point.

**Suggested test file name:** `tests/flows/test_journey_deep_link_handoff.py`

**Testability notes:** harness affordance for injecting a deep link into a running app may be incomplete. Check `app_state.deep_link(url)` — stage patch if missing.

---

## Journey 12: Release-build smoke (additional)

**Pitch:** A packaged `.app` (not `bun tauri dev`) launches, completes first-run setup on a new machine, reaches home. Validates the signed/notarized bundle path — exercised by `test_release_no_mcp.py` already.

**Priority score (5/10):** Per-release sanity; currently in scope for G8.2. Included for completeness.

**Suggested test file name:** `tests/flows/test_journey_release_build_smoke.py` (existing: `test_release_no_mcp.py`).

**Testability notes:** needs an external signed bundle + `PYTEST_OPTIN_MUTATE_SYSTEM=1`. Keep as its own marker.

---

## Priority ranking (composite impact × frequency)

| Rank | Journey | Score |
|------|---------|-------|
| 1 | Journey 2 — New project → chat → abort | 10 |
| 2 | Journey 3 — Multi-turn chat with tool use | 10 |
| 3 | Journey 1 — First-run onboarding | 9 |
| 4 | Journey 4 — LaTeX compile-edit-recompile | 9 |
| 5 | Journey 5 — Settings change & persistence | 8 |
| 6 | Journey 9 — Model/agent/provider switch mid-convo | 8 |
| 7 | Journey 6 — Session fork & branching | 7 |
| 8 | Journey 7 — Project switch + isolation | 7 |
| 9 | Journey 8 — Delete session + confirm | 7 |
| 10 | Journey 10 — Attachment / file upload | 6 |
| 11 | Journey 11 — Deep-link handoff | 5 |
| 12 | Journey 12 — Release-build smoke | 5 |

---

## Summary of harness affordances needed (rolled up)

Each entry below is a single suggested patch under `packages/desktop/tests-gui/docs/gpd-app-patches/`:

- `G6-welcome-data-actions.patch` — anchors on welcome API-key input + submit.
- `G6-openorcreate-data-actions.patch` — anchors on create/choose/name/submit in `DialogOpenOrCreateProject`.
- `G6-tex-observability.patch` — anchors + a PDF-hash debug hook for the TeX build pane.
- `G6-settings-snapshot-ipc.patch` — IPC read-helper to snapshot current settings for post-relaunch assertions (may not be needed if sidecar `/config` already exposes).
- `G6-fork-observability.patch` — anchors on fork dialog items + `opencode_http.fork_session` driver method.
- `G6-sidebar-project-data-actions.patch` — anchors on sidebar project entries (to drive project switch).
- `G6-session-delete-data-actions.patch` — anchors on session item menu/delete/confirm.
- `G6-model-picker-data-actions.patch` — anchors on prompt-input model picker + options.
- `G6-attachment-data-actions.patch` — anchors on attachment UI + test-only synthetic drop helper.

None of these are strictly blockers — MCP `execute_js` + accessibility queries can reach most of these via aria labels and text content — but each would cut a brittle selector dance out of the corresponding test.

---

## What's out of scope for G1.5

- Per-step coverage (that's G2/G9).
- Visual-regression baselines (G7.1).
- Permission-prompt journey — GPD ships with `"permission": "allow"` so permission-dialog journeys are not user-visible in the default configuration. If we ever flip that default, add a journey.
- MCP-server-invocation journey — end-users don't manually invoke MCP; the assistant does it. Covered implicitly under Journey 3 (tool use).
