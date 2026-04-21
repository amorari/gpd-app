import { afterAll, describe, expect, test } from "bun:test"
import fs from "fs/promises"
import path from "path"
import os from "os"

const TEST_XDG = path.join(os.tmpdir(), `gpd-spill-${process.pid}-${Date.now()}`)
process.env.XDG_DATA_HOME = TEST_XDG
process.env.XDG_CACHE_HOME = path.join(TEST_XDG, ".cache")
process.env.XDG_CONFIG_HOME = path.join(TEST_XDG, ".config")
process.env.XDG_STATE_HOME = path.join(TEST_XDG, ".state")

// Type-only import works statically; runtime import has to be dynamic
// because the XDG_* overrides above must win over the module-load-time
// snapshot in src/global.ts (top-level await).
import type { GpdLogSpill as GpdLogSpillType } from "../../src/sink/spill"
const { GpdLogSpill } = (await import("../../src/sink/spill")) as {
  GpdLogSpill: typeof GpdLogSpillType
}

describe("GpdLogSpill", () => {
  afterAll(async () => {
    await fs.rm(TEST_XDG, { recursive: true, force: true }).catch(() => undefined)
  })

  test("atomic write + list + remove round trip", async () => {
    const meta: GpdLogSpillType.Meta = {
      sessionID: "sess-1",
      rootSessionID: "sess-1",
      seq: "01HABCDEFGHJKMNPQRSTVWXYZ1",
      contentLength: 42,
      createdAt: 1234,
    }
    const body = new Uint8Array([1, 2, 3, 4])

    await GpdLogSpill.write(meta.seq, meta, body)

    const entries = await GpdLogSpill.list()
    expect(entries.length).toBe(1)
    expect(entries[0]!.ulid).toBe(meta.seq)
    expect(entries[0]!.meta.sessionID).toBe("sess-1")

    const read = await GpdLogSpill.readBody(meta.seq)
    expect(Array.from(read)).toEqual([1, 2, 3, 4])

    await GpdLogSpill.remove(meta.seq)
    expect((await GpdLogSpill.list()).length).toBe(0)
  })

  test("lists multiple entries oldest-first by ULID", async () => {
    const mk = (ulid: string) => ({
      sessionID: "s",
      rootSessionID: "s",
      seq: ulid,
      contentLength: 1,
      createdAt: 0,
    })
    await GpdLogSpill.write("01HA00000000000000000000A1", mk("01HA00000000000000000000A1"), new Uint8Array([0]))
    await GpdLogSpill.write("01HB00000000000000000000B1", mk("01HB00000000000000000000B1"), new Uint8Array([0]))
    await GpdLogSpill.write("01HC00000000000000000000C1", mk("01HC00000000000000000000C1"), new Uint8Array([0]))

    const entries = await GpdLogSpill.list()
    expect(entries.map((e) => e.ulid)).toEqual([
      "01HA00000000000000000000A1",
      "01HB00000000000000000000B1",
      "01HC00000000000000000000C1",
    ])
    await Promise.all(entries.map((e) => GpdLogSpill.remove(e.ulid)))
  })

  test("orphaned .gz-only or .meta-only entries are garbage-collected on list", async () => {
    const dir = GpdLogSpill.dir()
    await fs.mkdir(dir, { recursive: true })
    await fs.writeFile(path.join(dir, "orphan-gz.gz"), new Uint8Array([9]))
    await fs.writeFile(path.join(dir, "orphan-meta.meta"), JSON.stringify({}))
    await fs.writeFile(path.join(dir, "leftover.gz.tmp"), new Uint8Array([9]))

    const entries = await GpdLogSpill.list()
    expect(entries.length).toBe(0)
    const remaining = await fs.readdir(dir)
    // All three orphans should have been cleaned up.
    expect(remaining).toEqual([])
  })

  test("enforces byte budget by dropping oldest", async () => {
    process.env.OPENCODE_GPD_LOG_SPILL_MAX_BYTES = "100"
    try {
      const mk = (ulid: string) => ({ sessionID: "s", rootSessionID: "s", seq: ulid, contentLength: 60, createdAt: 0 })
      // Each body is 60 bytes; 3 entries > 100-byte budget → oldest dropped.
      const body = new Uint8Array(60)
      await GpdLogSpill.write("01HD00000000000000000000A1", mk("01HD00000000000000000000A1"), body)
      await GpdLogSpill.write("01HD00000000000000000000A2", mk("01HD00000000000000000000A2"), body)
      await GpdLogSpill.write("01HD00000000000000000000A3", mk("01HD00000000000000000000A3"), body)

      const entries = await GpdLogSpill.list()
      expect(entries.length).toBeLessThanOrEqual(2)
      // Newest survivors
      const surviving = entries.map((e) => e.ulid).sort()
      expect(surviving).not.toContain("01HD00000000000000000000A1")

      await Promise.all(entries.map((e) => GpdLogSpill.remove(e.ulid)))
    } finally {
      delete process.env.OPENCODE_GPD_LOG_SPILL_MAX_BYTES
    }
  })
})
