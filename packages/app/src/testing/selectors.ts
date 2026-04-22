/**
 * Typed registry of E2E test selector ids.
 *
 * See `docs/E2E_SELECTORS.md` (Decision 0.B).
 *
 * **Usage.**
 *   Prefer ARIA-based locators (`getByRole` + `getByLabel`) wherever the
 *   element has or should have an accessible name. Registry entries are
 *   for surfaces where ARIA is genuinely insufficient — typically
 *   contenteditable islands (CodeMirror) or virtual containers.
 *
 * **Registration rule.**
 *   Every entry added here must map to exactly one live DOM node in the
 *   final build. A CI check (`scripts/check-selector-uniqueness.ts`)
 *   enforces that no `data-testid` value appears on >1 element.
 *
 * **Attribute.**
 *   All entries are emitted as `data-testid="<value>"`. Never use
 *   `data-action` for test-only hooks — that attribute is overloaded
 *   for runtime concerns in this codebase.
 */
export const SELECTORS = {
  /**
   * CodeMirror contenteditable host for the line editor in the file-edit
   * panel. Must be attached to `view.contentDOM` after `onMount` creates
   * the EditorView — NOT to the outer wrapper div, which is empty at
   * mount time and not focusable.
   *
   * See `packages/app/src/components/file-edit/line-editor.tsx` and
   * Task 3.6 rollout.
   */
  FILE_EDIT_LINE_INPUT: "file-edit-line-input",

  /**
   * GPD physics shortcut toolbar container rendered above the prompt
   * input on `packages/app/src/components/physics-shortcuts-bar.tsx`.
   * Used by E2E to scope button-level assertions to this toolbar.
   */
  PHYSICS_SHORTCUTS_BAR: "gpd-physics-shortcuts",

  /**
   * GPD equation editor dialog root at
   * `packages/app/src/components/dialog-equation-editor.tsx`.
   */
  EQUATION_EDITOR_DIALOG: "gpd-equation-editor",
} as const satisfies Record<string, string>

export type SelectorId = (typeof SELECTORS)[keyof typeof SELECTORS]

/**
 * Convenience helper that returns a `{ "data-testid": "..." }` prop
 * object. Encourages `data-testid={...SELECTORS.foo(...)}` call sites
 * instead of raw string literals.
 */
export function testId(id: SelectorId): { "data-testid": SelectorId } {
  return { "data-testid": id }
}
