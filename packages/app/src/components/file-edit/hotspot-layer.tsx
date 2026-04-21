import { createEffect, createSignal, onCleanup, Show } from "solid-js"
import { Dialog } from "@opencode-ai/ui/dialog"
import { Button } from "@opencode-ai/ui/button"
import { useDialog } from "@opencode-ai/ui/context/dialog"
import { makeEventListener } from "@solid-primitives/event-listener"
import { showToast } from "@opencode-ai/ui/toast"
import { useLanguage } from "@/context/language"
import { useSDK } from "@/context/sdk"
import { useFile } from "@/context/file"
import { useComments } from "@/context/comments"
import { EditHotspot } from "./edit-hotspot"
import { LineEditor } from "./line-editor"
import { splitLines } from "./eligibility"
import type { FileEditState } from "./use-file-edit"

interface HotspotLayerProps {
  container: HTMLElement | undefined
  filePath: string
  content: string
  editState: FileEditState
  tier: "small" | "medium"
}

type LineRect = {
  line: number
  top: number
  height: number
}

function findViewerRoot(container: HTMLElement | undefined): ShadowRoot | undefined {
  if (!container) return undefined
  const host = container.querySelector("diffs-container")
  if (!(host instanceof HTMLElement)) return undefined
  return host.shadowRoot ?? undefined
}

function collectLineRects(container: HTMLElement, root: ShadowRoot): LineRect[] {
  const containerRect = container.getBoundingClientRect()
  const seen = new Map<number, LineRect>()

  for (const node of Array.from(root.querySelectorAll("[data-line]")) as HTMLElement[]) {
    const raw = node.dataset.line
    if (!raw) continue
    const value = parseInt(raw, 10)
    if (Number.isNaN(value)) continue
    if (seen.has(value)) continue

    const rect = node.getBoundingClientRect()
    if (rect.height === 0) continue

    seen.set(value, {
      line: value,
      top: rect.top - containerRect.top,
      height: rect.height,
    })
  }

  return Array.from(seen.values())
}

async function readConflictPayload(err: unknown): Promise<
  | {
      currentContent?: string
      currentLineContent?: string
    }
  | undefined
> {
  if (!err || typeof err !== "object") return undefined
  const maybeResponse = (err as { response?: Response }).response
  if (maybeResponse && typeof maybeResponse.status === "number" && maybeResponse.status === 409) {
    try {
      const body = await maybeResponse.clone().json()
      if (body && body.reason === "conflict") {
        return {
          currentContent: typeof body.currentContent === "string" ? body.currentContent : undefined,
          currentLineContent:
            typeof body.currentLineContent === "string" ? body.currentLineContent : undefined,
        }
      }
    } catch {
      return undefined
    }
  }
  const maybeErrorBody = (err as { error?: { reason?: string; currentContent?: string; currentLineContent?: string } })
    .error
  if (maybeErrorBody && maybeErrorBody.reason === "conflict") {
    return {
      currentContent: maybeErrorBody.currentContent,
      currentLineContent: maybeErrorBody.currentLineContent,
    }
  }
  return undefined
}

/**
 * Mounts an overlay that renders:
 *   - a single hovered-line pencil affordance on top of Pierre's file shadow DOM
 *   - an in-place single-line editor when the user activates editing
 *   - conflict and "large file" confirmation dialogs (via useDialog())
 *
 * Assumes the parent passes an already-eligible file (tier small/medium).
 */
