import { afterAll, describe, expect, test } from "bun:test"
import fs from "fs/promises"
import path from "path"
import os from "os"
import { GpdLog } from "../../src/sink/schema"

// Set XDG_DATA_HOME *before* importing anything that resolves Global.Path.
// Global/index.ts snapshots xdgData at module load (top-level await), so any
// later override is ignored. Pin a deterministic sandbox.
const TEST_XDG = path.join(os.tmpdir(), `gpd-sink-${process.pid}-${Date.now()}`)
process.env.XDG_DATA_HOME = TEST_XDG
process.env.XDG_CACHE_HOME = path.join(TEST_XDG, ".cache")
process.env.XDG_CONFIG_HOME = path.join(TEST_XDG, ".config")
process.env.XDG_STATE_HOME = path.join(TEST_XDG, ".state")

const { GpdLogWriter } = await import("../../src/sink/jsonl-writer")

describe("GpdLogWriter (local JSONL)", () => {
  afterAll(async () => {
    await fs.rm(TEST_XDG, { recursive: true, force: true }).catch(() => undefined)
  })

  test("routes events, spills >32KB tool outputs, writes index", async () => {

    const root = "sess-root-01"
    const sub = "sess-sub-02"
    const big = "x".repeat(40 * 1024)

    const events: GpdLog.Event[] = [
      {
        kind: "session_init",
        v: GpdLog.SCHEMA_VERSION,
        ts: 1,
        sessionID: root,
        parentSessionID: null,
        rootSessionID: root,
        info: { id: root } as never,
      },
      {
        kind: "part_updated",
        v: GpdLog.SCHEMA_VERSION,
        ts: 2,
        sessionID: root,
        part: {
          type: "tool",
          id: "p1",
          messageID: "m1",
          sessionID: root,
          state: { status: "completed", output: big, title: "t", metadata: {}, input: {}, time: { start: 0, end: 1 } },
          tool: "bash",
          callID: "c1",
        } as never,
      },
      {
        kind: "message_updated",
        v: GpdLog.SCHEMA_VERSION,
        ts: 3,
        sessionID: sub,
        info: { id: "m2", sessionID: sub } as never,
      },
    ]

    await GpdLogWriter.append(root, events)

    const base = GpdLogWriter.baseDir()
    const rootFile = path.join(base, root, "root.jsonl")
    const subFile = path.join(base, root, "subagents", `agent-${sub}.jsonl`)
    const spillDir = path.join(base, root, "tool-results")

    const rootTxt = await fs.readFile(rootFile, "utf8")
    const rootLines = rootTxt.trim().split("\n")
    expect(rootLines.length).toBe(2)
    expect(JSON.parse(rootLines[0]!).kind).toBe("session_init")
    const spilled = JSON.parse(rootLines[1]!)
    expect(spilled.kind).toBe("part_updated")
    expect(spilled.spilledBlobSha).toMatch(/^[0-9a-f]{64}$/)
    expect(spilled.part.state.output).toContain("__spilled__:")
    expect(spilled.part.state.output.length).toBeLessThan(2000) // placeholder, not the 40KB

    const subTxt = await fs.readFile(subFile, "utf8")
    expect(subTxt.trim().split("\n").length).toBe(1)
    expect(JSON.parse(subTxt.trim()).kind).toBe("message_updated")

    const spilledFiles = await fs.readdir(spillDir)
    expect(spilledFiles.length).toBe(1)
    const spilledContent = await fs.readFile(path.join(spillDir, spilledFiles[0]!), "utf8")
    expect(spilledContent).toBe(big)

    // Append semantics: subsequent call extends root.jsonl.
    await GpdLogWriter.append(root, [
      {
        kind: "session_close",
        v: GpdLog.SCHEMA_VERSION,
        ts: 4,
        sessionID: root,
        reason: "flush",
      },
    ])
    const rootTxt2 = await fs.readFile(rootFile, "utf8")
    expect(rootTxt2.trim().split("\n").length).toBe(3)
    expect(JSON.parse(rootTxt2.trim().split("\n").at(-1)!).kind).toBe("session_close")

    await GpdLogWriter.writeIndex(root, {
      rootSessionID: root,
      subagentSessionIDs: [sub],
      createdAt: 1,
      closedAt: 4,
      reason: "flush",
    })
    const idx = JSON.parse(await fs.readFile(path.join(base, root, "index.json"), "utf8"))
    expect(idx.subagentSessionIDs).toEqual([sub])
  })
})
