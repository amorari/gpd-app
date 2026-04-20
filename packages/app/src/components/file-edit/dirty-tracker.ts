import { createSignal } from "solid-js"

// Module-level signal: which file paths currently have an open inline line edit.
// A tab shows a dirty dot next to its filename while its path is in this set.
const [dirty, setDirty] = createSignal<ReadonlySet<string>>(new Set())

let beforeUnloadInstalled = false

function ensureBeforeUnloadHook() {
  if (beforeUnloadInstalled) return
  if (typeof window === "undefined") return
  beforeUnloadInstalled = true
  window.addEventListener("beforeunload", (event) => {
    if (dirty().size === 0) return
    event.preventDefault()
    // Chromium requires a non-empty returnValue to trigger the prompt.
    event.returnValue = ""
  })
}

export function isFileDirty(path: string): boolean {
  return dirty().has(path)
}

export function setFileDirty(path: string, value: boolean) {
  const current = dirty()
  const has = current.has(path)
  if (has === value) return
  const next = new Set(current)
  if (value) next.add(path)
  else next.delete(path)
  setDirty(next)
  if (value) ensureBeforeUnloadHook()
}

/** Reactive accessor for Solid tracking contexts (use inside createMemo/effect). */
export const dirtyFileSet = () => dirty()
