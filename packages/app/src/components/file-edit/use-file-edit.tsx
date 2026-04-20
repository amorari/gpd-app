import { createSignal } from "solid-js"

export type EditTarget = {
  file: string
  line: number // 1-indexed
  original: string
}

export type ConflictState = {
  target: EditTarget
  draft: string
  currentContent?: string
  currentLineContent?: string
}

/**
 * SolidJS hook that owns transient state for the inline-edit flow:
 *   - which (file, line) is being edited, if any
 *   - whether the editor is currently saving to the backend
 *   - any unresolved conflict the user needs to adjudicate
 *   - whether the tier-2 "large file" warning has been acknowledged for this session
 *
 * The hook is intentionally per-tab (instantiated by FileTabContent) so that
 * closing a tab discards its transient state but other tabs stay unaffected.
 */
export function createFileEditState() {
  const [target, setTarget] = createSignal<EditTarget | null>(null)
  const [saving, setSaving] = createSignal(false)
  const [conflict, setConflict] = createSignal<ConflictState | null>(null)
  const [discardPrompt, setDiscardPrompt] = createSignal<null | {
    resolve: (confirmed: boolean) => void
  }>(null)
  const acknowledgedLargeFiles = new Set<string>()

  const isEditing = () => target() !== null

  const open = (next: EditTarget) => {
    setConflict(null)
    setTarget(next)
  }

  const close = () => {
    setTarget(null)
    setSaving(false)
  }

  const acknowledgeLargeFile = (file: string) => {
    acknowledgedLargeFiles.add(file)
  }

  const hasAcknowledgedLargeFile = (file: string) => acknowledgedLargeFiles.has(file)

  const confirmDiscard = () =>
    new Promise<boolean>((resolve) => {
      if (!isEditing()) {
        resolve(true)
        return
      }
      setDiscardPrompt({
        resolve: (confirmed) => {
          setDiscardPrompt(null)
          resolve(confirmed)
        },
      })
    })

  return {
    target,
    saving,
    setSaving,
    conflict,
    setConflict,
    discardPrompt,
    isEditing,
    open,
    close,
    acknowledgeLargeFile,
    hasAcknowledgedLargeFile,
    confirmDiscard,
  }
}

export type FileEditState = ReturnType<typeof createFileEditState>
