# E2E Selector Strategy (Decision 0.B)

**Status:** LANDED — registry + CI uniqueness check at commit `c52b3d23f4`, CodeMirror `contentDOM` attachment at `80f7aaadb9`.
**Decided:** 2026-04-22
**Decided by:** claude
**Supersedes:** parts of PR #10, PR #12, PR #23 premise

---

## Problem

Three open PRs (#10, #12, #23) add `data-action` attributes as E2E test hooks. Problems verified against `gpd` HEAD:

1. **`data-action` is not a test-only convention in this codebase.** Used for runtime event delegation at `packages/app/src/components/prompt-input.tsx:1374` and on non-interactive wrapper divs at `settings-general.tsx:238-260`. Overloading the name means a future author might `querySelector('[data-action=...]')` for runtime and hit a test hook — or vice versa.
2. **No uniqueness invariant.** PR #10 and PR #23 both add `data-action="new-session"` to different surfaces. `NewSessionItem` at `sidebar-items.tsx:292` is rendered N times by `WorkspaceSessionList` at `sidebar-workspace.tsx:246-252` — so `[data-action="new-session"]` matches multiple nodes in a single DOM even without the cross-PR collision.
3. **Location leaks into names.** `session-sidebar-archive` (PR #12) bakes "sidebar" into the selector. A refactor moving archive into a context menu breaks E2E for an implementation reason.
4. **Some targets already have accessible names.** The archive button at `sidebar-items.tsx:249-255` has `aria-label={language.t("common.archive")}`. The best selector here is `getByRole('button', { name: /Archive/ })` — which ALSO exercises the accessibility contract, catching regressions that remove labels.
5. **Some targets cannot use accessibility.** `file-edit/line-editor.tsx:149-152` mounts a CodeMirror editor. The wrapper `<div>` is empty on mount; the actual contenteditable is a child created by `new EditorView({ parent: hostEl })`. There is no ARIA role on the wrapper. An attribute-based selector on the wrapper (what PR #23 adds) points at the WRONG node and doesn't help Playwright send keystrokes.

## Options

### Option A — `data-testid` + typed registry

- All E2E hooks use `data-testid="..."` (semantic: test-only; standard Testing-Library convention).
- Values live in `packages/app/src/testing/selectors.ts` as a string-literal union.
- CI check asserts every value appears on exactly one element in the built DOM.

**Pros:** One convention, enforceable uniqueness, no accessibility coupling to worry about.
**Cons:** Two selector languages in one codebase (ARIA for real a11y, testid for tests). Must maintain both. Tests don't exercise accessibility.

### Option B — ARIA-first

- Tests use `getByRole`, `getByLabel`, `getByPlaceholderText`.
- Pin the test locale so label strings are stable.
- Require every interactive element to have an accessible name.

**Pros:** Tests double as accessibility lint. One convention. No new attributes.
**Cons:** CodeMirror has no ARIA role on its shell. Some icon-only buttons need `aria-label` added. Locale pinning adds test infra. Tests fail for accessibility reasons that are actually intentional (e.g., tooltip-only labels on decorative elements).

### Option C — Hybrid

- Default to ARIA (`getByRole` + `getByLabel`) wherever the element has or should have an accessible name.
- Use `data-testid` only for surfaces where ARIA is genuinely insufficient: CodeMirror contenteditable, virtualized list items, etc.
- The `data-testid` values go through the typed registry from Option A.
- CI check on `data-testid` uniqueness.

**Pros:** Tests exercise accessibility by default. Only uses `data-testid` where it genuinely adds value. Future-proof: new surfaces reach for ARIA first.
**Cons:** Author judgement call on which strategy fits. Needs a short guideline so the line doesn't drift.

## Decision

**Option C — Hybrid.**

### Rationale

- Destructive/interactive buttons in the app already have `aria-label` via `language.t(...)` — the product needs the accessible name regardless of E2E. Using `getByRole` there makes tests free.
- CodeMirror content is a real gap where ARIA isn't enough. Attaching `data-testid` to `view.contentDOM` (not `hostEl`) after `onMount` gives Playwright something to `.type()` against.
- Typed registry prevents string-literal drift and catches collisions in CI.
- Same-attribute-as-app-semantics (`data-action` overloading) goes away entirely.

### Guideline

> Prefer `getByRole('button', { name: /…/ })` / `getByLabel` for any interactive element with an accessible name.
>
> Add `data-testid={SELECTORS.FOO}` ONLY if:
> - The target is not a focusable/accessible element (e.g., a virtual list item container, a CodeMirror surface).
> - OR the element's accessible name is dynamic in a way that breaks locale-stable locators (rare — justify in comment).
>
> Never use `data-action` for test-only hooks. Never add a test-only attribute without a registry entry.

### Registry shape

```ts
// packages/app/src/testing/selectors.ts
export const SELECTORS = {
  // CodeMirror surfaces
  FILE_EDIT_LINE_INPUT: "file-edit-line-input",
  // Virtual or unnamed containers
  SIDEBAR_NEW_SESSION_ITEM: "sidebar-new-session-item",
  TITLEBAR_NEW_SESSION_ITEM: "titlebar-new-session-item",
  // Add entries here; each must be unique and point to exactly one DOM node.
} as const satisfies Record<string, string>

export type SelectorId = (typeof SELECTORS)[keyof typeof SELECTORS]
```

- Values are strings, keys are uppercase constants, each key maps to exactly one live DOM node in the final build.
- Values use surface-agnostic names (`session-archive`, NOT `session-sidebar-archive`) so moving the element doesn't break tests.

### CI uniqueness check

`scripts/check-selector-uniqueness.ts` (lands in Task 4.2):

```ts
// Grep data-testid across packages/app/src, assert no value appears on >1 element.
// Fails build if violated.
```

Runs as part of `bun turbo test`.

### Per-PR consequences

- **PR #10** (`NewSessionItem` data-action): REJECT. The `NewSessionItem` multi-renders per workspace; a `data-testid` on each instance would still ambiguate. Fix: E2E locates via `getByRole('button', { name: /New session/ })` scoped to the active workspace's container (whose `data-testid` can be added separately). If a container-scoped selector is needed, introduce `data-testid={SELECTORS.SIDEBAR_WORKSPACE}` on the enclosing list element, not on `NewSessionItem` itself.
- **PR #12** (`session-sidebar-archive`): REJECT. Use `getByRole('button', { name: /Archive/ })` after hover/focus in tests. The archive button already has `aria-label={language.t("common.archive")}`.
- **PR #23**:
  - Titlebar `new-session`: consider `getByRole('button', { name: /New session/ })` scoped to the titlebar container. If genuinely needed, `data-testid={SELECTORS.TITLEBAR_NEW_SESSION_ITEM}`.
  - Dialog selectors (connect-provider, manage-models, select-mcp, select-model, open-or-create-project, line-editor): every interactive element in these dialogs has a visible label or placeholder. `getByRole` / `getByLabel` / `getByPlaceholderText` cover them.
  - `file-edit/line-editor.tsx:149-152`: `data-testid={SELECTORS.FILE_EDIT_LINE_INPUT}` applied to `view.contentDOM` after mount (NOT to `hostEl`). This is the one legitimate data-testid in PR #23.
  - JSX comment in `app.tsx`: keep if it documents a real invariant; consider converting to an eslint rule if the invariant is load-bearing.

### Task remapping

- **Task 1.4** scope: scaffold `packages/app/src/testing/selectors.ts` with the two currently-known entries (`FILE_EDIT_LINE_INPUT`, plus placeholder for any ARIA-insufficient case we discover). Add the CI check scaffold at `scripts/check-selector-uniqueness.ts`.
- **Task 3.6** scope: replace all `data-action="..."` hooks in PRs #10/#12/#23 with either `getByRole`-friendly markup (add `aria-label` where missing) OR registry-backed `data-testid` where ARIA is insufficient. Move `file-edit-line-input` selector onto `view.contentDOM`.
- **Task 4.2** scope: the CI check already scaffolded in Task 1.4. Task 4.2 is the "wire into turbo + make it fail red" step.

### Acceptance tests

1. `scripts/check-selector-uniqueness.ts` runs in CI and fails on duplicate `data-testid` values.
2. Adding a new `data-testid="foo"` to a component requires also adding `FOO: "foo"` to `SELECTORS` (enforceable via TypeScript: use `SELECTORS.FOO` reference, not a bare string literal).
3. Playwright test for archive button uses `getByRole('button', { name: /Archive/ })` and passes with locale pinned.
4. Playwright test for CodeMirror line editor uses `getByTestId(SELECTORS.FILE_EDIT_LINE_INPUT)` and can `.type()` characters that land in the editor.

### Out of scope

- Migrating existing `data-action` runtime-delegation uses (they stay as they are; they are not test hooks).
- Broader accessibility audit of the app. This decision does NOT mandate that every interactive element becomes ARIA-compliant overnight — just that new test hooks prefer ARIA when available.

## Veto

Revert this commit + the Task 1.4 scaffold commit if the guideline or registry shape is wrong. Acceptable counter-proposals: Option A (pure data-testid) if Option C's judgement call is considered too loose; Option B (pure ARIA) if the team is willing to invest in locale pinning and full ARIA coverage up-front.