export function FileEditHotspotLayer(props: HotspotLayerProps) {
  const language = useLanguage()
  const sdk = useSDK()
  const file = useFile()
  const comments = useComments()
  const dialog = useDialog()
  const [hovered, setHovered] = createSignal<LineRect | null>(null)
  const [rectMap, setRectMap] = createSignal<Map<number, LineRect>>(new Map())

  const recompute = () => {
    const host = props.container
    if (!host) return
    const root = findViewerRoot(host)
    if (!root) return
    const rects = collectLineRects(host, root)
    const map = new Map<number, LineRect>()
    for (const rect of rects) map.set(rect.line, rect)
    setRectMap(map)
    const current = hovered()
    if (current) {
      const fresh = map.get(current.line)
      if (fresh) setHovered(fresh)
    }
  }

  createEffect(() => {
    const host = props.container
    if (!host) return
    const handleMove = (event: MouseEvent) => {
      const rect = host.getBoundingClientRect()
      const y = event.clientY - rect.top
      const rects = rectMap()
      let best: LineRect | null = null
      for (const entry of rects.values()) {
        if (y >= entry.top && y <= entry.top + entry.height) {
          best = entry
          break
        }
      }
      setHovered(best)
    }
    const handleLeave = () => setHovered(null)
    makeEventListener(host, "mousemove", handleMove)
    makeEventListener(host, "mouseleave", handleLeave)
  })

  createEffect(() => {
    void props.content
    const host = props.container
    if (!host) return
    const frame = requestAnimationFrame(recompute)
    onCleanup(() => cancelAnimationFrame(frame))
  })

  createEffect(() => {
    const host = props.container
    if (!host) return
    const ro = new ResizeObserver(() => recompute())
    ro.observe(host)
    onCleanup(() => ro.disconnect())

    makeEventListener(window, "scroll", recompute, { capture: true, passive: true })
    makeEventListener(window, "resize", recompute)
  })

  const confirmLargeFile = () =>
    new Promise<boolean>((resolve) => {
      let settled = false
      const settle = (ok: boolean) => {
        if (settled) return
        settled = true
        resolve(ok)
      }
      dialog.show(
        () => (
          <Dialog
            title={language.t("file.edit.largeFileWarning.title")}
            description={language.t("file.edit.largeFileWarning.description")}
          >
            <div class="mt-3 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => {
                  settle(false)
                  dialog.close()
                }}
              >
                {language.t("common.cancel")}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  settle(true)
                  dialog.close()
                }}
              >
                {language.t("file.edit.largeFileWarning.continue")}
              </Button>
            </div>
          </Dialog>
        ),
        () => settle(false),
      )
    })

  const openLineEditor = async (lineRect: LineRect) => {
    if (props.editState.saving()) return
    const current = props.editState.target()
    if (current && current.file === props.filePath && current.line === lineRect.line) return

    if (props.editState.isEditing()) {
      const ok = await props.editState.confirmDiscard()
      if (!ok) return
    }

    if (props.tier === "medium" && !props.editState.hasAcknowledgedLargeFile(props.filePath)) {
      const confirmed = await confirmLargeFile()
      if (!confirmed) return
      props.editState.acknowledgeLargeFile(props.filePath)
    }

    const lines = splitLines(props.content)
    const original = lines[lineRect.line - 1] ?? ""
    props.editState.open({
      file: props.filePath,
      line: lineRect.line,
      original,
    })
  }

  const notifyCommentsOfEdit = (filePath: string, line: number, oldLine: string, newLine: string) => {
    if (newLine.trim() !== "" || oldLine.trim() === "") return
    const list = comments.list(filePath)
    const editedNote = language.t("file.edit.comment.editedNote")
    for (const comment of list) {
      const { start, end } = comment.selection
      if (line < Math.min(start, end) || line > Math.max(start, end)) continue
      if (comment.comment.includes(editedNote)) continue
      const updated = comment.comment ? `${comment.comment}\n\n${editedNote}` : editedNote
      comments.update(filePath, comment.id, updated)
    }
  }

  const keepMineFlow = async () => {
    const state = props.editState.conflict()
    if (!state) return
    const currentLine = state.currentLineContent ?? ""
    props.editState.setSaving(true)
    try {
      await sdk.client.file.editLine({
        path: state.target.file,
        line: state.target.line,
        oldContent: currentLine,
        newContent: state.draft,
      })
      await file.load(state.target.file, { force: true })
      props.editState.setConflict(null)
      props.editState.close()
    } catch (err: any) {
      showToast({
        variant: "error",
        title: language.t("file.edit.save.failed.title"),
        description: err?.message,
      })
    } finally {
      props.editState.setSaving(false)
    }
  }

  const reloadFromConflict = async () => {
    const state = props.editState.conflict()
    if (!state) return
    await file.load(state.target.file, { force: true })
    props.editState.setConflict(null)
    props.editState.close()
  }

  // Show conflict dialog when a conflict is set.
  createEffect(() => {
    const state = props.editState.conflict()
    if (!state) return
    const target = props.editState.target()
    if (!target || target.file !== props.filePath) return

    dialog.show(
      () => (
        <Dialog
          title={language.t("file.edit.conflict.title")}
          description={language.t("file.edit.conflict.description")}
        >
          <Show when={state.currentLineContent !== undefined}>
            <pre class="mt-2 max-h-40 overflow-auto rounded bg-surface p-2 font-mono text-xs">
              {state.currentLineContent}
            </pre>
          </Show>
          <div class="mt-3 flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={async () => {
                dialog.close()
                await keepMineFlow()
              }}
              disabled={props.editState.saving()}
            >
              {language.t("file.edit.conflict.keepMine")}
            </Button>
            <Button
              variant="primary"
              onClick={async () => {
                dialog.close()
                await reloadFromConflict()
              }}
              disabled={props.editState.saving()}
            >
              {language.t("file.edit.conflict.reload")}
            </Button>
          </div>
        </Dialog>
      ),
      () => props.editState.setConflict(null),
    )
  })

  // Show discard confirmation dialog whenever a prompt is requested.
  createEffect(() => {
    const prompt = props.editState.discardPrompt()
    if (!prompt) return
    dialog.show(
      () => (
        <Dialog
          title={language.t("file.edit.discard.title")}
          description={language.t("file.edit.discard.description")}
        >
          <div class="mt-3 flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                dialog.close()
                prompt.resolve(false)
              }}
            >
              {language.t("common.cancel")}
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                dialog.close()
                prompt.resolve(true)
              }}
            >
              {language.t("file.edit.discard.confirm")}
            </Button>
          </div>
        </Dialog>
      ),
      () => prompt.resolve(false),
    )
  })

  const handleSave = async (newContent: string) => {
    const target = props.editState.target()
    if (!target) return
    props.editState.setSaving(true)
    try {
      const response = (await sdk.client.file.editLine({
        path: target.file,
        line: target.line,
        oldContent: target.original,
        newContent,
      })) as { data?: { ok?: boolean; content?: string } }

      const data = response?.data
      if (data?.ok && typeof data.content === "string") {
        await file.load(target.file, { force: true })
        notifyCommentsOfEdit(target.file, target.line, target.original, newContent)
        props.editState.close()
      } else {
        showToast({
          variant: "error",
          title: language.t("file.edit.save.failed.title"),
        })
      }
    } catch (err: any) {
      const conflictData = await readConflictPayload(err)
      if (conflictData) {
        props.editState.setConflict({
          target,
          draft: newContent,
          currentContent: conflictData.currentContent,
          currentLineContent: conflictData.currentLineContent,
        })
      } else {
        showToast({
          variant: "error",
          title: language.t("file.edit.save.failed.title"),
          description: err?.message,
        })
      }
    } finally {
      props.editState.setSaving(false)
    }
  }

  const editorRect = () => {
    const target = props.editState.target()
    if (!target) return null
    if (target.file !== props.filePath) return null
    return rectMap().get(target.line) ?? null
  }

  const isEditingThisFile = () => {
    const target = props.editState.target()
    return !!target && target.file === props.filePath
  }

  return (
    <>
      <Show when={hovered()}>
        {(rect) => (
          <Show
            when={!isEditingThisFile() || props.editState.target()?.line !== rect().line}
            fallback={null}
          >
            <EditHotspot
              top={rect().top}
              height={rect().height}
              lineNumber={rect().line}
              onClick={() => openLineEditor(rect())}
            />
          </Show>
        )}
      </Show>

      <Show when={isEditingThisFile() && editorRect()}>
        {(rect) => {
          const target = props.editState.target()!
          return (
            <div
              class="pointer-events-auto absolute left-0 right-0 z-10"
              style={{
                top: `${rect().top}px`,
              }}
            >
              <LineEditor
                filePath={target.file}
                lineNumber={target.line}
                initialContent={target.original}
                saving={props.editState.saving()}
                onSave={handleSave}
                onCancel={() => {
                  props.editState.close()
                }}
              />
            </div>
          )
        }}
      </Show>
    </>
  )
}
