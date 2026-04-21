// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// B6 — Edge-case coverage for the digit-key highlight branch in `nav()`
// (see /tmp/opencode-pr-impl.md: L357-L436 for the keydown handler, and the
// behavior matrix for expected ignores). Focuses on inputs that MUST be
// ignored by the digit branch and on the 10-option cap (digits only reach
// indices 0..8 per `Math.min(count(), 9)`).
import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks — installed before the component imports resolve. Pattern mirrors
// src/components/prompt-input/submit.test.ts.
// ---------------------------------------------------------------------------

type ReplyCall = { requestID: string; answers: string[][] }
const replyCalls: ReplyCall[] = []
const rejectCalls: string[] = []
const toastCalls: unknown[] = []

let pendingReply: { resolve: (v: boolean) => void; reject: (err: unknown) => void } | null = null
let pendingReject: { resolve: (v: boolean) => void; reject: (err: unknown) => void } | null = null
let replyMode: "resolved" | "pending" = "resolved"
let rejectMode: "resolved" | "pending" = "resolved"

let SessionQuestionDock: Component<{ request: QuestionRequest; onSubmit: () => void }>
let render: typeof import("solid-js/web").render
let QueryClient: typeof import("@tanstack/solid-query").QueryClient
let QueryClientProvider: typeof import("@tanstack/solid-query").QueryClientProvider

beforeAll(async () => {
  mock.module("@/context/sdk", () => ({
    useSDK: () => ({
      directory: "/repo",
      url: "http://localhost:4096",
      event: { on: () => () => undefined, emit: () => undefined },
      createClient: () => ({}),
      client: {
        question: {
          reply: (input: { requestID: string; answers: string[][] }) => {
            replyCalls.push({ requestID: input.requestID, answers: input.answers.map((a) => [...a]) })
            if (replyMode === "pending") {
              return new Promise<boolean>((resolve, reject) => {
                pendingReply = { resolve, reject }
              })
            }
            return Promise.resolve(true)
          },
          reject: (input: { requestID: string }) => {
            rejectCalls.push(input.requestID)
            if (rejectMode === "pending") {
              return new Promise<boolean>((resolve, reject) => {
                pendingReject = { resolve, reject }
              })
            }
            return Promise.resolve(true)
          },
        },
      },
    }),
  }))

  mock.module("@/context/language", () => ({
    useLanguage: () => ({
      t: (key: string) => key,
    }),
  }))

  mock.module("@opencode-ai/ui/toast", () => ({
    showToast: (toast: unknown) => {
      toastCalls.push(toast)
      return 0
    },
  }))

  const solidWeb = await import("solid-js/web")
  render = solidWeb.render

  const query = await import("@tanstack/solid-query")
  QueryClient = query.QueryClient
  QueryClientProvider = query.QueryClientProvider

  const mod = await import("./session-question-dock")
  SessionQuestionDock = mod.SessionQuestionDock
})

beforeEach(() => {
  replyCalls.length = 0
  rejectCalls.length = 0
  toastCalls.length = 0
  pendingReply = null
  pendingReject = null
  replyMode = "resolved"
  rejectMode = "resolved"
})

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeRequest(input: {
  id?: string
  questions: Array<{
    question?: string
    header?: string
    options: Array<{ label: string; description?: string }>
    multiple?: boolean
    custom?: boolean
  }>
}): QuestionRequest {
  return {
    id: input.id ?? "req-1",
    sessionID: "sess-1",
    questions: input.questions.map((q) => ({
      question: q.question ?? "Pick one",
      header: q.header ?? "Question",
      options: q.options.map((o) => ({ label: o.label, description: o.description ?? "" })),
      multiple: q.multiple,
      custom: q.custom,
    })),
  } as unknown as QuestionRequest
}

function mount(request: QuestionRequest, onSubmit: () => void = () => undefined) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const dispose = render(
    () => (
      <QueryClientProvider client={client}>
        <SessionQuestionDock request={request} onSubmit={onSubmit} />
      </QueryClientProvider>
    ),
    container,
  )
  return {
    container,
    cleanup: () => {
      dispose()
      container.remove()
    },
  }
}

// Flush microtasks + a couple of animation frames: useMutation is async and
// the component's focus() uses requestAnimationFrame.
async function flush() {
  for (let i = 0; i < 4; i++) {
    await Promise.resolve()
    await new Promise<void>((r) => requestAnimationFrame(() => r()))
  }
  await Promise.resolve()
}

function options(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    container.querySelectorAll<HTMLButtonElement>(
      '[data-slot="question-option"]:not([data-custom="true"])',
    ),
  )
}

function dock(container: HTMLElement): HTMLElement {
  const el = container.querySelector('[data-component="dock-prompt"]') as HTMLElement | null
  if (!el) throw new Error("dock-prompt element not found")
  return el
}

// Helper — construct options with labels opt-1, opt-2, ... opt-N.
function labels(n: number): Array<{ label: string }> {
  return Array.from({ length: n }, (_, i) => ({ label: `opt-${i + 1}` }))
}

function pressDigit(
  el: HTMLElement,
  digit: string,
  modifiers: {
    metaKey?: boolean
    ctrlKey?: boolean
    altKey?: boolean
    shiftKey?: boolean
  } = {},
) {
  const ev = new KeyboardEvent("keydown", {
    key: digit,
    metaKey: modifiers.metaKey ?? false,
    ctrlKey: modifiers.ctrlKey ?? false,
    altKey: modifiers.altKey ?? false,
    shiftKey: modifiers.shiftKey ?? false,
    bubbles: true,
    cancelable: true,
  })
  el.dispatchEvent(ev)
  return ev
}

