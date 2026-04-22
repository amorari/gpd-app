# Root-Cause Fix Plan — 2026-04-22

Companion to `docs/PR-REVIEW-2026-04-22.md`. Reorganizes the 13-PR bug list into a dependency-ordered fix plan that attacks root causes instead of symptoms.

**Reading order:** work top-down. Phase 0 items unblock Phase 2 and Phase 3 items; Phase 1 plumbing unblocks Phase 3 fixes. Many PRs are split across phases because their premise lives at one layer and their symptom at another.

**Attribution:** every root-cause block lists the original PR(s) whose observation seeded it. Original author credit preserved at commit-message level when work lands. Original PRs remain open untouched — they are superseded via commit message ("supersedes PR #N; identified by @amorari") once a replacement lands.

**Execution mode (2026-04-22 kickoff):**
- Decisions picked by Claude based on review evidence; user vetoes if wrong.
- Commits serially to `gpd`.
- Phase 0 drafts + independent Phase 1/2/4 tasks proceed in parallel. Tasks gated on a decision wait.
- Per-task prereq: if the task touches files in `app.tsx`, `layout.tsx`, `global-sync.tsx`, `settings-general.tsx`, `tos-*.tsx`, `welcome-screen.tsx`, or any file in `infra/litellm/gpd_tos/` or `packages/app/src/lib/tos-accept.ts` — rebase onto current `gpd` HEAD before coding. TOS work landed after the reviewed PRs were authored; the diffs will need manual merge.
- Owner for all tasks until reassignment: Claude (`cameron@psi.inc` as committer).

**Execution outcome (2026-04-22, end of session):**
- 17 commits shipped on `gpd`.
- Tasks 0.A / 0.B / 0.C: all LANDED.
- Tasks 1.1 / 1.2 / 1.3 / 1.4 / 2.1 / 2.3 / 2.4 / 2.5 / 3.1 / 3.2 / 3.4 / 3.5 / 3.6 / 4.1 / 4.2: all LANDED.
- Task 1.5 (Rust supervisor refactor): DEFERRED after 10-agent adversarial review; telemetry-driven reactivation pending.
- Task 1.5a (gpd-logger graceful-shutdown flush): LANDED at commit `db2d53a6cd` as the extraction of the only concrete user-facing value from the Task 1.5 scope.

---

## Phase 0 — Architecture decisions

These are not implementation tasks. They are required decisions. No Phase 2 or Phase 3 work can ship coherently without these settled. One-page design doc per decision, 1-day review cycle, then lock.

### Decision 0.A — Config persistence model

**Problem.** `OPENCODE_CONFIG_DIR` has asymmetric read/write semantics. Loader at `packages/opencode/src/config/config.ts:1422-1468` treats entries as "local" tier. Writer `Config.update` at `config.ts:1593-1600` writes `${InstanceState.directory}/config.json` (project-local). `Config.updateGlobal` at `config.ts:1620` writes `globalConfigFile()` = `Global.Path.config/*` only. `loadGlobal` at `config.ts:1239-1263` reads `Global.Path.config/*` only. No route writes `$OPENCODE_CONFIG_DIR/opencode.json`.

**Decision required.** Pick ONE canonical source for GPD's managed config:
- **Option A — Drop `OPENCODE_CONFIG_CONTENT`.** Write a real file on first run at `$OPENCODE_CONFIG_DIR/opencode.json`. Normal discovery chain loads it. Standard Config.update path writes it. User-editable. Requires updating `gpd_setup.rs::build_config_json` consumers and ensuring the file path is not clobbered on re-install.
- **Option B — Promote `OPENCODE_CONFIG_DIR` to a first-class global tier.** Extend `loadGlobal` + `globalConfigFile` to check `OPENCODE_CONFIG_DIR/opencode.json` before `Global.Path.config/*`. Round-trips via existing `/global/config` route. Keeps env-var injection for defaults.

