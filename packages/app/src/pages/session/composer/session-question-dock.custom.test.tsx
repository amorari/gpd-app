// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
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
// Test helpers (same shape as session-question-dock.test.tsx).
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
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await new Promise<void>((r) => requestAnimationFrame(() => r()))
  }
  // textarea focusCustom uses setTimeout(..., 0)
  await new Promise<void>((r) => setTimeout(r, 5))
  await Promise.resolve()
}

function presetOptions(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    container.querySelectorAll<HTMLButtonElement>('[data-slot="question-option"]:not([data-custom="true"])'),
  )
}

function customButton(container: HTMLElement): HTMLButtonElement | null {
  return container.querySelector<HTMLButtonElement>('button[data-slot="question-option"][data-custom="true"]')
}

function customTextarea(container: HTMLElement): HTMLTextAreaElement | null {
  return container.querySelector<HTMLTextAreaElement>('[data-slot="question-custom-input"]')
}

function submitButton(container: HTMLElement): HTMLButtonElement | null {
  const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
  return buttons.find((b) => b.textContent?.trim() === "ui.common.submit") ?? null
}

// ---------------------------------------------------------------------------
// Tests — custom free-text edge cases on a single-choice question.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — custom free-text (single-choice)", () => {
  test("clicking the custom 'Type your own answer' button does NOT auto-submit and keeps dock open", async () => {
    const req = makeRequest({
      id: "req-custom-open",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    // Initially: single-choice single-question has NO primary button.
    expect(submitButton(m.container)).toBeNull()

    const custom = customButton(m.container)
    expect(custom).not.toBeNull()

    custom!.click()
    await flush()

    // Must NOT have replied.
    expect(replyCalls.length).toBe(0)
    expect(submitted).toBe(0)

    // Dock is still in the DOM.
    expect(m.container.querySelector('[data-component="dock-prompt"]')).not.toBeNull()

    // Primary Submit button becomes visible because custom free-text is active.
    expect(submitButton(m.container)).not.toBeNull()

    // The textarea should now be rendered (editing mode).
    expect(customTextarea(m.container)).not.toBeNull()

    m.cleanup()
  })

  test("typing custom text + Enter commits (does NOT submit); Submit button then submits with custom answer", async () => {
    const req = makeRequest({
      id: "req-custom-enter",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    const m = mount(req)
    await flush()

    // Open the custom textarea.
    customButton(m.container)!.click()
    await flush()

    const ta = customTextarea(m.container)
    expect(ta).not.toBeNull()

    // Type text via an input event (mirrors how the onInput handler fires).
    ta!.value = "my free-form answer"
    ta!.dispatchEvent(new Event("input", { bubbles: true }))
    await flush()

    // Press Enter (no shift, no meta) — commits, does NOT submit.
    ta!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      }),
    )
    await flush()

    // No reply yet — commit should not submit.
    expect(replyCalls.length).toBe(0)

    // After commit, the textarea is gone and the custom button is back (data-picked=true).
    expect(customTextarea(m.container)).toBeNull()
    const customAfter = customButton(m.container)
    expect(customAfter).not.toBeNull()
    expect(customAfter!.getAttribute("data-picked")).toBe("true")

    // Submit button is visible because on() is true.
    const submit = submitButton(m.container)
    expect(submit).not.toBeNull()

    // Click Submit — now we reply with the custom text as the answer.
    submit!.click()
    await flush()

    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.requestID).toBe(req.id)
    expect(replyCalls[0]!.answers).toEqual([["my free-form answer"]])

    m.cleanup()
  })

  test("canceling custom by clicking a preset option clears customOn and re-enables auto-submit on the preset pick", async () => {
    const req = makeRequest({
      id: "req-custom-cancel",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    // Open custom, type something, commit.
    customButton(m.container)!.click()
    await flush()

    const ta = customTextarea(m.container)!
    ta.value = "something custom"
    ta.dispatchEvent(new Event("input", { bubbles: true }))
    await flush()

    ta.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
    )
    await flush()

    // Sanity: custom is picked, submit button present, no reply yet.
    expect(customButton(m.container)!.getAttribute("data-picked")).toBe("true")
    expect(submitButton(m.container)).not.toBeNull()
    expect(replyCalls.length).toBe(0)

    // Now click a preset option — pick() sets customOn=false and auto-progresses
    // (single-choice, last question → submit).
    const presets = presetOptions(m.container)
    expect(presets.length).toBe(2)
    presets[0]!.click()
    await flush()

    // Reply happened with the PRESET label, not the custom text.
    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Yes"]])
    // onMutate fires onSubmit optimistically.
    expect(submitted).toBe(1)

    m.cleanup()
  })
})
