// Regression suite for PR #1's click-auto-submit behavior. After the
// digit-highlight feature landed, `selectOption` now clears `store.highlighted`
// as a side effect but must still route clicks through `pick()` →
// `autoProgress()` for single-choice and `toggle()` for multi-choice. These
// tests exercise the click path exclusively — see
// session-question-dock.test.tsx for the primary dock coverage, and the
// sibling keyboard/digit suites for Enter/digit paths.
//
// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks — installed before the component imports resolve. Pattern mirrors
// src/components/prompt-input/submit.test.ts and the primary dock suite.
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
// Test helpers — mirror the primary suite so fixtures stay in sync.
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

function dockRoot(container: HTMLElement): HTMLElement {
  const dock = container.querySelector('[data-component="dock-prompt"]') as HTMLElement | null
  if (!dock) throw new Error("dock root not found")
  return dock
}

// ---------------------------------------------------------------------------
// Tests — click path regressions for PR #1 semantics. The digit-highlight
// feature added to the dock must not alter click behavior in any way except
// the documented side-effect of clearing `store.highlighted`.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — click-path regression (PR #1)", () => {
  test("single-choice click submits exactly once via reply mutation", async () => {
    // PR #1 contract: click on a single-choice option runs pick() → autoProgress()
    // → submit. After the digit feature, `selectOption` clears highlight first,
    // but the submit semantics must be identical.
    const req = makeRequest({
      id: "req-click-single",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    let submittedCount = 0
    const m = mount(req, () => submittedCount++)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    opts[1]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.requestID).toBe(req.id)
    expect(replyCalls[0]!.answers).toEqual([["No"]])
    // onMutate fires onSubmit optimistically.
    expect(submittedCount).toBe(1)

    m.cleanup()
  })

  test("multi-choice clicks toggle aria-checked without submitting", async () => {
    // Click path for multi must still route to toggle(), NOT pick()/autoProgress().
    // No reply until explicit Submit.
    const req = makeRequest({
      id: "req-click-multi",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "Alpha" }, { label: "Beta" }, { label: "Gamma" }],
        },
      ],
    })
    const m = mount(req)
    await flush()

    const opts = () => options(m.container)
    expect(opts()[0]!.getAttribute("aria-checked")).toBe("false")
    expect(opts()[1]!.getAttribute("aria-checked")).toBe("false")

    opts()[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(opts()[0]!.getAttribute("aria-checked")).toBe("true")
    expect(opts()[1]!.getAttribute("aria-checked")).toBe("false")

    opts()[1]!.click()
    await flush()
    expect(replyCalls.length).toBe(0)
    expect(opts()[0]!.getAttribute("aria-checked")).toBe("true")
    expect(opts()[1]!.getAttribute("aria-checked")).toBe("true")

    // Submit button is still present — no auto-submit on multi click.
    expect(submitButton(m.container)).not.toBeNull()

    m.cleanup()
  })

  test("click after digit highlight picks the clicked option and clears data-highlighted", async () => {
    // Digit "2" highlights opts[1]; clicking opts[0] must submit "Alpha"
    // (not "Beta"), and the data-highlighted attribute must disappear because
    // selectOption() resets store.highlighted to -1.
    const req = makeRequest({
      id: "req-click-after-digit",
      questions: [{ options: [{ label: "Alpha" }, { label: "Beta" }, { label: "Gamma" }] }],
    })
    const m = mount(req)
    await flush()

    // Dispatch digit "2" on the dock root to highlight the 2nd option.
    dockRoot(m.container).dispatchEvent(
      new KeyboardEvent("keydown", { key: "2", bubbles: true, cancelable: true }),
    )
    await flush()

    const before = options(m.container)
    expect(before[1]!.getAttribute("data-highlighted")).toBe("true")
    // Sanity: the other options are not highlighted.
    expect(before[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(before[2]!.getAttribute("data-highlighted")).toBeNull()

    // Now click the FIRST option — the clicked one wins, not the highlighted one.
    before[0]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Alpha"]])

    // data-highlighted is cleared from every option after the click commits.
    for (const opt of options(m.container)) {
      expect(opt.getAttribute("data-highlighted")).toBeNull()
    }

    m.cleanup()
  })

  test("rapid double-click on same single-choice option submits exactly once", async () => {
    // Double-submit protection via sending() guard inside selectOption().
    // Use pending mode so the mutation stays in flight between clicks.
    replyMode = "pending"
    const req = makeRequest({
      id: "req-click-double",
      questions: [{ options: [{ label: "Only" }] }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(1)

    // Fire two clicks back-to-back — the second must be suppressed.
    opts[0]!.click()
    opts[0]!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Only"]])

    // Release the in-flight mutation for clean teardown.
    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })

  test("click while a prior mutation is pending produces no additional submit", async () => {
    // Two options: click first (pending), then click second before resolution.
    // Guard must reject the second click entirely.
    replyMode = "pending"
    const req = makeRequest({
      id: "req-click-pending",
      questions: [{ options: [{ label: "First" }, { label: "Second" }] }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    opts[0]!.click()
    await flush()
    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["First"]])

    // Second click while mutation is still pending: ignored.
    opts[1]!.click()
    await flush()
    expect(replyCalls.length).toBe(1)

    // Resolve to unblock teardown.
    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })
})