**Affects:** PR #14, PR #22. Neither can be finalized without this.

**Bifurcation note for Task 3.1:** If Option A lands, Task 3.1 collapses to "delete hardcoded `obj.insert("model", ...)` at `gpd_setup.rs:488-489` entirely AND migrate first-run writes from `OPENCODE_CONFIG_CONTENT` into a real `$OPENCODE_CONFIG_DIR/opencode.json` write in `run_first_setup`." If Option B lands, Task 3.1 is the 1-line guard as originally specified plus `loadGlobal`/`globalConfigFile` extension. Scope is option-dependent.

**Owner:** Claude.

**Output:** `docs/CONFIG_ARCHITECTURE.md` + ADR, applied to `docs/GPD_DISTRIBUTION.md` "How the welcome screen works" section.

### Decision 0.B — E2E selector strategy

**Problem.** Three PRs add `data-action` attributes with no registry, no uniqueness check, inconsistent naming (`session-sidebar-archive` vs `session-menu-rename` vs `openorcreate-*`). `data-action` is ALREADY used for runtime event delegation at `packages/app/src/components/prompt-input.tsx:1374` and on non-interactive wrappers at `settings-general.tsx:238-260` — the name is not test-only by convention. PR #10 + PR #23 collide on `new-session`. Accessibility-first alternatives exist: destructive actions already have `aria-label` via `language.t("common.archive")`.

**Decision required.** Pick the E2E locator strategy:
- **Option A — `data-testid` + typed registry.** New attribute name (unambiguous, test-only), central `packages/app/src/testing/selectors.ts` as a string-literal union type, CI uniqueness check.
- **Option B — Accessibility-first.** Playwright `getByRole` + `getByLabel` against `aria-*` attributes. Pinned test locale. No new attributes. Product must maintain accessible names as the test contract.
- **Option C — Hybrid.** `data-testid` only where ARIA is insufficient (e.g., empty-text icon-only buttons that already have `aria-label` → use ARIA; CodeMirror contenteditable with no ARIA role → use `data-testid` attached to `.cm-content`).

**Affects:** PR #10, PR #12, PR #23.

**Owner:** frontend tech lead.

**Output:** `docs/E2E_SELECTORS.md`, eslint rule prototype, registry scaffold.

### Decision 0.C — Sidecar supervisor architecture

**Problem.** PR #15 layers a poll-based watchdog on top of existing spawn code that splits lifecycle across an `AtomicBool`, a `Mutex<Option<Child>>`, and a consumed-once `oneshot::Sender<ServerReadyData>`. No amount of patching makes this race-free. See `docs/PR-REVIEW-2026-04-22.md` § PR #15 for enumerated races.

**Decision required.** Approve a supervisor refactor scope. Proposed shape:

```rust
// One tokio::spawn'd supervisor task owns Child + ServerReadyData + health.
enum SidecarState {
    Spawning,
    Ready(ServerReadyData),
    Degraded { reason: String, retry_at: Instant },
    Fatal(String),
}

// Commands in:
enum SupervisorCmd { Shutdown(oneshot::Sender<()>) }

// Events out (Tauri-emitted):
enum SidecarEvent {
    Ready(ServerReadyData),     // frontend rebinds ServerConnection
    Degraded(String),
    Fatal(String),
}
```

Backoff policy: 1s → 2s → 4s → 8s → 16s, cap 60s. Budget: 5 failures in 60s → Fatal. Graceful shutdown: SIGTERM + 1s deadline → SIGKILL.

**Affects:** PR #15 entirely.

**Owner:** Claude.

**Output:** `docs/DESKTOP_SIDECAR_SUPERVISOR.md` + implementation plan.

