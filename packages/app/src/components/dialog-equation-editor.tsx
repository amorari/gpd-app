import { Component, createEffect, createSignal, onCleanup, onMount, Show } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { Dialog } from "@opencode-ai/ui/dialog"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { useLanguage } from "@/context/language"
import { PhysicsShortcutsBar } from "@/components/physics-shortcuts-bar"

interface MathfieldElement extends HTMLElement {
  getValue: (format?: string) => string
  setValue: (value: string) => void
  insert: (latex: string, options?: Record<string, unknown>) => void
}

interface Props {
  onInsert: (latex: string) => void
}

export const DialogEquationEditor: Component<Props> = (props) => {
  const dialog = useDialog()
  const language = useLanguage()

  const [loaded, setLoaded] = createSignal(false)
  const [failed, setFailed] = createSignal(false)

  let containerRef: HTMLDivElement | undefined
  let rootRef: HTMLDivElement | undefined
  let mathField: MathfieldElement | undefined

  // Dynamic import of MathLive so the ~1MB bundle stays out of the initial
  // chat load. soundsDirectory=null silences MathLive's audio feedback which
  // otherwise 404s in production (sound files aren't bundled).
  onMount(async () => {
    try {
      const ml = await import("mathlive")
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const MFE: any = ml.MathfieldElement ?? customElements.get("math-field")
      if (MFE && "soundsDirectory" in MFE) MFE.soundsDirectory = null
      setLoaded(true)
    } catch {
      setFailed(true)
    }
  })

  // Mount the math-field element after MathLive has registered the custom
  // element. Using document.createElement+append mirrors the gpd-web React
  // pattern; Solid's JSX doesn't understand <math-field> without extra typing.
  createEffect(() => {
    if (!loaded() || !containerRef) return
    if (!customElements.get("math-field")) return

    const existing = containerRef.querySelector("math-field") as MathfieldElement | null
    if (existing) {
      mathField = existing
      requestAnimationFrame(() => mathField?.focus())
      return
    }

    const field = document.createElement("math-field") as MathfieldElement
    field.style.width = "100%"
    field.style.minHeight = "56px"
    field.style.fontSize = "18px"
    containerRef.appendChild(field)
    mathField = field
    requestAnimationFrame(() => field.focus())
  })

  onCleanup(() => {
    if (mathField && mathField.parentNode) {
      mathField.parentNode.removeChild(mathField)
    }
    mathField = undefined
  })

  const handleShortcut = (latex: string) => {
    if (!mathField) return
    mathField.insert(latex)
    requestAnimationFrame(() => mathField?.focus())
  }

  const handleInsert = () => {
    const latex = mathField ? mathField.getValue("latex") : ""
    if (latex.trim().length > 0) props.onInsert(latex)
    dialog.close()
  }

  // Two-stage Escape: if MathLive has an active popover or virtual keyboard,
  // let MathLive swallow the first Escape. Close the dialog only if neither
  // is visible. Stop propagation in the popover case so Kobalte's dialog
  // dismissal doesn't also fire.
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "Escape") return
    const hasPopover =
      document.querySelector(".ML__popover:not([hidden])") ||
      document.querySelector(".ML__keyboard:not([hidden])")
    if (hasPopover) {
      e.stopPropagation()
      return
    }
    e.preventDefault()
    dialog.close()
  }

  return (
    <Dialog title={language.t("equation.dialog.title")} size="large">
      <div
        ref={rootRef}
        role="group"
        aria-label={language.t("equation.dialog.title")}
        data-testid="gpd-equation-editor"
        onKeyDown={handleKeyDown}
        class="flex flex-col gap-3 p-1"
      >
        <Show
          when={!failed()}
          fallback={
            <div class="min-h-[56px] flex items-center justify-center text-13-regular text-on-critical-base">
              {language.t("equation.dialog.unavailable")}
            </div>
          }
        >
          <Show
            when={loaded()}
            fallback={
              <div class="min-h-[56px] flex items-center justify-center text-13-regular text-text-weak">
                {language.t("equation.dialog.loading")}
              </div>
            }
          >
            <div
              ref={containerRef}
              class="rounded-md border border-border-base bg-surface-raised-base p-2"
            />
          </Show>

          <PhysicsShortcutsBar onInsert={handleShortcut} />
        </Show>

        <div class="flex items-center justify-end gap-2 pt-1">
          <Button type="button" variant="ghost" size="normal" onClick={() => dialog.close()}>
            {language.t("equation.dialog.discard")}
          </Button>
          <Button type="button" variant="primary" size="normal" onClick={handleInsert}>
            {language.t("equation.dialog.insert")}
          </Button>
        </div>
      </div>
    </Dialog>
  )
}
