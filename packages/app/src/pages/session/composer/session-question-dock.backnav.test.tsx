// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// These tests focus specifically on the interaction between:
//   - Back-navigation via progress-segment jump
//   - Single-choice auto-submit on the final tab
// See DESIGN.md §5 (progress header) + §6 (auto-submit semantics).
import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks — mirror session-question-dock.test.tsx exactly so the two files can
// be run independently without cross-contamination.
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
// Test helpers (duplicated from session-question-dock.test.tsx for isolation)
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

function progressSegments(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    container.querySelectorAll<HTMLButtonElement>('[data-slot="question-progress-segment"]'),
  )
}

function questionText(container: HTMLElement): string {
  return container.querySelector('[data-slot="question-text"]')?.textContent ?? ""
}

// ---------------------------------------------------------------------------
// Tests — back-navigation via progress-segment + auto-submit interaction.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — progress-jump back-nav interaction with auto-submit", () => {
  test("progress-jump backward from tab 1 → tab 0 preserves prior pick; does NOT submit", async () => {
    const req = makeRequest({
      id: "req-backnav-preserve",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
        { question: "Q3", options: [{ label: "M" }, { label: "N" }] },
      ],
    })
    let submittedCount = 0
    const m = mount(req, () => submittedCount++)
    await flush()

    // Auto-advance: pick "A" on Q1 → lands on Q2.
    options(m.container)[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(submittedCount).toBe(0)
    expect(questionText(m.container)).toBe("Q2")

    // Click progress segment for tab 0 → back-navigate to Q1.
    const segs = progressSegments(m.container)
    expect(segs.length).toBe(3)
    segs[0]!.click()
    await flush()

    // Should NOT have submitted. Still no reply dispatched.
    expect(replyCalls.length).toBe(0)
    expect(submittedCount).toBe(0)
    // Now displaying Q1.
    expect(questionText(m.container)).toBe("Q1")

    // "A" is still selected (aria-checked="true" on original option).
    const opts = options(m.container)
    expect(opts.length).toBe(2)
    expect(opts[0]!.getAttribute("aria-checked")).toBe("true")
    expect(opts[1]!.getAttribute("aria-checked")).toBe("false")

    m.cleanup()
  })

  test("after back-nav, picking a different option auto-advances without double-submit", async () => {
    const req = makeRequest({
      id: "req-backnav-repick",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
        { question: "Q3", options: [{ label: "M" }, { label: "N" }] },
      ],
    })
    let submittedCount = 0
    const m = mount(req, () => submittedCount++)
    await flush()

    // Pick "A" on Q1 → auto-advance.
    options(m.container)[0]!.click()
    await flush()
    expect(questionText(m.container)).toBe("Q2")

    // Back-nav via progress segment 0.
    progressSegments(m.container)[0]!.click()
    await flush()
    expect(questionText(m.container)).toBe("Q1")

    // Re-pick: now choose "B" instead of "A".
    const opts = options(m.container)
    opts[1]!.click()
    await flush()

    // Auto-advances again to Q2, but nothing submitted (not final tab).
    expect(replyCalls.length).toBe(0)
    expect(submittedCount).toBe(0)
    expect(questionText(m.container)).toBe("Q2")

    // And the new pick overwrote the old one — only "B" is recorded for Q1.
    // (Re-navigate back to confirm a11y state.)
    progressSegments(m.container)[0]!.click()
    await flush()
    const reOpts = options(m.container)
    expect(reOpts[0]!.getAttribute("aria-checked")).toBe("false") // "A" is gone
    expect(reOpts[1]!.getAttribute("aria-checked")).toBe("true") // "B" is current

    m.cleanup()
  })

  test("final-tab single-choice pick submits; progress-jump after submit is a no-op (dock unmounted)", async () => {
    const req = makeRequest({
      id: "req-final-submit",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
        { question: "Q3", options: [{ label: "M" }, { label: "N" }] },
      ],
    })
    let submittedCount = 0

    // Host simulates the real session-composer-region behaviour: unmount the
    // dock when onSubmit fires (the parent swaps the UI back to the regular
    // prompt). We capture the segment refs BEFORE cleanup so we can click
    // them afterwards and assert no-op.
    const container = document.createElement("div")
    document.body.appendChild(container)
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    let disposed = false
    const onSubmit = () => {
      submittedCount++
      // Defer unmount to mirror real flow (parent reacts to onSubmit).
      queueMicrotask(() => {
        if (disposed) return
        disposed = true
        dispose()
      })
    }

    const dispose = render(
      () => (
        <QueryClientProvider client={client}>
          <SessionQuestionDock request={req} onSubmit={onSubmit} />
        </QueryClientProvider>
      ),
      container,
    )
    await flush()

    // Advance through Q1 → Q2.
    options(container)[0]!.click()
    await flush()
    expect(questionText(container)).toBe("Q2")
    // Advance through Q2 → Q3.
    options(container)[0]!.click()
    await flush()
    expect(questionText(container)).toBe("Q3")

    // Grab segment references BEFORE the final pick triggers unmount.
    const segsBeforeSubmit = progressSegments(container)
    expect(segsBeforeSubmit.length).toBe(3)

    // Final tab: picking ANY option triggers submit (reply with all answers).
    options(container)[1]!.click() // "N"
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.requestID).toBe(req.id)
    expect(replyCalls[0]!.answers).toEqual([["A"], ["X"], ["N"]])
    expect(submittedCount).toBe(1)

    // Dock should have been unmounted (our onSubmit-handler disposed it).
    expect(disposed).toBe(true)
    expect(progressSegments(container).length).toBe(0)

    // Clicking a stale, detached progress segment is a no-op — no extra reply,
    // no extra onSubmit.
    const beforeReplies = replyCalls.length
    const beforeSubmits = submittedCount
    segsBeforeSubmit[0]!.click()
    segsBeforeSubmit[1]!.click()
    await flush()
    expect(replyCalls.length).toBe(beforeReplies)
    expect(submittedCount).toBe(beforeSubmits)

    container.remove()
  })
})
