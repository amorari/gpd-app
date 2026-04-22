import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { Effect } from "effect"
import fs from "fs/promises"
import path from "path"
import os from "os"

const TEST_XDG = path.join(os.tmpdir(), `gpd-http-abort-${process.pid}-${Date.now()}`)
process.env.XDG_DATA_HOME = TEST_XDG
process.env.XDG_CACHE_HOME = path.join(TEST_XDG, ".cache")
process.env.XDG_CONFIG_HOME = path.join(TEST_XDG, ".config")
process.env.XDG_STATE_HOME = path.join(TEST_XDG, ".state")

// Regression lock for the AbortSignal wiring added in Task 1.5a. Proves:
//   1. `GpdLogHttp.post` threads the signal into the underlying fetch,
//      so an aborted in-flight request rejects promptly instead of
//      hanging to the server's own timeout.
//   2. On AbortError the existing network-catch branch at
//      http-writer.ts:85-89 runs its spill-to-disk path — the drain
//      timeout guarantees events land somewhere (network OR disk).
//   3. `post()` without a signal preserves the prior behavior (no
//      regression on the debounced-flush path).

type GpdLogHttpModule = typeof import("../../src/sink/http-writer")
type GpdLogSpillModule = typeof import("../../src/sink/spill")
let GpdLogHttp: GpdLogHttpModule["GpdLogHttp"]
let GpdLogSpill: GpdLogSpillModule["GpdLogSpill"]

// Mock HTTP server state.
let server: { stop: () => void; url: string; setBehavior: (kind: "ok" | "hang") => void }

function buildMockAuth(apiKey: string) {
  // `GpdLogHttp.post` calls `runGet(auth, GPD_PROVIDER_ID)` which runs
  // `Effect.runPromise(auth.get(providerID).pipe(Effect.orElseSucceed(() => undefined)))`.
  // So `auth.get` must return a real Effect. We don't need the full
  // Auth service — returning a succeeded Effect with the expected
  // shape is enough to exercise the POST code path.
  return {
    get: (_providerID: string) => Effect.succeed({ type: "api", key: apiKey }),
  } as any
}

beforeAll(async () => {
  // Start the mock server FIRST so we know the port, then set
  // OPENCODE_GPD_LOG_URL BEFORE dynamic-importing http-writer.ts —
  // the writer reads the env at module load and snapshots the value.
  let behavior: "ok" | "hang" = "ok"
  const bun = Bun.serve({
    port: 0,
    async fetch(req) {
      if (behavior === "hang") {
        return await new Promise<Response>((_resolve, reject) => {
          req.signal.addEventListener("abort", () => reject(new Error("aborted")))
        })
      }
      return new Response(JSON.stringify({ path: "mock/ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    },
  })
  server = {
    stop: () => bun.stop(),
    url: `http://${bun.hostname}:${bun.port}/gpd/log`,
    setBehavior: (kind) => {
      behavior = kind
    },
  }
  process.env.OPENCODE_GPD_LOG_URL = server.url

  // NOW import (module-load env snapshot picks up our override).
  ;({ GpdLogHttp } = (await import("../../src/sink/http-writer")) as GpdLogHttpModule)
  ;({ GpdLogSpill } = (await import("../../src/sink/spill")) as GpdLogSpillModule)
  void GpdLogSpill // referenced to keep the import; spill artifacts cleaned in afterAll
})

afterAll(async () => {
  server?.stop()
  // Drain any spill entries we wrote so later tests in the same Bun
  // process start clean (Global.Path is module-load snapshot; XDG
  // isolation per file doesn't stop us from sharing the spill dir
  // the first-loaded module picked).
  try {
    const entries = await GpdLogSpill.list()
    await Promise.all(entries.map((e) => GpdLogSpill.remove(e.ulid)))
  } catch {
    // ignore — best-effort cleanup
  }
  await fs.rm(TEST_XDG, { recursive: true, force: true }).catch(() => undefined)
})

describe("GpdLogHttp.post — AbortSignal wiring (Task 1.5a)", () => {
  const baseInput = {
    sessionID: "ses_abort_test" as any,
    rootSessionID: "ses_abort_test" as any,
    events: [
      {
        kind: "message_updated" as const,
        v: 1,
        ts: Date.now(),
        sessionID: "ses_abort_test" as any,
        info: {} as any,
      },
    ],
  } as any

  test("no signal → existing happy path returns ok", async () => {
    server.setBehavior("ok")
    const auth = buildMockAuth("sk-test-ok")
    const outcome = await GpdLogHttp.post(auth, baseInput)
    expect(outcome.kind).toBe("ok")
  })

  test("aborted signal → fetch rejects promptly, outcome is spilled", async () => {
    server.setBehavior("hang")
    const auth = buildMockAuth("sk-test-abort")
    const ctrl = new AbortController()

    // Abort after 50ms so the in-flight fetch resolves via the
    // network-catch path at http-writer.ts:85-89.
    setTimeout(() => ctrl.abort(), 50)

    const start = Date.now()
    const outcome = await GpdLogHttp.post(auth, baseInput, { signal: ctrl.signal })
    const elapsed = Date.now() - start

    expect(outcome.kind).toBe("spilled")
    if (outcome.kind === "spilled") {
      expect(outcome.reason).toBe("network")
    }
    // Must complete well under the server's hang timeout — proves the
    // abort actually short-circuits fetch rather than waiting.
    expect(elapsed).toBeLessThan(1000)
  })

  test("pre-aborted signal → immediate spill, no request latency", async () => {
    server.setBehavior("hang")
    const auth = buildMockAuth("sk-test-pre-abort")
    const ctrl = new AbortController()
    ctrl.abort()

    const start = Date.now()
    const outcome = await GpdLogHttp.post(auth, baseInput, { signal: ctrl.signal })
    const elapsed = Date.now() - start

    expect(outcome.kind).toBe("spilled")
    expect(elapsed).toBeLessThan(500)
  })
})
