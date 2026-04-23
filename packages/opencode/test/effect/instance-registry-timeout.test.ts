import { expect, test } from "bun:test"
import { disposeInstance, registerDisposer } from "../../src/effect/instance-registry"

// Regression: 1.1.12 Change-API-Key hang. A single disposer that never
// resolved wedged Promise.allSettled in disposeInstance forever, which
// blocked Instance.disposeAll, which blocked POST /global/dispose, which
// blocked the frontend await that guarded localStorage cleanup + reload.
// Every disposer must be bounded so one slow disposer cannot starve the
// others or the surrounding disposeAll call.
test("disposeInstance returns within ~10s when a disposer never resolves", async () => {
  const off = registerDisposer(() => new Promise(() => {}))
  const started = Date.now()
  try {
    await disposeInstance("/tmp/never-resolves")
  } finally {
    off()
  }
  const elapsed = Date.now() - started
  // 10s ceiling + a generous margin for CI scheduling jitter.
  expect(elapsed).toBeLessThan(11_500)
  // And definitely not instant — the timeout should have fired.
  expect(elapsed).toBeGreaterThan(9_500)
}, 15_000)

test("disposeInstance still runs fast-path disposers when another hangs", async () => {
  let ranFast = false
  const offFast = registerDisposer(async () => {
    ranFast = true
  })
  const offSlow = registerDisposer(() => new Promise(() => {}))
  try {
    await disposeInstance("/tmp/mixed")
  } finally {
    offFast()
    offSlow()
  }
  expect(ranFast).toBe(true)
}, 15_000)
