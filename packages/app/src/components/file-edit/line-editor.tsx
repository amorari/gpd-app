import { EditorView, keymap, placeholder as placeholderExt } from "@codemirror/view"
import { Compartment, EditorState, type Extension } from "@codemirror/state"
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands"
import { bracketMatching, indentOnInput, syntaxHighlighting, defaultHighlightStyle } from "@codemirror/language"
import { createEffect, createSignal, onCleanup, onMount } from "solid-js"
import { Button } from "@opencode-ai/ui/button"
import { useLanguage } from "@/context/language"
import { detectLanguage, type EditorLanguage } from "./eligibility"

type LanguageLoader = () => Promise<Extension>

// Dynamically import language packs only when needed. Keeps the bundle small.
const LANGUAGE_LOADERS: Record<Exclude<EditorLanguage, undefined>, LanguageLoader> = {
  markdown: async () => {
    const mod = await import("@codemirror/lang-markdown")
    return mod.markdown()
  },
  python: async () => {
    const mod = await import("@codemirror/lang-python")
    return mod.python()
  },
  javascript: async () => {
    const mod = await import("@codemirror/lang-javascript")
    return mod.javascript({ jsx: true, typescript: true })
  },
}

export interface LineEditorProps {
  filePath: string
  lineNumber: number
  initialContent: string
  saving?: boolean
  onSave: (newContent: string) => void
  onCancel: () => void
}

export function LineEditor(props: LineEditorProps) {
  const language = useLanguage()
  let hostEl!: HTMLDivElement
  let view: EditorView | undefined
  const [dirty, setDirty] = createSignal(false)

  const getValue = () => view?.state.doc.toString() ?? props.initialContent

  const save = () => {
    if (props.saving) return
    const next = getValue()
    if (next === props.initialContent) {
      props.onCancel()
      return
    }
    props.onSave(next)
  }

  const languageCompartment = new Compartment()

  const baseExtensions = (): Extension[] => [
    history(),
    bracketMatching(),
    indentOnInput(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    placeholderExt(""),
    EditorView.lineWrapping,
    EditorState.allowMultipleSelections.of(false),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        setDirty(update.state.doc.toString() !== props.initialContent)
      }
    }),
    keymap.of([
      {
        key: "Mod-Enter",
        preventDefault: true,
        stopPropagation: true,
        run: () => {
          save()
          return true
        },
      },
      {
        key: "Escape",
        preventDefault: true,
        stopPropagation: true,
        run: () => {
          props.onCancel()
          return true
        },
      },
      // Block newline insertion — single-line editing only.
      {
        key: "Enter",
        preventDefault: true,
        run: () => true,
      },
      ...historyKeymap,
      ...defaultKeymap,
    ]),
    languageCompartment.of([]),
  ]

  onMount(() => {
    view = new EditorView({
      parent: hostEl,
      state: EditorState.create({
        doc: props.initialContent,
        extensions: baseExtensions(),
      }),
    })
    view.focus()
    // Place cursor at end of line.
    const end = view.state.doc.length
    view.dispatch({ selection: { anchor: end, head: end } })

    const lang = detectLanguage(props.filePath)
    if (lang) {
      const loader = LANGUAGE_LOADERS[lang]
      loader()
        .then((ext) => {
          if (!view) return
          view.dispatch({
            effects: languageCompartment.reconfigure(ext),
          })
        })
        .catch(() => {
          // Silently fall back to unstyled editing if the language pack fails to load.
        })
    }
  })

  onCleanup(() => {
    view?.destroy()
    view = undefined
  })

  // React to saving state by disabling interaction (via pointerEvents on host).
  createEffect(() => {
    if (!view) return
    const editable = !props.saving
    view.contentDOM.setAttribute("aria-readonly", editable ? "false" : "true")
  })

  return (
    <div
      data-component="line-editor"
      class="flex flex-col gap-2 rounded-md border border-border bg-background p-2 shadow-md"
      onClick={(event) => event.stopPropagation()}
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div
        class="min-h-[1.75rem] overflow-x-auto rounded border border-border-weak bg-surface px-2 py-1 font-mono text-sm"
        ref={(el) => (hostEl = el)}
        data-action="file-edit-line-input"
      />
      <div class="flex items-center justify-end gap-2">
        <span class="mr-auto text-xs text-text-weak">
          {language.t("file.edit.hint", { line: String(props.lineNumber) })}
        </span>
        <Button size="small" variant="ghost" onClick={() => props.onCancel()} disabled={props.saving} data-action="file-edit-cancel">
          {language.t("file.edit.cancel")}
        </Button>
        <Button
          size="small"
          variant="primary"
          onClick={() => save()}
          disabled={props.saving || !dirty()}
          aria-busy={props.saving ? "true" : "false"}
          data-action="file-edit-save"
        >
          {props.saving ? language.t("common.saving") : language.t("file.edit.save")}
        </Button>
      </div>
    </div>
  )
}
