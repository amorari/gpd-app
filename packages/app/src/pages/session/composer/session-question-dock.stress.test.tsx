// Stress / edge-case tests for SessionQuestionDock.
// Mirrors the mock patterns in session-question-dock.test.tsx.
import { beforeAll, beforeEach, afterEach, describe, expect, mock, test } from "bun:test"
import type { Component } from "solid-js"
import type { QuestionRequest } from "@opencode-ai/sdk/v2"

// ---------------------------------------------------------------------------
// Mocks (installed before component imports resolve).
// ---------------------------------------------------------------------------

type ReplyCall = { requestID: string; answers: string[][] }
const replyCalls: ReplyCall[] = []
const rejectCalls: string[] = []
const toastCalls: unknown[] = []

let pendingReply: { resolve: (v: boolean) => void; reject: (err: unknown) => void } | null = null
let replyMode: "resolved" | "pending" = "resolved"

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
  replyMode = "resolved"
})

// ---------------------------------------------------------------------------
// Helpers
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
    id: input.id ?? "req-stress",
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

// ---------------------------------------------------------------------------
// Unhandled-rejection / error capture utilities for test 3.
// ---------------------------------------------------------------------------

type Captured = {
  unhandled: unknown[]
  errors: unknown[]
  restore: () => void
}

function captureErrors(): Captured {
  const unhandled: unknown[] = []
  const errors: unknown[] = []

  const origConsoleError = console.error
  console.error = (...args: unknown[]) => {
    errors.push(args)
  }

  const onUnhandled = (ev: Event) => {
    // PromiseRejectionEvent in browsers / happy-dom; Bun also fires
    // "unhandledRejection" on process. We attach both.
    const anyEv = ev as unknown as { reason?: unknown }
    unhandled.push(anyEv.reason ?? ev)
  }
  const onProcess = (reason: unknown) => {
    unhandled.push(reason)
  }

  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("unhandledrejection", onUnhandled as EventListener)
  }
  if (typeof process !== "undefined" && typeof process.on === "function") {
    process.on("unhandledRejection", onProcess)
  }

  return {
    unhandled,
    errors,
    restore: () => {
      console.error = origConsoleError
      if (typeof window !== "undefined" && typeof window.removeEventListener === "function") {
        window.removeEventListener("unhandledrejection", onUnhandled as EventListener)
      }
      if (typeof process !== "undefined" && typeof process.off === "function") {
        process.off("unhandledRejection", onProcess)
      }
    },
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SessionQuestionDock — stress / edge cases", () => {
  test("rapid-fire clicks during pending mutation: 10x sync click yields exactly one reply", async () => {
    replyMode = "pending"
    const req = makeRequest({
      id: "req-rapid-10",
      questions: [{ options: [{ label: "OnlyChoice" }] }],
    })
    let onSubmitCount = 0
    const m = mount(req, () => onSubmitCount++)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(1)

    // Fire 10 synchronous clicks on the same single-choice option.
    for (let i = 0; i < 10; i++) opts[0]!.click()

    await flush()

    // The sending() guard + disabled attr must coalesce these to a single
    // network call.
    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["OnlyChoice"]])
    expect(replyCalls[0]!.requestID).toBe(req.id)
    // onMutate fires optimistically exactly once.
    expect(onSubmitCount).toBe(1)

    // Resolve the in-flight mutation for clean teardown.
    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })

  test("keyboard spam: 5 Enter keydowns in one microtask → exactly one reply; focus remains sane", async () => {
    replyMode = "pending"
    const req = makeRequest({
      id: "req-kb-spam",
      questions: [
        {
          question: "Last",
          options: [{ label: "Pick" }, { label: "Other" }],
        },
      ],
    })
    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(2)

    // Focus an option and dispatch 5 Enter keydowns synchronously.
    // happy-dom maps Enter on <button> → click, so this drives the
    // same code path a real browser would.
    opts[0]!.focus()
    expect(document.activeElement).toBe(opts[0])

    for (let i = 0; i < 5; i++) {
      opts[0]!.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
      )
      // Also simulate the resulting click that real browsers fire —
      // this is what happy-dom does for <button> + Enter. We call it
      // explicitly to guarantee the activation path is exercised even
      // if the synthetic keydown doesn't emit a click in this env.
      opts[0]!.click()
    }

    await flush()

    // Exactly one reply despite 5 activations.
    expect(replyCalls.length).toBe(1)
    expect(replyCalls[0]!.answers).toEqual([["Pick"]])

    // Focus state post-submit is sane: focus is either still on the picked
    // option (now disabled) or moved to a valid element inside the doc.
    // It must not be null / detached.
    const active = document.activeElement
    expect(active).not.toBeNull()
    // activeElement should belong to this document (not garbage-collected).
    expect(active?.ownerDocument).toBe(document)

    // All option buttons must be disabled while the mutation is pending.
    for (const o of options(m.container)) {
      expect(o.disabled).toBe(true)
    }

    pendingReply?.resolve(true)
    await flush()

    m.cleanup()
  })

  test("unmount during pending mutation: no unhandled rejection, no console errors, mutation resolves cleanly", async () => {
    replyMode = "pending"
    const req = makeRequest({
      id: "req-unmount",
      questions: [{ options: [{ label: "Go" }] }],
    })
    const cap = captureErrors()

    const m = mount(req)
    await flush()

    const opts = options(m.container)
    expect(opts.length).toBe(1)

    // Start the mutation.
    opts[0]!.click()
    await flush()

    // Mutation must be in-flight.
    expect(replyCalls.length).toBe(1)
    expect(pendingReply).not.toBeNull()

    // Simulate parent unmount mid-flight.
    m.cleanup()
    await flush()

    // Now resolve the pending promise. If the component mishandled
    // teardown this could trigger DOM access errors or stale-state writes.
    pendingReply?.resolve(true)

    // Give solid-query a few ticks to run onSuccess / cache.delete.
    for (let i = 0; i < 6; i++) {
      await Promise.resolve()
      await new Promise<void>((r) => setTimeout(r, 0))
    }

    cap.restore()

    // No unhandled rejections.
    expect(cap.unhandled.length).toBe(0)
    // No console errors from the component / solid-query during unmount.
    // (solid-query may log internally on error, but success should be silent.)
    if (cap.errors.length > 0) {
      // Surface what was logged so the failure message is actionable.
      // eslint-disable-next-line no-console
      console.log("captured console.error during unmount:", cap.errors)
    }
    expect(cap.errors.length).toBe(0)
  })
})
