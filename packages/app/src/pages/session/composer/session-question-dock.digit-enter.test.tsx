// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// Agent B2 — digit+Enter flow tests (DESIGN.md §5, §6, impl summary
// /tmp/opencode-pr-impl.md "Behavior matrix"). The digit highlights an
// option via `highlightOption()`; a subsequent plain Enter commits through
// `selectOption()` → `pick()` (single-choice auto-submit / advance) or
// `toggle()` (multi-choice, no submit).
import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks — installed before the component imports resolve. Pattern mirrors
// the PR #1 companion test file (./session-question-dock.test.tsx).
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

// Dispatch a bubbling keydown from a target inside the options container.
// The `nav` handler lives on the DockPrompt root (onKeyDown) and filters by
// `event.target.closest('[data-slot="question-options"]')`, so the target
// must be a descendant of that container for digit/Enter branches to fire.
function pressKey(target: HTMLElement, key: string, init: KeyboardEventInit = {}) {
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...init }),
  )
}

// ---------------------------------------------------------------------------
// Tests — digit highlight + Enter commit flow.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — digit key + Enter commit", () => {
  test("single-choice + single question: digit '2' then Enter submits options[1] once, no Submit button", async () => {
    const req = makeRequest({
      id: "req-single",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    let submittedCount = 0
    const m = mount(req, () => submittedCount++)
    await flush()

    // Single-choice + single-question dock has no primary Submit/Next button.
    expect(submitButton(m.container)).toBeNull()
    expect(nextButton(m.container)).toBeNull()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    // Digit "2" highlights option index 1. Target can be any node inside
    // the options container; use opts[0] as a stable anchor so the event's
    // .closest('[data-slot="question-options"]') match succeeds regardless
    // of current document.activeElement.
    pressKey(opts[0]!, "2")
    await flush()

    // Highlight landed on index 1, focus moved.
    expect(opts[1]!.getAttribute("data-highlighted")).toBe("true")
    expect(opts[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(document.activeElement).toBe(opts[1]!)
    // No reply yet — digit is highlight-only.
    expect(replyCalls.length).toBe(0)

    // Plain Enter on the highlighted option commits → selectOption → pick →
    // autoProgress → reply ("No" is options[1].label).
    pressKey(opts[1]!, "Enter")
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["No"]])
    expect(replyCalls[0]!.requestID).toBe(req.id)
    // onMutate fires onSubmit optimistically.
    expect(submittedCount).toBe(1)
    // Still no Submit button rendered after the pick.
    expect(submitButton(m.container)).toBeNull()

    m.cleanup()
  })

  test("single-choice + multi question: digit '1' then Enter advances to Q2, focuses first option of Q2", async () => {
    const req = makeRequest({
      id: "req-advance",
      questions: [
        { question: "Q1", options: [{ label: "A" }, { label: "B" }] },
        { question: "Q2", options: [{ label: "X" }, { label: "Y" }] },
      ],
    })
    const m = mount(req)
    await flush()

    const q1Opts = options(m.container)
    expect(q1Opts.length).toBe(2)

    // Highlight option 0 via digit "1".
    pressKey(q1Opts[0]!, "1")
    await flush()
    expect(q1Opts[0]!.getAttribute("data-highlighted")).toBe("true")
    expect(document.activeElement).toBe(q1Opts[0]!)

    // Enter commits: autoProgress moves to Q2, no reply yet.
    pressKey(q1Opts[0]!, "Enter")
    await flush()

    expect(replyCalls.length).toBe(0)
    const questionText = m.container.querySelector('[data-slot="question-text"]')
    expect(questionText?.textContent).toBe("Q2")

    // Focus landed on Q2's first option (role=radio) — DESIGN.md §6 a11y
    // contract: auto-advance focuses the first option of the new tab.
    const q2Opts = options(m.container)
    expect(q2Opts.length).toBe(2)
    expect(document.activeElement).toBe(q2Opts[0]!)
    expect(document.activeElement?.getAttribute("role")).toBe("radio")
    // Fresh tab — no highlight carried over.
    expect(q2Opts[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(q2Opts[1]!.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })

  test("multi-choice: digit '2' + Enter toggles option 1 only (aria-checked flips, no submit); digit '3' + Enter toggles option 2; Submit still required", async () => {
    const req = makeRequest({
      id: "req-multi-digit",
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

    // Primary Submit button is visible on multi-choice.
    expect(submitButton(m.container)).not.toBeNull()

    const opts = options(m.container)
    expect(opts.length).toBe(3)
    expect(opts[1]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[2]!.getAttribute("aria-checked")).toBe("false")

    // Digit "2" → highlight opts[1], Enter → toggle (no submit).
    pressKey(opts[0]!, "2")
    await flush()
    expect(opts[1]!.getAttribute("data-highlighted")).toBe("true")
    pressKey(opts[1]!, "Enter")
    await flush()
    expect(opts[1]!.getAttribute("aria-checked")).toBe("true")
    expect(replyCalls.length).toBe(0)
    // After commit, highlight is cleared (selectOption clears on entry).
    expect(opts[1]!.getAttribute("data-highlighted")).toBeNull()

    // Digit "3" → highlight opts[2], Enter → toggle (no submit).
    pressKey(opts[1]!, "3")
    await flush()
    expect(opts[2]!.getAttribute("data-highlighted")).toBe("true")
    pressKey(opts[2]!, "Enter")
    await flush()
    expect(opts[2]!.getAttribute("aria-checked")).toBe("true")
    // opts[1] stays checked — toggle is independent per-option.
    expect(opts[1]!.getAttribute("aria-checked")).toBe("true")
    expect(replyCalls.length).toBe(0)

    // Submit button still present and required for final submit.
    const submit = submitButton(m.container)
    expect(submit).not.toBeNull()
    submit!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    // Both "Two" and "Three" selected; final submit carries both labels.
    expect(replyCalls[0]!.answers).toEqual([["Two", "Three"]])

    m.cleanup()
  })

  test("Enter with no prior digit highlight is a nav-level no-op (no reply, no errors, no unintended submit)", async () => {
    const req = makeRequest({
      id: "req-enter-only",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    // Confirm baseline: no highlight on any option.
    for (const o of opts) expect(o.getAttribute("data-highlighted")).toBeNull()

    // Dispatch plain Enter without setting focus (activeElement may be body).
    // The nav handler's Enter branch short-circuits when store.highlighted === -1.
    pressKey(opts[0]!, "Enter")
    await flush()

    // No submit, no advance, no thrown errors (test would fail on unhandled).
    expect(replyCalls.length).toBe(0)
    // Question text unchanged (still first question).
    const questionText = m.container.querySelector('[data-slot="question-text"]')
    expect(questionText?.textContent).toBe("Pick one")
    // Still no highlight state lingering.
    for (const o of options(m.container)) expect(o.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })

  test("double-Enter protection: digit '1' + Enter + Enter → reply called at most once", async () => {
    // Hold the mutation pending so the sending() guard is exercised; without
    // pending mode the first reply resolves before the second Enter fires
    // and we'd only be testing the highlight-cleared guard, not sending().
    replyMode = "pending"
    const req = makeRequest({
      id: "req-double-enter",
      questions: [{ options: [{ label: "Only" }, { label: "Other" }] }],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    // Highlight opt 0 with digit "1".
    pressKey(opts[0]!, "1")
    await flush()
    expect(opts[0]!.getAttribute("data-highlighted")).toBe("true")

    // Rapid double-Enter: first commits, second must be blocked. Second
    // Enter may hit either the sending() guard inside selectOption or the
    // highlight-cleared guard in nav (clearHighlight runs before
    // selectOption). Either way: at most one reply.
    pressKey(opts[0]!, "Enter")
    pressKey(opts[0]!, "Enter")
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Only"]])

    // Resolve the pending mutation for clean teardown.
    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })
})
