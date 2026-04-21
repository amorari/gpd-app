// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// Tests the digit-key highlight behaviour introduced in
// feat/questionnaire-number-keys (PR follow-up to #1). See
// /tmp/opencode-pr-impl.md for the full behavior matrix.
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
    id: input.id ?? "req-digits-1",
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

function optionsContainer(container: HTMLElement): HTMLElement {
  const el = container.querySelector('[data-slot="question-options"]') as HTMLElement | null
  if (!el) throw new Error("question-options container not found")
  return el
}

// ---------------------------------------------------------------------------
// Tests — digit-key highlight behaviour.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — digit-key highlight", () => {
  test('pressing "1" with 3 options highlights and focuses the first option only', async () => {
    const req = makeRequest({
      id: "req-digit-1",
      questions: [
        {
          question: "Pick",
          options: [{ label: "Alpha" }, { label: "Beta" }, { label: "Gamma" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(3)

    pressKey(m.container, "1")
    await flush()

    expect(opts[0]!.getAttribute("data-highlighted")).toBe("true")
    expect(opts[1]!.getAttribute("data-highlighted")).toBeNull()
    expect(opts[2]!.getAttribute("data-highlighted")).toBeNull()

    // Focus should have moved to the first option.
    expect(document.activeElement).toBe(opts[0])

    // Digit press must not submit.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('pressing "2" then "3" in sequence: only the last-pressed index retains the highlight', async () => {
    const req = makeRequest({
      id: "req-digit-seq",
      questions: [
        {
          question: "Pick",
          options: [{ label: "A" }, { label: "B" }, { label: "C" }, { label: "D" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    pressKey(m.container, "2")
    await flush()

    let opts = options(m.container)
    expect(opts[1]!.getAttribute("data-highlighted")).toBe("true")
    expect(opts[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(opts[2]!.getAttribute("data-highlighted")).toBeNull()

    pressKey(m.container, "3")
    await flush()

    opts = options(m.container)
    expect(opts[2]!.getAttribute("data-highlighted")).toBe("true")
    // Previously highlighted index 1 must have been cleared.
    expect(opts[1]!.getAttribute("data-highlighted")).toBeNull()
    expect(opts[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(opts[3]!.getAttribute("data-highlighted")).toBeNull()

    expect(document.activeElement).toBe(opts[2])
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('pressing "5" with 3 real options (+ custom slot = 4 addressable) is out of range — no highlight, no error', async () => {
    const req = makeRequest({
      id: "req-digit-oor",
      questions: [
        {
          question: "Pick",
          options: [{ label: "A" }, { label: "B" }, { label: "C" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(3)

    // Capture the currently-focused element before the no-op press so we can
    // assert focus did not jump anywhere unexpected.
    const activeBefore = document.activeElement

    expect(() => pressKey(m.container, "5")).not.toThrow()
    await flush()

    for (const o of opts) {
      expect(o.getAttribute("data-highlighted")).toBeNull()
    }
    // Custom slot must also not be highlighted.
    const custom = m.container.querySelector<HTMLButtonElement>(
      '[data-slot="question-option"][data-custom="true"]',
    )
    if (custom) {
      expect(custom.getAttribute("data-highlighted")).toBeNull()
    }

    // Out-of-range digit must not reassign focus.
    expect(document.activeElement).toBe(activeBefore)
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('digit press does NOT call the submit mutation (highlight only — submission requires Enter)', async () => {
    const req = makeRequest({
      id: "req-digit-no-submit",
      questions: [
        {
          question: "Pick",
          options: [{ label: "A" }, { label: "B" }, { label: "C" }],
        },
      ],
    })
    let submittedCount = 0
    const m = renderDock(req, () => submittedCount++)
    await flush()

    pressKey(m.container, "1")
    pressKey(m.container, "2")
    pressKey(m.container, "3")
    await flush()

    expect(replyCalls.length).toBe(0)
    expect(submittedCount).toBe(0)

    // Final highlight is on option 3 (index 2) and nothing else.
    const opts = options(m.container)
    expect(opts[2]!.getAttribute("data-highlighted")).toBe("true")
    expect(opts[0]!.getAttribute("data-highlighted")).toBeNull()
    expect(opts[1]!.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })

  test('options container advertises aria-keyshortcuts="1 2 3 4 5 6 7 8 9 Enter"', async () => {
    const req = makeRequest({
      id: "req-digit-aria-container",
      questions: [
        {
          question: "Pick",
          options: [{ label: "A" }, { label: "B" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const optsContainer = optionsContainer(m.container)
    expect(optsContainer.getAttribute("aria-keyshortcuts")).toBe("1 2 3 4 5 6 7 8 9 Enter")

    m.cleanup()
  })

  test('each option 1–9 has its own aria-keyshortcuts="N" on the button', async () => {
    // Use 9 options to exercise the entire range. Any 10th option would not
    // get a shortcut, but that case is covered by the implementation contract
    // and is not asserted here (no 10+ option scenario in this file).
    const labels = ["O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O9"]
    const req = makeRequest({
      id: "req-digit-aria-buttons",
      questions: [
        {
          question: "Pick",
          options: labels.map((label) => ({ label })),
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(9)

    opts.forEach((btn, i) => {
      expect(btn.getAttribute("aria-keyshortcuts")).toBe(String(i + 1))
    })

    m.cleanup()
  })
})
