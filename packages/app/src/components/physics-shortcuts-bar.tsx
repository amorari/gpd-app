import { createMemo, For } from "solid-js"
import katex from "katex"
import "katex/dist/katex.min.css"
import { PHYSICS_MACROS } from "@/utils/katex-physics-macros"

interface Shortcut {
  label: string
  insert: string
  tooltip: string
}

// MathLive's built-in matrix dialog caps at 5x5; we offer 2x2 through 10x10
// as direct LaTeX inserts so physicists aren't stuck hand-typing larger
// pmatrix blocks. Users who need N > 10 still type `\begin{pmatrix} … \end{pmatrix}`
// at any size (LaTeX itself has no upper bound).
function pmatrix(n: number): string {
  const row = Array(n).fill("").join(" & ")
  const rows = Array(n).fill(row).join(" \\\\ ")
  return `\\begin{pmatrix} ${rows} \\end{pmatrix}`
}
const MATRIX_SHORTCUTS: ReadonlyArray<Shortcut> = [
  {
    label: "\\begin{pmatrix}\\end{pmatrix}",
    insert: pmatrix(2),
    tooltip: "2x2 matrix",
  },
  ...Array.from({ length: 8 }, (_, i) => i + 3).map((n) => ({
    label: `${n}\\times ${n}`,
    insert: pmatrix(n),
    tooltip: `${n}x${n} matrix`,
  })),
]

const PHYSICS_SHORTCUTS: ReadonlyArray<Shortcut> = [
  { label: "\\sum", insert: "\\sum_{i=}^{}", tooltip: "Summation" },
  { label: "\\int", insert: "\\int_{}^{}", tooltip: "Integral" },
  { label: "\\sqrt{}", insert: "\\sqrt{}", tooltip: "Square root" },
  { label: "\\partial", insert: "\\frac{\\partial }{\\partial }", tooltip: "Partial derivative" },
  { label: "\\lambda", insert: "\\lambda", tooltip: "Lambda" },
  { label: "\\nabla", insert: "\\nabla", tooltip: "Nabla/Del" },
  { label: "\\infty", insert: "\\infty", tooltip: "Infinity" },
  { label: "\\hbar", insert: "\\hbar", tooltip: "Reduced Planck constant" },
  { label: "\\vec{x}", insert: "\\vec{}", tooltip: "Vector" },
  { label: "\\hat{x}", insert: "\\hat{}", tooltip: "Unit vector" },
  { label: "\\langle|\\rangle", insert: "\\langle | \\rangle", tooltip: "Bra-ket" },
  ...MATRIX_SHORTCUTS,
  { label: "\\frac{}{}", insert: "\\frac{}{}", tooltip: "Fraction" },
  { label: "\\cdot", insert: "\\cdot", tooltip: "Dot product" },
  { label: "\\times", insert: "\\times", tooltip: "Cross product" },
  { label: "\\alpha", insert: "\\alpha", tooltip: "Alpha" },
]

export function PhysicsShortcutsBar(props: { onInsert: (latex: string) => void }) {
  const rendered = createMemo(() =>
    PHYSICS_SHORTCUTS.map((s) => ({
      ...s,
      html: katex.renderToString(s.label, {
        throwOnError: false,
        displayMode: false,
        trust: false,
        maxSize: 500,
        maxExpand: 1_000,
        macros: PHYSICS_MACROS,
      }),
    })),
  )

  return (
    <div
      data-testid="gpd-physics-shortcuts"
      class="flex items-center gap-1 overflow-x-auto py-1"
      style={{ "scrollbar-width": "none" }}
    >
      <style>{`[data-testid="gpd-physics-shortcuts"]::-webkit-scrollbar{display:none}`}</style>
      <For each={rendered()}>
        {(s) => (
          <button
            type="button"
            title={s.tooltip}
            aria-label={`Insert ${s.tooltip} symbol`}
            onClick={() => props.onInsert(s.insert)}
            class="flex items-center justify-center shrink-0 size-8 rounded bg-surface-raised-base border border-border-base text-text-strong hover:bg-surface-raised-base-hover active:bg-surface-base-active transition-[background] duration-150 overflow-hidden"
            style={{ "font-size": "12px" }}
            innerHTML={s.html}
          />
        )}
      </For>
    </div>
  )
}
