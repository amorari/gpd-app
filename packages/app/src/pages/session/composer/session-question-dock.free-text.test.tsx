// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// Tests the interaction between the digit-key highlight behaviour and the
// "Type your own answer" (custom free-text) slot. In particular: while the
// textarea is focused (store.editing = true), nav() must short-circuit at
// L376 BEFORE entering the digit branch — see /tmp/opencode-pr-impl.md.
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
// Test helpers (same shape as session-question-dock.test.tsx +
// session-question-dock.custom.test.tsx).
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

// Flush microtasks + a few animation frames. Custom textarea open path uses
// setTimeout(0) inside focusCustom(), so add a macrotask wait too.
async function flush() {
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await new Promise<void>((r) => requestAnimationFrame(() => r()))
  }
  await new Promise<void>((r) => setTimeout(r, 5))
  await Promise.resolve()
}

function options(container: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    container.querySelectorAll<HTMLButtonElement>(
      '[data-slot="question-option"]:not([data-custom="true"])',
    ),
  )
}

function customButton(container: HTMLElement): HTMLButtonElement | null {
  return container.querySelector<HTMLButtonElement>(
    'button[data-slot="question-option"][data-custom="true"]',
  )
}

function customTextarea(container: HTMLElement): HTMLTextAreaElement | null {
  return container.querySelector<HTMLTextAreaElement>('[data-slot="question-custom-input"]')
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

// Dispatch a KeyboardEvent from a specific element. Used when we need the
// event to originate inside the textarea (so `event.target` is the textarea
// and `store.editing` is true when nav() reads it).
function pressKeyOn(el: EventTarget, key: string, init: KeyboardEventInit = {}) {
  el.dispatchEvent(
    new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
      ...init,
    }),
  )
}

