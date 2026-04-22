import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import { waitForPaint } from "./bootstrap"

describe("waitForPaint", () => {
  let originalRAF: typeof globalThis.requestAnimationFrame
  let originalDoc: any

  beforeEach(() => {
    originalRAF = globalThis.requestAnimationFrame
    originalDoc = (globalThis as any).document
  })

  afterEach(() => {
    if (originalRAF) {
      globalThis.requestAnimationFrame = originalRAF
    } else {
      // @ts-ignore
      delete globalThis.requestAnimationFrame
    }
    if (originalDoc !== undefined) {
      ;(globalThis as any).document = originalDoc
    } else {
      delete (globalThis as any).document
    }
  })

  test("resolves when requestAnimationFrame fires normally (visible)", async () => {
    let fired = false
    ;(globalThis as any).document = { visibilityState: "visible" }
    globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      setTimeout(() => cb(performance.now()), 1)
      return 1
    }) as any

    await waitForPaint()
    fired = true
    expect(fired).toBe(true)
  })

  test("hidden document → fast-path resolve without waiting for rAF", async () => {
    ;(globalThis as any).document = { visibilityState: "hidden" }
    // Sabotage rAF so it would hang if reached.
    globalThis.requestAnimationFrame = (() => 0) as any

    const start = Date.now()
    await waitForPaint()
    const elapsed = Date.now() - start

    // Should be microtask-fast (< 20ms). If we fell through to the
    // 500ms safety timer, this assertion would fail.
    expect(elapsed).toBeLessThan(100)
  })

  test("500ms safety timer releases bootstrap when rAF never fires", async () => {
    ;(globalThis as any).document = { visibilityState: "visible" }
    globalThis.requestAnimationFrame = (() => 0) as any // never calls back

    const start = Date.now()
    await waitForPaint()
    const elapsed = Date.now() - start

    expect(elapsed).toBeGreaterThanOrEqual(450)
    expect(elapsed).toBeLessThan(750)
  })

  test("SSR / non-browser (no requestAnimationFrame) → microtask resolve", async () => {
    // @ts-ignore
    delete globalThis.requestAnimationFrame
    delete (globalThis as any).document

    const start = Date.now()
    await waitForPaint()
    const elapsed = Date.now() - start

    expect(elapsed).toBeLessThan(50)
  })

  test("bootstrapGlobal ready-gate promise chains correctly", async () => {
    ;(globalThis as any).document = { visibilityState: "visible" }
    globalThis.requestAnimationFrame = ((cb: FrameRequestCallback) => {
      setTimeout(() => cb(performance.now()), 1)
      return 1
    }) as any

    let ran = false
    await waitForPaint().then(() => {
      ran = true
    })
    expect(ran).toBe(true)
  })
})
