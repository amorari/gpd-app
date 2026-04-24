// Regression test for the Node-side auth.json concurrent-writer fix
// (proper-lockfile around Auth.set / Auth.remove). Before the lock:
//   1. Process A reads {}                     ─┐ overlapping
//   2. Process B reads {}                      │ reads then
//   3. A writes {provider0: ...}               │ last-writer-wins
//   4. B writes {provider1: ...}              ─┘ A's write lost
// After: step 2 blocks until step 3 completes, so B reads {provider0}
// before writing {provider0, provider1}. Final file has both.
//
// Setup: drive Auth.set from 16 worker processes in parallel, each
// writing a distinct provider key to a throwaway auth.json. Assert all
// 16 keys are present in the final file. Pre-lock, roughly N/2 keys
// would be missing (last-writer-wins narrows the window to milliseconds
// but doesn't eliminate it).
//
// The test spawns `bun` child processes rather than threads because
// proper-lockfile is a cross-PROCESS lock; a single-process many-fiber
// test wouldn't exercise the actual race.

import { describe, expect, test, afterAll, beforeAll } from "bun:test"
import { spawn } from "node:child_process"
import fs from "node:fs/promises"
import os from "node:os"
import path from "node:path"

// Worker script lives alongside this test (auth-concurrent-worker.ts)
// so node_modules resolve normally. Env-driven XDG_DATA_HOME overrides
// Global.Path.data to the throwaway dir.

describe("Auth.set — cross-process race", () => {
  let tmpDataDir: string
  let workerPath: string

  beforeAll(async () => {
    tmpDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "auth-race-"))
    await fs.mkdir(path.join(tmpDataDir, "opencode"), { recursive: true })
    // Worker lives in the package tree so node_modules resolve.
    workerPath = path.resolve(__dirname, "auth-concurrent-worker.ts")
  })

  afterAll(async () => {
    await fs.rm(tmpDataDir, { recursive: true, force: true }).catch(() => undefined)
  })

  test("16 concurrent writers — every key lands", async () => {
    const N = 16
    const children: Promise<void>[] = []
    for (let i = 0; i < N; i++) {
      children.push(
        new Promise<void>((resolve, reject) => {
          const proc = spawn(
            "bun",
            ["run", workerPath, `provider${i}`, tmpDataDir],
            { stdio: ["ignore", "pipe", "pipe"], cwd: process.cwd() },
          )
          let stderr = ""
          proc.stderr?.on("data", (c) => (stderr += c.toString()))
          proc.on("exit", (code) => {
            if (code === 0) resolve()
            else reject(new Error(`worker ${i} exit ${code}: ${stderr}`))
          })
        }),
      )
      // Tiny jitter so workers don't all fire at exact same instant —
      // gives the race a chance to trigger pre-lock.
      await new Promise((r) => setTimeout(r, Math.random() * 5))
    }

    await Promise.all(children)

    // The lock-holder semantic: every call to Auth.set serialises the
    // read-modify-write, so the final file must contain all 16 keys.
    const authPath = path.join(tmpDataDir, "opencode", "auth.json")
    const raw = await fs.readFile(authPath, "utf8")
    const parsed = JSON.parse(raw)
    const keys = Object.keys(parsed).filter((k) => k.startsWith("provider"))
    expect(keys.length).toBe(N)
    for (let i = 0; i < N; i++) {
      expect(keys).toContain(`provider${i}`)
    }
  }, 30_000)
})