function highlightedOption(container: HTMLElement): HTMLButtonElement | null {
  return container.querySelector<HTMLButtonElement>(
    '[data-slot="question-option"][data-highlighted="true"]',
  )
}

// ---------------------------------------------------------------------------
// Tests — digit-branch edge cases. Contract: /tmp/opencode-pr-impl.md §L357-L436
// and the behavior matrix rows for "Digit '0'", "Digit with Cmd/Ctrl/Alt/Meta",
// "Digit out of range", and "10+ options".
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — digit-branch edge cases", () => {
  test("digit '0' is ignored (loop is '1'-'9' only)", async () => {
    const req = makeRequest({
      id: "req-zero",
      questions: [{ options: labels(3) }],
    })
    const m = mount(req)
    await flush()

    expect(highlightedOption(m.container)).toBeNull()
    pressDigit(dock(m.container), "0")
    await flush()

    // Nothing highlighted, no reply, no toast.
    expect(highlightedOption(m.container)).toBeNull()
    expect(replyCalls.length).toBe(0)
    expect(toastCalls.length).toBe(0)

    m.cleanup()
  })

  test("Cmd+digit is ignored (modifier early return at L378)", async () => {
    const req = makeRequest({
      id: "req-cmd-digit",
      questions: [{ options: labels(3) }],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    const ev = pressDigit(dock(m.container), "1", { metaKey: true })
    await flush()

    expect(highlightedOption(m.container)).toBeNull()
    expect(replyCalls.length).toBe(0)
    expect(submitted).toBe(0)
    // Modifier early-return must not swallow browser default (no preventDefault).
    expect(ev.defaultPrevented).toBe(false)

    m.cleanup()
  })

  test("Ctrl+digit is ignored (modifier early return)", async () => {
    const req = makeRequest({
      id: "req-ctrl-digit",
      questions: [{ options: labels(3) }],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    const ev = pressDigit(dock(m.container), "2", { ctrlKey: true })
    await flush()

    expect(highlightedOption(m.container)).toBeNull()
    expect(replyCalls.length).toBe(0)
    expect(submitted).toBe(0)
    expect(ev.defaultPrevented).toBe(false)

    m.cleanup()
  })

  test("Alt+digit is ignored (modifier early return)", async () => {
    const req = makeRequest({
      id: "req-alt-digit",
      questions: [{ options: labels(3) }],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    const ev = pressDigit(dock(m.container), "3", { altKey: true })
    await flush()

    expect(highlightedOption(m.container)).toBeNull()
    expect(replyCalls.length).toBe(0)
    expect(submitted).toBe(0)
    expect(ev.defaultPrevented).toBe(false)

    m.cleanup()
  })

  test("10 options: the 10th option has no digit badge and no aria-keyshortcuts", async () => {
    const req = makeRequest({
      id: "req-ten",
      questions: [{ options: labels(10) }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(10)

    // Options 0..8 (1st..9th) each carry a digit badge + aria-keyshortcuts.
    for (let i = 0; i < 9; i++) {
      const opt = opts[i]!
      expect(opt.getAttribute("aria-keyshortcuts")).toBe(String(i + 1))
      const badge = opt.querySelector('.opt-num, [data-slot="question-option-num"]')
      expect(badge).not.toBeNull()
    }

    // The 10th option (index 9) gets no badge and no aria-keyshortcuts attr.
    const tenth = opts[9]!
    expect(tenth.hasAttribute("aria-keyshortcuts")).toBe(false)
    const tenthBadge = tenth.querySelector('.opt-num, [data-slot="question-option-num"]')
    expect(tenthBadge).toBeNull()

    m.cleanup()
  })

  test("10 options: digit '9' highlights the 9th option; no digit reaches option index 9", async () => {
    const req = makeRequest({
      id: "req-ten-digit",
      questions: [{ options: labels(10) }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(10)

    // Press "9" → highlight index 8 (the 9th option), not index 9.
    pressDigit(dock(m.container), "9")
    await flush()

    const highlighted = highlightedOption(m.container)
    expect(highlighted).not.toBeNull()
    expect(highlighted).toBe(opts[8]!)
    expect(opts[9]!.getAttribute("data-highlighted")).not.toBe("true")

    // No single digit key can highlight opts[9] — sweep "1"-"9" and assert
    // opts[9] never carries data-highlighted="true".
    for (const d of ["1", "2", "3", "4", "5", "6", "7", "8", "9"]) {
      pressDigit(dock(m.container), d)
      await flush()
      expect(opts[9]!.getAttribute("data-highlighted")).not.toBe("true")
    }

    // No stray reply/submit from any of the digit presses (single-choice + no
    // Enter follow-up means nothing should have been committed).
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test("Shift+digit is ignored (key is '!' etc., does not match '1'-'9')", async () => {
    // Shift+1 yields key="!" on real keyboards. Even if a caller forwarded
    // key="1" with shiftKey=true, the branch should still treat Shift-held
    // digits as not-a-digit-shortcut — browsers deliver "!" for 1, "@" for 2,
    // etc., and our switch matches on `event.key` only.
    const req = makeRequest({
      id: "req-shift-digit",
      questions: [{ options: labels(3) }],
    })
    const m = mount(req)
    await flush()

    // Real-world: Shift+"1" is delivered as key="!" by the browser.
    const ev = pressDigit(dock(m.container), "!", { shiftKey: true })
    await flush()

    expect(highlightedOption(m.container)).toBeNull()
    expect(replyCalls.length).toBe(0)
    // "!" is not a key we handle, so no preventDefault.
    expect(ev.defaultPrevented).toBe(false)

    m.cleanup()
  })
})
