// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// Tests the digit-key + Enter behaviour for MULTI-CHOICE questions introduced
// in feat/questionnaire-number-keys. The contract differs from single-choice:
// Enter on a digit-highlighted option toggles (does NOT auto-submit), and the
// primary Submit button remains visible throughout the interaction. See
// /tmp/opencode-pr-impl.md behavior matrix rows for
// "Enter on highlighted multi-choice option" and primaryButtonVisible().
import { beforeAll, beforeEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks — installed before the component imports resolve. Pattern mirrors
// session-question-dock.test.tsx.
// ---------------------------------------------------------------------------

type ReplyCall = { requestID: string; answers: string[][] }
const replyCalls: ReplyCall[] = []
const rejectCalls: string[] = []
const toastCalls: unknown[] = []

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
            return Promise.resolve(true)
          },
          reject: (input: { requestID: string }) => {
            rejectCalls.push(input.requestID)
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
})

// ---------------------------------------------------------------------------
// Test helpers — same pattern as session-question-dock.test.tsx, inlined per
// test-author instructions (no cross-file helper extraction).
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
    id: input.id ?? "req-multi-digit-1",
    sessionID: "sess-1",
    questions: input.questions.map((q) => ({
      question: q.question ?? "Pick many",
      header: q.header ?? "Question",
      options: q.options.map((o) => ({ label: o.label, description: o.description ?? "" })),
      multiple: q.multiple,
      custom: q.custom,
    })),
  } as unknown as QuestionRequest
}

function renderDock(request: QuestionRequest, onSubmit: () => void = () => undefined) {
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
  if (!dock) throw new Error("dock-prompt root not found in container")
  return dock
}

function pressKey(container: HTMLElement, key: string) {
  dockRoot(container).dispatchEvent(
    new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
    }),
  )
}

// ---------------------------------------------------------------------------
// Tests — multi-choice digit-key + Enter toggle behaviour.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — multi-choice digit keys", () => {
  test('pressing "1" highlights option 0 and focuses it, but aria-checked remains "false" until Enter', async () => {
    const req = makeRequest({
      id: "req-multi-highlight-only",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(4)

    // Precondition: nothing checked yet.
    for (const o of opts) {
      expect(o.getAttribute("aria-checked")).toBe("false")
    }

    pressKey(m.container, "1")
    await flush()

    // Highlighted + focused on option 0.
    expect(opts[0]!.getAttribute("data-highlighted")).toBe("true")
    expect(document.activeElement).toBe(opts[0])

    // aria-checked must NOT flip for multi-choice until Enter commits the pick.
    for (const o of opts) {
      expect(o.getAttribute("aria-checked")).toBe("false")
    }

    // Digit press alone never submits.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('pressing "1" then Enter toggles option 0 on (aria-checked="true"), but does NOT call the submit mutation', async () => {
    const req = makeRequest({
      id: "req-multi-enter-toggle",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    let submittedCount = 0
    const m = renderDock(req, () => submittedCount++)
    await flush()

    pressKey(m.container, "1")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    const opts = options(m.container)
    expect(opts[0]!.getAttribute("aria-checked")).toBe("true")
    // Other options unchanged.
    expect(opts[1]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[2]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[3]!.getAttribute("aria-checked")).toBe("false")

    // Multi-choice Enter must not trigger the reply mutation nor onSubmit.
    expect(replyCalls.length).toBe(0)
    expect(submittedCount).toBe(0)

    // Highlight should have been cleared by selectOption() on commit.
    expect(opts[0]!.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })

  test('two sequential digit+Enter presses ("1"/Enter then "3"/Enter) leave both options checked', async () => {
    const req = makeRequest({
      id: "req-multi-two-toggles",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    pressKey(m.container, "1")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    pressKey(m.container, "3")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    const opts = options(m.container)
    expect(opts[0]!.getAttribute("aria-checked")).toBe("true")
    expect(opts[2]!.getAttribute("aria-checked")).toBe("true")
    // Untouched options remain unchecked.
    expect(opts[1]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[3]!.getAttribute("aria-checked")).toBe("false")

    // Still no auto-submit.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('pressing "1" → Enter → Enter again (with focus still on option 0) toggles the option back off', async () => {
    const req = makeRequest({
      id: "req-multi-toggle-off",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    pressKey(m.container, "1")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    let opts = options(m.container)
    expect(opts[0]!.getAttribute("aria-checked")).toBe("true")

    // Re-highlight option 0 and press Enter again — toggle() should remove it
    // from the answers list, flipping aria-checked back to "false". The second
    // Enter must not auto-submit (the whole point of multi-choice Enter).
    pressKey(m.container, "1")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    opts = options(m.container)
    expect(opts[0]!.getAttribute("aria-checked")).toBe("false")
    // Everything else still unchecked.
    expect(opts[1]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[2]!.getAttribute("aria-checked")).toBe("false")
    expect(opts[3]!.getAttribute("aria-checked")).toBe("false")

    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test("Submit button remains visible throughout digit+Enter interactions on multi-choice", async () => {
    const req = makeRequest({
      id: "req-multi-submit-visible",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    // Visible at mount — primaryButtonVisible() returns true for multi().
    expect(submitButton(m.container)).not.toBeNull()

    pressKey(m.container, "1")
    await flush()
    expect(submitButton(m.container)).not.toBeNull()

    pressKey(m.container, "Enter")
    await flush()
    expect(submitButton(m.container)).not.toBeNull()

    pressKey(m.container, "3")
    await flush()
    expect(submitButton(m.container)).not.toBeNull()

    pressKey(m.container, "Enter")
    await flush()
    expect(submitButton(m.container)).not.toBeNull()

    // Still nothing submitted from digit+Enter flows.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test("clicking Submit after two digit-Enter toggles calls reply exactly once with the 2-option array", async () => {
    const req = makeRequest({
      id: "req-multi-submit-array",
      questions: [
        {
          question: "Multi",
          multiple: true,
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }, { label: "Four" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    // Toggle option 0 on.
    pressKey(m.container, "1")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    // Toggle option 2 on.
    pressKey(m.container, "3")
    await flush()
    pressKey(m.container, "Enter")
    await flush()

    // Precondition: no submission yet.
    expect(replyCalls.length).toBe(0)

    const submit = submitButton(m.container)
    expect(submit).not.toBeNull()
    submit!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.requestID).toBe(req.id)
    // Order: first toggled "One", then toggled "Three" — toggle() appends in
    // click order to the answers list for the current tab.
    expect(replyCalls[0]!.answers).toEqual([["One", "Three"]])

    m.cleanup()
  })
})