// ---------------------------------------------------------------------------
// Tests — free-text textarea vs. digit-key highlight path.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — free-text textarea interaction with digit keys", () => {
  test('digit typed into focused textarea flows into the value verbatim; no option gets data-highlighted', async () => {
    const req = makeRequest({
      id: "req-free-text-digit",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    const m = mount(req)
    await flush()

    // Open the textarea by clicking the custom slot.
    customButton(m.container)!.click()
    await flush()

    const ta = customTextarea(m.container)
    expect(ta).not.toBeNull()

    // Press "1" on the textarea — should flow into textarea value, NOT
    // highlight an option (nav() short-circuits on store.editing at L376).
    // happy-dom does not auto-insert characters for KeyboardEvent, so we
    // simulate typing by dispatching the keydown AND setting the value +
    // firing an input event, mirroring a real browser's effect.
    pressKeyOn(ta!, "1")
    ta!.value = "1"
    ta!.dispatchEvent(new Event("input", { bubbles: true }))
    await flush()

    // No option should be highlighted.
    const opts = options(m.container)
    for (const o of opts) {
      expect(o.getAttribute("data-highlighted")).toBeNull()
    }
    // Custom button is not in the DOM right now (textarea is rendered in
    // its place), but if the nav() digit branch had fired incorrectly we'd
    // see a second-tab jump or a data-highlighted attr on a preset option.
    expect(customButton(m.container)).toBeNull()

    // Textarea value reflects what was typed.
    expect(ta!.value).toBe("1")

    // Digit press inside the textarea must not submit.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test("digit key on focused textarea does NOT trigger submit or highlight", async () => {
    const req = makeRequest({
      id: "req-free-text-no-submit",
      questions: [
        {
          question: "Q",
          options: [{ label: "One" }, { label: "Two" }, { label: "Three" }],
        },
      ],
    })
    let submitted = 0
    const m = mount(req, () => submitted++)
    await flush()

    customButton(m.container)!.click()
    await flush()

    const ta = customTextarea(m.container)
    expect(ta).not.toBeNull()

    // Press "2" while textarea is focused/editing.
    pressKeyOn(ta!, "2")
    await flush()

    // Mutation must NOT have fired (nav short-circuited, no pick/next).
    expect(replyCalls.length).toBe(0)
    expect(submitted).toBe(0)

    // No preset option has the digit highlight.
    const opts = options(m.container)
    for (const o of opts) {
      expect(o.getAttribute("data-highlighted")).toBeNull()
    }

    // Still editing — textarea is still in the DOM.
    expect(customTextarea(m.container)).not.toBeNull()

    m.cleanup()
  })

  test("Enter inside textarea runs the textarea's own commit path, NOT the dock's digit-commit Enter path", async () => {
    const req = makeRequest({
      id: "req-free-text-enter",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    const m = mount(req)
    await flush()

    customButton(m.container)!.click()
    await flush()

    const ta = customTextarea(m.container)
    expect(ta).not.toBeNull()

    // Type some text.
    ta!.value = "free form"
    ta!.dispatchEvent(new Event("input", { bubbles: true }))
    await flush()

    // Press Enter from inside the textarea. The textarea's own onKeyDown
    // handler calls commitCustom(); nav() sees store.editing=true and
    // bails at L376 before reaching the Enter digit-commit branch at L412.
    // Observable: commit closes the textarea and reveals the custom button
    // with data-picked="true". If the dock's Enter branch had instead
    // fired it would route through selectOption() against whatever was
    // highlighted — but store.highlighted is -1, so there would be no
    // commit at all, and the textarea would remain open.
    pressKeyOn(ta!, "Enter")
    await flush()

    // After commit: textarea gone, custom button back with data-picked.
    expect(customTextarea(m.container)).toBeNull()
    const custom = customButton(m.container)
    expect(custom).not.toBeNull()
    expect(custom!.getAttribute("data-picked")).toBe("true")

    // Enter on the textarea must NOT submit (commit only).
    expect(replyCalls.length).toBe(0)

    // And none of the preset options should be highlighted (nav digit path
    // never ran because store.editing was true at the time of keydown).
    for (const o of options(m.container)) {
      expect(o.getAttribute("data-highlighted")).toBeNull()
    }

    m.cleanup()
  })

  test("clicking the custom 'Type your own answer' slot opens the textarea and flips store.editing (observable via primary button visibility)", async () => {
    const req = makeRequest({
      id: "req-free-text-click-open",
      questions: [{ options: [{ label: "Yes" }, { label: "No" }] }],
    })
    const m = mount(req)
    await flush()

    // Pre-click: single-choice single-question has NO primary button
    // (primaryButtonVisible is false).
    expect(submitButton(m.container)).toBeNull()
    expect(customTextarea(m.container)).toBeNull()

    // Click the custom button (which renders at options().length).
    const custom = customButton(m.container)
    expect(custom).not.toBeNull()
    custom!.click()
    await flush()

    // store.editing flipped to true: observable because primaryButtonVisible
    // now returns true (editing short-circuit in the memo), exposing Submit.
    expect(submitButton(m.container)).not.toBeNull()

    // Textarea is rendered and is the focused element.
    const ta = customTextarea(m.container)
    expect(ta).not.toBeNull()
    expect(document.activeElement).toBe(ta)

    // No reply happened from the click (custom open never auto-submits).
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })

  test('digit = custom slot index + 1 (when options.length < 9) highlights the custom slot; Enter then opens the textarea via customOpen()', async () => {
    // 3 preset options → custom slot is at index 3 → digit "4" should target it.
    const req = makeRequest({
      id: "req-free-text-digit-custom",
      questions: [
        {
          question: "Q",
          options: [{ label: "Alpha" }, { label: "Beta" }, { label: "Gamma" }],
        },
      ],
    })
    const m = mount(req)
    await flush()

    // Dispatch from the dock root (not from textarea — it doesn't exist yet).
    // Event target is the dock; nav() runs; store.editing=false so we reach
    // the digit branch.
    pressKeyOn(dockRoot(m.container), "4")
    await flush()

    // Custom button should now carry data-highlighted="true".
    const customBefore = customButton(m.container)
    expect(customBefore).not.toBeNull()
    expect(customBefore!.getAttribute("data-highlighted")).toBe("true")

    // No preset option should be highlighted.
    for (const o of options(m.container)) {
      expect(o.getAttribute("data-highlighted")).toBeNull()
    }

    // Focus is on the custom button (highlightOption moves focus).
    expect(document.activeElement).toBe(customBefore)

    // No reply yet — digit highlight is not a commit.
    expect(replyCalls.length).toBe(0)

    // Now press Enter. The Enter nav branch requires store.focus ===
    // store.highlighted (both are `options().length`, i.e. 3) and calls
    // selectOption(3), which routes to customOpen() because
    // optIndex === options().length.
    pressKeyOn(dockRoot(m.container), "Enter")
    await flush()

    // Textarea is now open (customOpen flipped editing=true).
    expect(customTextarea(m.container)).not.toBeNull()

    // Primary button is now visible (editing=true drives primaryButtonVisible).
    expect(submitButton(m.container)).not.toBeNull()

    // Still no reply — opening the textarea is not a submit.
    expect(replyCalls.length).toBe(0)

    m.cleanup()
  })
})