**gpd-logger shutdown contract (REQUIRED).** The supervisor's SIGTERM→deadline→SIGKILL sequence must give `packages/opencode/src/sink/gpd-logger.ts` time to drain. gpd-logger at `230-239` has in-memory pending events with 1s debounce (`:169-175`) and no scope finalizer that flushes to HTTP on teardown. Supervisor contract:
1. Rust sends shutdown request (SIGTERM OR a Tauri-ACK'd shutdown command on a dedicated IPC).
2. Sidecar handler installs a flush-then-exit on the signal: drain gpd-logger pending events synchronously (single blocking HTTP flush), then exit 0.
3. Rust waits up to `GPD_SHUTDOWN_DEADLINE_MS` (default 3000).
4. On deadline miss, SIGKILL and log a warn with the deadline value.

Without step 2's flush, SIGTERM alone doesn't fix the log-loss window — it just delays the SIGKILL that still happens after the 3s deadline. The logger change is part of the supervisor task, not a side concern.

---

## Phase 1 — Foundational plumbing

Landable in parallel after Phase 0 decisions. Each unblocks multiple Phase 3 items.

### Task 1.1 — SDK `rewrite()` copies workspace/directory headers on all methods

**Root cause.** `packages/sdk/js/src/v2/client.ts:17` returns early for non-GET/HEAD:
```ts
if (request.method !== "GET" && request.method !== "HEAD") return request
```
Server middleware reads only query params. Every POST/DELETE/PATCH that should be workspace-scoped is actually running under the caller's instance.

**Change.**
- Remove the method-gate at `client.ts:17`.
- For non-GET methods the SDK can still set headers; extend the rewrite to copy headers into query string consistently. Alternative: leave the headers AND have the server read `x-opencode-workspace` / `x-opencode-directory` as fallback in `WorkspaceRouterMiddleware` at `packages/opencode/src/server/instance/middleware.ts:64`.
- Add SDK tests under `packages/sdk/js/test/` that POST with `experimental_workspaceID` and assert the outgoing Request has the right query param.
- Regenerate `packages/sdk/js/src/v2/gen/*` if any spec changes.

**Risk.** Changing server-side to read the header is safer than changing the SDK because the server change is additive — SDK behavior unchanged, but missing header no longer silently mis-routes.

**Covers:** PR #18 root cause.

**Verification.** Integration test: `client.session.create({ workspaceID })` creates a session with `directory = workspace.directory`, not caller instance directory.

### Task 1.2 — Canonical workspace key helper

**Root cause.** `packages/app/src/context/global-sync/child-store.ts:124-166` keys 4+ caches (`children`, `vcsCache`, `metaCache`, `iconCache`, `lifecycle`, `pins`, `disposers`) by raw `directory` string. Trailing-slash / case / relative alias creates parallel cache entries, leaked SDK clients via `sdkFor(alias)`, duplicated child stores via `applyDirectoryEvent(alias)`.

**Change.**
- New helper `packages/app/src/utils/workspace-key.ts`:
  ```ts
  export function workspaceKey(dir: string): string {
    return dir.replace(/[/\\]+$/, "").replace(/\\/g, "/")
    // platform case folding if Windows / macOS case-insensitive FS
  }
  ```
- Apply at every keyed boundary: `ensureChild`, `sdkFor`, `mark`, `applyDirectoryEvent`, `disposeDirectory`, `pins`, anywhere `vcsCache.get|set` / `metaCache.*` / `iconCache.*` / `children[*]` / `lifecycle[*]` is touched.
- SSE event handler at `packages/app/src/context/global-sync.tsx:326-347`: canonicalize `event.directory` before dispatch. Remove the linear-scan fallback from PR #20 — it's no longer needed and it masks the real invariant.

**Risk.** Invalidates persisted child-store state whose `Persist.workspace(directory, ...)` keys use the un-canonicalized form. Migration: on first canonical-keyed read, check for the alias key, copy to canonical, delete alias.

**Covers:** PR #20 root cause.

**Verification.** Test: dispatch SSE events with `/repo` and `/repo/` directories, assert single child store, single SDK client, single persisted cache entry.

### Task 1.3 — Path canonicalization helpers

**Root cause.** `rejectUnsafeProjectPath` at `packages/app/src/utils/project-path.ts:14-68` is pure string comparison. No `path.resolve`, no `realpath`, no symlink follow, no case fold. `<home>/Documents/..` passes. Becomes a trust boundary under PR #19.

**Change.**
- Add platform-scoped canonicalizer. On desktop: Tauri command that calls `std::fs::canonicalize`. On web: server round-trip via an existing `Filesystem.resolve`-equivalent route.
- Rewrite `rejectUnsafeProjectPath` to canonicalize first, then compare against forbidden roots.
- Add regression tests: `..` segments, symlink to `/`, case variants (`/USERS/name`), URL-encoded `%2e%2e`, Windows `\\server\share`, trailing `/`, mixed separators.
- Same helper used by Phase 3 PR #19 fix.

**Covers:** PR #19 path-traversal class.

**Verification.** Test matrix runs in CI. Add one E2E test that navigates to `/%2e%2e` and asserts rejection.

### Task 1.4 — Selector registry (gated on Decision 0.B)

If Decision 0.B chose Option A or C: create `packages/app/src/testing/selectors.ts`:
```ts
export const SELECTORS = {
  SIDEBAR_NEW_SESSION: "sidebar-new-session",
  TITLEBAR_NEW_SESSION: "titlebar-new-session",
  SESSION_ARCHIVE: "session-archive",
  ...
} as const satisfies Record<string, string>

export type SelectorId = typeof SELECTORS[keyof typeof SELECTORS]
```
Add a `scripts/check-selector-uniqueness.ts` that greps `data-testid="..."` across `packages/app/src`, asserts no value appears on >1 element, and runs in CI.

**Covers:** PR #10, PR #12, PR #23 coordination.

### Task 1.5 — Supervisor refactor (gated on Decision 0.C)

Implement the shape from Decision 0.C. Replace existing `packages/desktop/src-tauri/src/lib.rs::initialize`, `kill_sidecar`, and spawn lifecycle with the single-task supervisor. Publish `SidecarReady`/`SidecarDegraded`/`SidecarFatal` via Tauri event. Update `packages/desktop/src/index.tsx:469` to subscribe and rebind the `ServerConnection` on new `Ready` events.

**Covers:** PR #15 entirely.

---

## Phase 2 — Server correctness

Depends on Phase 1 Task 1.1 for #18-family fixes. Otherwise independent.

### Task 2.1 — Push 404/409 into service layer

**Root cause.** PR #13's route-level `list().some()` pattern is TOCTOU-racy AND collapses "already resolved" into "not found". The existing centralized `NamedError → HTTP` mapping at `packages/opencode/src/server/middleware.ts:20-27` already handles `NotFoundError`. Service layer is the correct home for both detection AND conflict distinction.

**Change.**
- `packages/opencode/src/permission/index.ts:203-206`: `Permission.Service.reply` throws `NotFoundError("permission", id)` if request absent. Throws `ConflictError("permission", id, "already-resolved")` if resolved.
- Same pattern for `Question.Service.reply`, `Question.Service.reject`, `SessionRevert.Service.revert`.
- Add `ConflictError` to the named-error map with HTTP 409.
- Revert PR #13's route-level checks. Each handler becomes a plain service call that relies on middleware mapping.
- Tests in `packages/opencode/test/server/*-httpapi.test.ts`: 404 on bogus ID, 404 on deleted-after-list, 409 on already-resolved, success on first call.

**Covers:** PR #13 404 intent.

### Task 2.2 — Revert `MessageID.zod` breaking change

**Root cause.** PR #13 made `messageID` required on `/session/:id/diff` input schema. But `SessionSummary.diff` at `packages/opencode/src/session/summary.ts:134-145` **does not reference `messageID`** — it just reads `["session_diff", input.sessionID]` from storage. Service interface (`summary.ts:161-164`) and generated SDK (`sdk.gen.ts:2063-2069`) still optional. TUI caller (`packages/opencode/src/cli/cmd/tui/context/sync.tsx:490-495`) passes no messageID. This is a pure contract break with no implementation.

**Change.**
- Revert the schema change at `packages/opencode/src/server/instance/session.ts:486` back to `MessageID.zod.optional()`.
- If message-scoped diffing is an actual roadmap goal, file a separate follow-up: implement it in `SessionSummary.diff`, regenerate SDK, update in-tree callers, bump SDK major — ship as an API-change PR.

**Covers:** PR #13 scope creep.

**Coordination note.** Task 2.1 and Task 2.2 both touch `packages/opencode/src/server/instance/session.ts`. Land as a single commit or strictly sequentially (2.2 first — it's a pure revert) to avoid trivial merge conflicts.

### Task 2.3 — Orphan-workspace DELETE emits `session.deleted`

**Root cause.** `packages/opencode/src/server/instance/middleware.ts:82-92` escape hatch for missing workspace record calls `next()` without Instance context. `Session.remove()` checks for instance state and disables publish when absent. TUI SSE never receives `session.deleted`.

**Change.**
- When workspace record missing on DELETE, fall back to `sessionInfo.directory` and provide instance context via `Instance.provide({ directory, ... })` so `Session.remove()` can publish.
- OR emit a synthetic compensating `session.deleted` event after `next()` if providing instance is unsafe.
- Test: DELETE with missing workspace record → 204 AND SSE `session.deleted` delivered.

**Covers:** PR #18 orphan-DELETE concern.

### Task 2.5 — PR #14 safe slice (invalidate-wait + error logging)

**Independent of Decision 0.A.** Lands immediately.

**Root cause.** Two small correctness issues in `packages/opencode/src/config/config.ts` that PR #14 bundled in with the contested changes:
- `updateGlobal` at `config.ts:1637` fires `invalidate()` without waiting. Callers doing `.update().then(.get())` can race against the disposal.
- `update` at `config.ts:1593-1600` dies silently via `Effect.orDie` with no `tapError` log. Debugging failed config writes requires adding logging manually.

**Change.**
- `config.ts:1637`: `yield* invalidate()` → `yield* invalidate(true)`.
- `config.ts:1597-1599`: prepend `Effect.tapError((err) => Effect.sync(() => log.error("Config.update failed", { error: String(err) })))` before the `Effect.orDie`.

Total: ~4 lines. No API surface change. No test update needed.

**Covers:** PR #14's landable slice. Remaining PR #14 scope (PATCH /config route change, `command`/`agent` strip, `globalConfigFile()` retarget) is blocked on Decision 0.A and documented above.

**Sequencing note.** Ship this first to unblock debugging on any downstream work. Attribution commit message: "supersedes PR #14's safe slice; identified by @amorari."

### Task 2.4 — DELETE SSE directory routing

**Root cause.** Original DELETE concern from PR #18 — resolve via `sessionInfo.directory` when `workspaceID` absent. Already partly correct in PR #18 for the common case. Fold this in after Task 2.3 lands.

**Change.** Keep PR #18's `Filesystem.resolve(sessionInfo.directory)` path. Merge with Task 2.3's instance-provision fix into a single diff.

**Covers:** PR #18 happy-path.

---

## Phase 3 — User-facing fixes

Depends on Phase 1 for plumbing. Each landable independently once its prerequisites are in.

### Task 3.1 — Preserve user model in `inject_provider_config`

**Depends on:** Decision 0.A.

**Root cause.** `packages/desktop/src-tauri/src/gpd_setup.rs:488-489` unconditionally writes `obj.insert("model", "gpd/claude-sonnet-4-6")`. Called from `run_first_setup()`, `repair_gpd_venv()`, and re-entered from `lib.rs:520-529` when marker exists but venv probe fails. Saved model lost on every recovery.

**Change.**
- Guard the insert: `if !obj.contains_key("model") { obj.insert("model", default) }`.
- Respect Decision 0.A: if OPENCODE_CONFIG_CONTENT goes away (Option A), the default lives in a real file written once; if it stays (Option B), the default stays in `build_config_json` but with the guard above.
- Drop hardcoded default from `OPENCODE_CONFIG_CONTENT` separately (PR #22's actual useful change).
- Integration test: start with non-default model → trigger repair → model preserved.

**Covers:** PR #22.

### Task 3.2 — `waitForPaint` visibility-gated fallback

**Root cause.** `packages/app/src/context/global-sync/bootstrap.ts:35`. Current code races rAF against a 50 ms timer — ugly but bounded. PR #17 removes the timer. In hidden/backgrounded WebView, rAF suspends → boot stalls.

**Change.**
- Keep one of: (a) `Promise.race([rAF+setTimeout(0), setTimeout(resolve, 500)])` with a less aggressive fallback, or (b) fast path `if (document.visibilityState !== "visible") return resolve()` before rAF.
- Regression test: monkey-patch `requestAnimationFrame = () => {}`, assert `bootstrapGlobal()` still reaches `ready=true` within 1s.
- Drop the `batch()` around a single write — no-op.

**Covers:** PR #17 intent.

### Task 3.3 — `/:dir` auto-register with preflight

**Depends on:** Task 1.3 (canonicalization).

**Root cause.** PR #19 persists project to `server.projects` before the open succeeds, bypasses `platform.checkProjectAccessible`, and relies on the un-canonicalized `rejectUnsafeProjectPath`.

**Change.**
- Route `/:dir` handler through the existing `navigateToProject` / `openSafe` path used by sidebar and deep-link opens. `platform.checkProjectAccessible` returns `locked` → `layout.projects.unlock`, `missing` → toast.
- Canonicalize with Task 1.3 helper BEFORE the unsafe-path check.
- Only commit `server.projects.open` after the session-load succeeds; on failure, roll back.
- Consider an explicit confirm prompt for first-time URL opens (`Open <dir>?`). User-visible, but safer than silent mutation.
- Toast dedup: `Set<string>` of already-rejected paths to avoid per-signal re-toasts.
- Tests: canonical rejection cases from Task 1.3, locked-folder URL → reconnect path, missing-folder URL → toast, successful open persists, failed open rolls back.

**Covers:** PR #19.

### Task 3.4 — Session deep-link ordering + scheme pin

**Depends on:** Task 1.2 (workspace key).

**Root cause.** PR #20 introduces `parseAnySchemeUrl` that accepts any URL with `hostname === "session"`. Loop at `packages/app/src/pages/layout.tsx:1460-1467` fires `session.get` per link with last-response-wins navigation race.

**Change.**
- Replace `parseAnySchemeUrl` with `parseAppSchemeUrl(url: string)` that allowlists `gpd://` and `opencode://`. Reuse across all deep-link helpers.
- Make batch deterministic: resolve the LAST link only, OR stamp batch with a monotonic token and ignore stale `session.get` completions.
- Tests in `packages/app/src/pages/layout/helpers.test.ts`: `gpd://session/<id>` accepted, `https://session/<id>` rejected, `file://session/<id>` rejected, malformed rejected.
- Remove PR #20's linear-scan SSE fallback (Task 1.2 makes it unnecessary).

**Covers:** PR #20.

### Task 3.5 — Installer key-export strategy

**Root cause.** Install script writes the API key to three places: `~/.gpd/config/litellm.env` (consumed by `gpd` wrapper), `~/.local/share/opencode/auth.json` (consumed by app+CLI, chmod 600), and a shell login-profile export (consumed by nothing that ships; Windows installer deliberately skips). `chmod` band-aid at `install-gpd/install:1190` only covers the fallback path; `install:1156` and `install:1169` are the common paths and have no chmod.

**Change.** Pick one:
- **Preferred — drop the default login-profile export.** Match the Windows installer. Keep `litellm.env` (chmod via `umask 077`) and `auth.json` (os.chmod 0o600) as the two canonical stores. Document any POSIX-only consumer before reintroducing as an opt-in.
- **If the export must remain:** wrap `write_rc_block` (or a dedicated secret-bearing helper) in `umask 077`. Post-`mv`, `chmod 600` and verify mode. No `|| true` on the chmod — fail loudly. Apply at all three call sites.
- Add a regression test in `install-gpd/test/` that drops a 644 rc file into a temp install root and asserts resulting mode is 600 at every secret-bearing site.

**Covers:** PR #16.

### Task 3.6 — Selector rollout (gated on Decision 0.B + Task 1.4)

**Change.** Apply the chosen strategy across PR #10, #12, #23's intended surfaces:
- If Option A (`data-testid` + registry): translate `data-action="new-session"` → `data-testid={SELECTORS.SIDEBAR_NEW_SESSION}` at `sidebar-items.tsx:292`, `data-testid={SELECTORS.TITLEBAR_NEW_SESSION}` at `titlebar.tsx:273-285`, `data-testid={SELECTORS.SESSION_ARCHIVE}` at `sidebar-items.tsx:249-255`, etc.
- Fix `file-edit/line-editor.tsx:149-152` by attaching the selector to CodeMirror's contentDOM after mount: `view.contentDOM.setAttribute("data-testid", SELECTORS.FILE_EDIT_LINE_INPUT)`. Not the shell `<div>`.
- Run prettier on the two wrapped-`<List>` files in PR #23.
- If Option B (ARIA): pin test locale and use `getByRole`/`getByLabel`. No new attributes. Document required `aria-label` coverage in the product.

**Covers:** PR #10, PR #12, PR #23.

---

## Phase 4 — Test hardening

Independent, landable any time after Phase 0 decisions.

### Task 4.1 — Markdown security test matrix

**Root cause.** PR #21 tests miss the dangerous-URL branch entirely and `raw_html_is_stripped` asserts the wrong thing (comrak 0.50 with `unsafe=false` substitutes `<!-- raw HTML omitted -->`, doesn't strip or escape).

**Change.** In `packages/desktop/src-tauri/src/markdown.rs` tests:
- Rename `raw_html_is_stripped` → `raw_html_not_passed_through`. Assert both `!contains("<script>")` AND `contains("<!-- raw HTML omitted -->")`. Add `<iframe>` and `<img onerror=...>` cases.
- Add `external_link_gets_class_and_target` assertion that the safe `href` is PRESENT (currently just checks class/target).
- Add dangerous-URL tests:
  - `[x](javascript:alert(1))` → `<a>` with empty/missing `href`
  - `[x](vbscript:...)` → same
  - `[x](file:///etc/passwd)` → same
  - `[x](data:text/html,<script>)` → same
  - `![img](data:image/png;base64,iVBOR...)` → `src` preserved (allowlist)
- Add autolink test (`options.extension.autolink` is enabled at `markdown.rs:49`, currently untested).

**Covers:** PR #21.

### Task 4.2 — Selector uniqueness CI check (gated on Task 1.4)

Script at `scripts/check-selector-uniqueness.ts`:
```ts
// grep data-testid across packages/app/src, assert uniqueness
// fails CI if any value appears on >1 element
```
Wire into `bun turbo test` pipeline.

### Task 4.3 — Regression tests for fixes landed in Phase 2/3

For each fix, verify a failing test exists BEFORE the fix and passes AFTER:
- Task 2.1 → `test/server/question-httpapi.test.ts` 404/409 cases
- Task 2.3 → DELETE with missing workspace asserts SSE
- Task 3.1 → model survives repair
- Task 3.2 → hidden-rAF boot completes
- Task 3.3 → path-traversal rejection, locked reconnect, rollback
- Task 3.4 → scheme allowlist + batch determinism
- Task 3.5 → 600 at every secret-bearing site

---

## Dependency graph

```
Decision 0.A (config) ──┬─► Task 3.1 (preserve model)
                         └─► Task 1.5 partially (unrelated)

Decision 0.B (selectors) ──► Task 1.4 (registry) ──► Task 3.6 (rollout)
                                                   └─► Task 4.2 (uniqueness CI)

Decision 0.C (supervisor) ──► Task 1.5 (refactor)

Task 1.1 (SDK rewrite) ──► Task 2.3 ──► Task 2.4

Task 1.2 (workspace key) ──► Task 3.4 (deep-link)

Task 1.3 (canonicalize path) ──► Task 3.3 (/:dir)

Task 2.1 (service 404/409) ──► Task 2.2 (revert MessageID) — same file; sequence 2.2 → 2.1

Task 2.5 (PR #14 safe slice) ──── independent, ship first

Task 3.5 (installer) ──────────────────────────── independent

Task 4.1 (markdown tests) ─────────────────────── independent

TOS-coordination prereq for: Task 3.2 (app.tsx, bootstrap.ts), Task 3.3
(layout.tsx, global-sync.tsx), Task 3.4 (layout.tsx, deep-links.ts,
helpers.test.ts), Task 3.6 (app.tsx, titlebar.tsx, dialog-*.tsx).
Rebase onto current gpd HEAD before coding — TOS work landed post-review.
```

Critical path: Decisions 0.A/0.B/0.C → Tasks 1.x → Tasks 3.x. Phase 2 server-side tasks are mostly parallelizable.

## Sequencing

Suggested week-by-week:

**Week 1** — Phase 0 decisions. Three one-page design docs. Review cycle. Lock.

**Week 2** — Phase 1 tasks 1.1 through 1.4 land. Task 1.5 (supervisor refactor) begins.

**Week 3** — Phase 2 tasks (2.1–2.4) land, parallel with Task 1.5 completion. Task 4.1 (markdown) can slot in here.

**Week 4** — Phase 3 tasks (3.1–3.6) land. Task 4.2/4.3 regression coverage follows each.

---

## Out-of-scope but worth noting

- Autolink extension is enabled in markdown.rs:49 but never tested. Task 4.1 covers it.
- Session lifecycle observability gap in `docs/LOGGING.md:537-549` (session_close never emitted). Unrelated to these PRs but surfaced during review.
- `Config.update` writes `config.json` (not `opencode.json`) — undocumented. Worth capturing in the Phase 0.A doc.
- PR author worked from a stale snapshot; future hardening sprints should rebase on HEAD first to avoid landing on pre-TOS and pre-installer architecture.

---

## Attribution

Original PR observations that seeded each root-cause block:
- PR #10 → Task 3.6
- PR #12 → Task 3.6
- PR #13 → Tasks 2.1 + 2.2
- PR #14 → Decision 0.A + Task 2.5 (landable 4-line slice)
- PR #15 → Decision 0.C + Task 1.5
- PR #16 → Task 3.5
- PR #17 → Task 3.2
- PR #18 → Task 1.1 + Task 2.3 + Task 2.4
- PR #19 → Task 1.3 + Task 3.3
- PR #20 → Task 1.2 + Task 3.4
- PR #21 → Task 4.1
- PR #22 → Decision 0.A + Task 3.1
- PR #23 → Task 3.6

Credit `amorari` in commit messages for the identification: "Identified by @amorari in PR #N. Root-cause fix lands here; original symptom-patch superseded."

---

## Related docs

- `docs/PR-REVIEW-2026-04-22.md` — per-PR review evidence + file:line refs
- `docs/GPD_DISTRIBUTION.md` — provider config + welcome-screen architecture (update after Decision 0.A)
- `docs/LOGGING.md` — gpd-logger flush semantics (referenced by Decision 0.C SIGTERM path)
- `docs/CHANGES.md` — append per landed task
