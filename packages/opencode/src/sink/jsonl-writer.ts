import fs from "fs/promises"
import path from "path"
import crypto from "crypto"
import { Global } from "@/global"
import { GpdLog } from "./schema"

export namespace GpdLogWriter {
  /**
   * Base directory for Phase-2 local JSONL logs. Phase 3 switches the
   * transport to POST /gpd/log through the LiteLLM proxy, but files written
   * here remain useful as the on-disk spill staging area.
   */
  export function baseDir(): string {
    return path.join(Global.Path.data, "gpd-session-logs")
  }

  function sessionDir(rootSessionID: string): string {
    return path.join(baseDir(), rootSessionID)
  }

  function jsonlPath(rootSessionID: string, sessionID: string): string {
    if (sessionID === rootSessionID) {
      return path.join(sessionDir(rootSessionID), "root.jsonl")
    }
    return path.join(sessionDir(rootSessionID), "subagents", `agent-${sessionID}.jsonl`)
  }

  function spillPath(rootSessionID: string, sha: string): string {
    return path.join(sessionDir(rootSessionID), "tool-results", `${sha}.txt`)
  }

  function indexPath(rootSessionID: string): string {
    return path.join(sessionDir(rootSessionID), "index.json")
  }

  /**
   * Write one or more events as NDJSON lines to the session's log file.
   * Events are routed to `root.jsonl` or `subagents/agent-<id>.jsonl`
   * based on `sessionID` vs. `rootSessionID`.
   *
   * Tool-part outputs larger than `SPILL_BYTES_THRESHOLD` are written to
   * `tool-results/<sha256>.txt` and the JSONL line stores only the hash
   * plus first/last 256 chars for grep-ability.
   */
  export async function append(rootSessionID: string, events: GpdLog.Event[]): Promise<void> {
    const byFile = new Map<string, GpdLog.Event[]>()
    const spills: { path: string; content: string }[] = []

    for (const evt of events) {
      const processed = maybeSpill(rootSessionID, evt, spills)
      const p = jsonlPath(rootSessionID, processed.sessionID)
      const arr = byFile.get(p) ?? []
      arr.push(processed)
      byFile.set(p, arr)
    }

    await Promise.all([
      ...spills.map(async (s) => {
        await fs.mkdir(path.dirname(s.path), { recursive: true })
        // Idempotent: content-addressed, identical hashes have identical bytes.
        await fs.writeFile(s.path, s.content, { flag: "w" }).catch((e) => {
          if (e?.code === "EEXIST") return
          throw e
        })
      }),
      ...Array.from(byFile.entries()).map(async ([filePath, evts]) => {
        await fs.mkdir(path.dirname(filePath), { recursive: true })
        const lines = evts.map((e) => JSON.stringify(e)).join("\n") + "\n"
        await fs.appendFile(filePath, lines, { encoding: "utf8" })
      }),
    ])
  }

  /**
   * If the event is a tool-part update whose output exceeds the threshold,
   * spill the output to a side file and replace the in-line text with a
   * placeholder referencing the hash.
   */
  function maybeSpill(
    rootSessionID: string,
    evt: GpdLog.Event,
    spills: { path: string; content: string }[],
  ): GpdLog.Event {
    if (evt.kind !== "part_updated") return evt
    const part = evt.part as unknown as { type: string; state?: { output?: string } }
    if (part.type !== "tool") return evt
    const output = part.state?.output
    if (typeof output !== "string") return evt
    if (Buffer.byteLength(output, "utf8") <= GpdLog.SPILL_BYTES_THRESHOLD) return evt

    const sha = crypto.createHash("sha256").update(output, "utf8").digest("hex")
    spills.push({ path: spillPath(rootSessionID, sha), content: output })

    // Preserve grep-ability: keep first/last 256 chars as an excerpt; the
    // full content lives under tool-results/<sha>.txt.
    const head = output.slice(0, 256)
    const tail = output.length > 512 ? output.slice(-256) : ""
    const placeholder = `__spilled__:${sha}\n<head>${head}</head>\n<tail>${tail}</tail>`

    return {
      ...evt,
      // Shallow-clone only the output path; upstream parts are immutable
      // per OpenCode conventions (we own this payload from here on).
      part: {
        ...(evt.part as unknown as Record<string, unknown>),
        state: {
          ...(part.state as Record<string, unknown>),
          output: placeholder,
        },
      } as unknown as typeof evt.part,
      spilledBlobSha: sha,
    }
  }

  /**
   * Write (or overwrite) the per-session manifest. Called on session close
   * or periodically as the session progresses; always a full rewrite.
   */
  export async function writeIndex(
    rootSessionID: string,
    manifest: {
      rootSessionID: string
      subagentSessionIDs: string[]
      createdAt: number
      closedAt: number | null
      reason: GpdLog.SessionCloseEvent["reason"] | null
    },
  ): Promise<void> {
    const p = indexPath(rootSessionID)
    await fs.mkdir(path.dirname(p), { recursive: true })
    await fs.writeFile(p, JSON.stringify(manifest, null, 2), { encoding: "utf8" })
  }
}
