import type { Session } from "@/session"
import type { MessageV2 } from "@/session/message-v2"
import type { Snapshot } from "@/snapshot"

export namespace GpdLog {
  export const SCHEMA_VERSION = 1 as const

  export type Event =
    | SessionInitEvent
    | MessageUpdatedEvent
    | PartUpdatedEvent
    | SessionDiffEvent
    | SessionDeletedEvent
    | SessionCloseEvent

  export type SessionInitEvent = {
    kind: "session_init"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
    parentSessionID: string | null
    rootSessionID: string
    info: Session.Info
  }

  export type MessageUpdatedEvent = {
    kind: "message_updated"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
    info: MessageV2.Info
  }

  export type PartUpdatedEvent = {
    kind: "part_updated"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
    part: MessageV2.Part
    /** Placeholder for tool outputs spilled to tool-results/<sha>.txt. */
    spilledBlobSha?: string
  }

  export type SessionDiffEvent = {
    kind: "session_diff"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
    diff: Snapshot.FileDiff[]
  }

  export type SessionDeletedEvent = {
    kind: "session_deleted"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
  }

  export type SessionCloseEvent = {
    kind: "session_close"
    v: typeof SCHEMA_VERSION
    ts: number
    sessionID: string
    reason: "flush" | "delete" | "shutdown"
  }

  /** Threshold above which tool-part output text is spilled to a side file. */
  export const SPILL_BYTES_THRESHOLD = 32 * 1024
}
