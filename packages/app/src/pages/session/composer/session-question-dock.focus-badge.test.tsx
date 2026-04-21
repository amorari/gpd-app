// Run with the test:unit script or equivalent; see packages/app/package.json.
// Requires the solid-preload.ts Bun plugin (wired into the test scripts) to
// compile Solid JSX via babel-preset-solid at load time.
//
// Tests the digit badge rendering + focus-navigation clearing behaviour
// introduced in feat/questionnaire-number-keys. See /tmp/opencode-pr-impl.md
// (behavior matrix) for the full contract — specifically:
//   * Each addressable option (index 0-8) renders a `.opt-num` span badge.
//   * Badges are `aria-hidden="true"` so screen readers don't double-announce.
//   * Custom "type your own answer" slot gets a badge iff options().length < 9.
//   * Arrow / Home / End / Tab after a digit press clears `store.highlighted`
//     and removes the `data-highlighted` attribute from all options.
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
    id: input.id ?? "req-focus-1",
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

function customOption(container: HTMLElement): HTMLButtonElement | null {
  return container.querySelector<HTMLButtonElement>(
    '[data-slot="question-option"][data-custom="true"]',
  )
}

function dockRoot(container: HTMLElement): HTMLElement {
  const dock = container.querySelector('[data-component="dock-prompt"]') as HTMLElement | null
  if (!dock) throw new Error("dock-prompt root not found in container")
  return dock
}

function pressKey(container: HTMLElement, key: string) {
  const active = document.activeElement
  const target =
    active instanceof HTMLElement && container.contains(active) ? active : dockRoot(container)
  target.dispatchEvent(
    new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
    }),
  )
}

// Returns the `.opt-num` badge span inside the given option button, or null.
function badgeInside(btn: HTMLElement): HTMLElement | null {
  return btn.querySelector<HTMLElement>('[data-slot="question-option-num"]')
}

// ---------------------------------------------------------------------------
// Tests — digit badge rendering + focus-nav highlight clearing.
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — digit badge rendering + focus-nav clearing", () => {
  test("3 options each render a .opt-num span with text '1', '2', '3' in order", async () => {
    const req = makeRequest({
      id: "req-badge-three",
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

    opts.forEach((btn, i) => {
      const badge = badgeInside(btn)
      expect(badge).not.toBeNull()
      expect(badge!.classList.contains("opt-num")).toBe(true)
      expect(badge!.textContent?.trim()).toBe(String(i + 1))
    })

    m.cleanup()
  })

  test("badges are aria-hidden='true' so screen readers do not double-announce", async () => {
    const req = makeRequest({
      id: "req-badge-aria",
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

    for (const btn of opts) {
      const badge = badgeInside(btn)
      expect(badge).not.toBeNull()
      expect(badge!.getAttribute("aria-hidden")).toBe("true")
    }

    m.cleanup()
  })

  test("custom slot renders a badge showing '4' when options().length = 3 (< 9)", async () => {
    // `custom: true` renders the "type your own answer" slot alongside the 3
    // real options. Per contract, that slot gets digit `options().length + 1`
    // (= 4 here) as its badge because options().length < 9.
    const req = makeRequest({
      id: "req-badge-custom",
      questions: [
        {
          question: "Pick",
          custom: true,
          options: [{ label: "A" }, { label: "B" }, { label: "C" }],
        },
      ],
    })
    const m = renderDock(req)
    await flush()

    const custom = customOption(m.container)
    expect(custom).not.toBeNull()

    const badge = badgeInside(custom!)
    expect(badge).not.toBeNull()
    expect(badge!.classList.contains("opt-num")).toBe(true)
    expect(badge!.getAttribute("aria-hidden")).toBe("true")
    expect(badge!.textContent?.trim()).toBe("4")

    m.cleanup()
  })

  test("ArrowDown after pressing '2' clears store.highlighted — no option has data-highlighted", async () => {
    const req = makeRequest({
      id: "req-arrow-clear",
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

    // Precondition: option index 1 is highlighted.
    let opts = options(m.container)
    expect(opts[1]!.getAttribute("data-highlighted")).toBe("true")

    pressKey(m.container, "ArrowDown")
    await flush()

    opts = options(m.container)
    for (const btn of opts) {
      expect(btn.getAttribute("data-highlighted")).toBeNull()
    }
    // Custom slot (if any) must also not carry the attribute.
    const custom = customOption(m.container)
    if (custom) expect(custom.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })

  test("Home after pressing '2' clears highlight and focuses the first option", async () => {
    const req = makeRequest({
      id: "req-home-clear",
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

    pressKey(m.container, "Home")
    await flush()

    opts = options(m.container)
    for (const btn of opts) {
      expect(btn.getAttribute("data-highlighted")).toBeNull()
    }

    // Focus lands on option 0.
    expect(document.activeElement).toBe(opts[0])

    m.cleanup()
  })

  test("End after pressing '2' clears highlight and focuses the last addressable option", async () => {
    const req = makeRequest({
      id: "req-end-clear",
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

    pressKey(m.container, "End")
    await flush()

    opts = options(m.container)
    for (const btn of opts) {
      expect(btn.getAttribute("data-highlighted")).toBeNull()
    }

    // End should land focus on the last addressable option. With no custom
    // slot present, that's the last real option (index 3). With a custom slot,
    // nav may land on it instead — accept either, but it must not be null and
    // must belong to this dock.
    const active = document.activeElement as HTMLElement | null
    expect(active).not.toBeNull()
    const custom = customOption(m.container)
    const candidates: Array<Element | null> = [opts[opts.length - 1]!, custom]
    expect(candidates.some((c) => c === active)).toBe(true)

    m.cleanup()
  })

  test("Tab after pressing '2' clears data-highlighted (Tab clears highlight without preventDefault)", async () => {
    const req = makeRequest({
      id: "req-tab-clear",
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

    // Dispatch Tab directly on the dock root so we can inspect the event's
    // defaultPrevented flag after the handler runs. Per contract, Tab must
    // clear the highlight but must NOT call preventDefault — native browser
    // focus traversal should still occur.
    const ev = new KeyboardEvent("keydown", {
      key: "Tab",
      bubbles: true,
      cancelable: true,
    })
    dockRoot(m.container).dispatchEvent(ev)
    await flush()

    expect(ev.defaultPrevented).toBe(false)

    opts = options(m.container)
    for (const btn of opts) {
      expect(btn.getAttribute("data-highlighted")).toBeNull()
    }
    const custom = customOption(m.container)
    if (custom) expect(custom.getAttribute("data-highlighted")).toBeNull()

    m.cleanup()
  })
})
