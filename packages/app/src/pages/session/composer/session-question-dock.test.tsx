// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
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

function submitButton(container: HTMLElement): HTMLButtonElement | null {
  const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
  return buttons.find((b) => b.textContent?.trim() === "ui.common.submit") ?? null
}

function nextButton(container: HTMLElement): HTMLButtonElement | null {
  const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
  return buttons.find((b) => b.textContent?.trim() === "ui.common.next") ?? null
}

// ---------------------------------------------------------------------------
// Tests — covering DESIGN.md §5 + §6 scenarios.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — auto-submit on single-choice", () => {
  test("single-choice + single question: click option → reply called once, no Submit in DOM", async () => {
    const req = makeRequest({
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    let submittedCount = 0
    const m = mount(req, () => submittedCount++)

    await flush()

    // Primary submit/next button must be absent for a single-choice-single-question dock.
    expect(submitButton(m.container)).toBeNull()
    expect(nextButton(m.container)).toBeNull()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    opts[0]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Yes"]])
    expect(replyCalls[0]!.requestID).toBe(req.id)
    // onMutate fires onSubmit optimistically.
    expect(submittedCount).toBe(1)
    expect(submitButton(m.container)).toBeNull()

    m.cleanup()
  })

  test("single-choice + multi question: auto-advances without submit, final pick submits accumulated answers", async () => {
    const req = makeRequest({
      id: "req-multi",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
      ],
    })
    const m = mount(req)
    await flush()

    // Tab 1: pick A → advances, no reply.
    options(m.container)[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)

    const questionText = m.container.querySelector('[data-slot="question-text"]')
    expect(questionText?.textContent).toBe("Q2")

    // Tab 2: pick Y (last question) → submit.
    options(m.container)[1]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["A"], ["Y"]])

    m.cleanup()
  })

  test("multi-choice: clicking options toggles selection, does NOT submit; explicit Submit required", async () => {
    const req = makeRequest({
      id: "req-multi-choice",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }],
        },
      ],
    })
    const m = mount(req)
    await flush()

    // Submit button IS present for multi-choice (primaryButtonVisible = true).
    expect(submitButton(m.container)).not.toBeNull()

    options(m.container)[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(options(m.container)[0]!.getAttribute("aria-checked")).toBe("true")

    options(m.container)[2]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(options(m.container)[2]!.getAttribute("aria-checked")).toBe("true")

    // Toggle first option back off.
    options(m.container)[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(options(m.container)[0]!.getAttribute("aria-checked")).toBe("false")

    // Click Submit explicitly.
    submitButton(m.container)!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Three"]])

    m.cleanup()
  })

  test("double-submit protection: rapid clicks produce exactly one reply (pending mutation)", async () => {
    replyMode = "pending"
    const req = makeRequest({
      id: "req-rapid",
      questions: [{ options: [{ label: "Only" }] }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(1)

    // Rapid triple click — second and third must be blocked by sending() guard.
    opts[0]!.click()
    opts[0]!.click()
    opts[0]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Only"]])

    // Resolve the pending mutation for clean teardown.
    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })

  test("keyboard: Enter on focused single-choice option auto-advances (tab 1 → tab 2)", async () => {
    const req = makeRequest({
      id: "req-keyboard",
      questions: [
        { question: "Q1", options: [{ label: "Alpha" }, { label: "Beta" }] },
        { question: "Q2", options: [{ label: "Gamma" }] },
      ],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    // Native browser behaviour: Enter on a <button role="radio"> fires a click.
    // happy-dom honours this, so dispatching a click on the focused option
    // is equivalent to the Enter key activating it. (DESIGN.md §4.3, §6.8.)
    opts[0]!.focus()
    opts[0]!.click()
    await flush()

    // Advanced to Q2, no reply yet.
    expect(replyCalls.length).toBe(0)
    const text = m.container.querySelector('[data-slot="question-text"]')
    expect(text?.textContent).toBe("Q2")

    m.cleanup()
  })

  test("keyboard: Cmd+Enter submits on multi-choice (still works while primary button is present)", async () => {
    const req = makeRequest({
      id: "req-cmd-enter",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }],
        },
      ],
    })
    const m = mount(req)
    await flush()

    // Select one option (does not submit).
    options(m.container)[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)

    // Dispatch Cmd+Enter on the dock root.
    const dock = m.container.querySelector('[data-component="dock-prompt"]') as HTMLElement
    expect(dock).not.toBeNull()
    dock.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        metaKey: true,
        bubbles: true,
        cancelable: true,
      }),
    )
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["One"]])

    m.cleanup()
  })

  test("a11y: after auto-advance, document.activeElement is a role=radio in the new tab", async () => {
    const req = makeRequest({
      id: "req-a11y",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
      ],
    })
    const m = mount(req)
    await flush()

    // Auto-advance from Q1 → Q2.
    options(m.container)[0]!.click()
    await flush()

    const active = document.activeElement
    expect(active).not.toBeNull()
    expect(active?.getAttribute("role")).toBe("radio")
    // The active element should be one of the new tab's options.
    const optsAfter = options(m.container)
    expect(optsAfter.some((o) => o === active)).toBe(true)

    m.cleanup()
  })
})
