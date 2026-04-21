import { Context, Effect, Exit, Layer, Scope, Stream } from "effect"
import { Bus } from "@/bus"
import { InstanceState } from "@/effect/instance-state"
import { Session } from "@/session"
import { MessageV2 } from "@/session/message-v2"
import type { SessionID } from "@/session/schema"
import { Log } from "@/util/log"
import { GpdLog } from "./schema"
import { GpdLogWriter } from "./jsonl-writer"

export namespace GpdLogger {
  const log = Log.create({ service: "gpd-logger" })
  const enabled =
    process.env["OPENCODE_GPD_LOGS_ENABLED"] === "1" || process.env["OPENCODE_GPD_LOGS_ENABLED"] === "true"

  type QueuedEvent =
    | { kind: "message"; sessionID: SessionID; info: MessageV2.Info }
    | { kind: "part"; sessionID: SessionID; part: MessageV2.Part }
    | { kind: "session"; sessionID: SessionID; info: Session.Info }
    | { kind: "diff"; sessionID: SessionID; diff: Parameters<typeof GpdLogWriter.append>[1][number] extends infer _ ? unknown : never }
    | { kind: "deleted"; sessionID: SessionID }

  type State = {
    /** Per-session event queue, keyed by coalesce-key within the session. */
    queue: Map<SessionID, Map<string, QueuedEvent>>
    /** Cached root-session ID per session to avoid repeated DB walks. */
    rootCache: Map<SessionID, SessionID>
    /** Tracks sessions we've already written the `session_init` header for. */
    initialized: Set<SessionID>
    scope: Scope.Closeable
  }

  export interface Interface {
    readonly init: () => Effect.Effect<void>
  }

  export class Service extends Context.Service<Service, Interface>()("@opencode/GpdLogger") {}

  function coalesceKey(evt: QueuedEvent): string {
    switch (evt.kind) {
      case "session":
        return "session"
      case "message":
        return `msg/${evt.info.id}`
      case "part":
        return `part/${evt.part.messageID}/${evt.part.id}`
      case "diff":
        return "diff"
      case "deleted":
        return "deleted"
    }
  }

  /** Walk up the parent chain once, memoised per session. */
  function resolveRoot(
    sessions: Session.Interface,
    cache: Map<SessionID, SessionID>,
    sessionID: SessionID,
  ): Effect.Effect<SessionID> {
    const cached = cache.get(sessionID)
    if (cached) return Effect.succeed(cached)
    return Effect.gen(function* () {
      const root = yield* sessions.root(sessionID)
      cache.set(sessionID, root)
      return root
    })
  }

  /** Materialise queued events into GpdLog.Event lines, including session_init on first touch. */
  function materialise(
    sessionID: SessionID,
    rootSessionID: SessionID,
    parentSessionID: SessionID | null,
    sessionInfo: Session.Info | undefined,
    queued: QueuedEvent[],
    initialized: Set<SessionID>,
  ): GpdLog.Event[] {
    const out: GpdLog.Event[] = []
    const now = Date.now()

    if (!initialized.has(sessionID) && sessionInfo) {
      out.push({
        kind: "session_init",
        v: GpdLog.SCHEMA_VERSION,
        ts: now,
        sessionID,
        parentSessionID,
        rootSessionID,
        info: sessionInfo,
      })
      initialized.add(sessionID)
    }

    for (const evt of queued) {
      switch (evt.kind) {
        case "message":
          out.push({
            kind: "message_updated",
            v: GpdLog.SCHEMA_VERSION,
            ts: now,
            sessionID: evt.sessionID,
            info: evt.info,
          })
          break
        case "part":
          out.push({
            kind: "part_updated",
            v: GpdLog.SCHEMA_VERSION,
            ts: now,
            sessionID: evt.sessionID,
            part: evt.part,
          })
          break
        case "session":
          // already folded into session_init; no extra line needed.
          break
        case "diff":
          out.push({
            kind: "session_diff",
            v: GpdLog.SCHEMA_VERSION,
            ts: now,
            sessionID: evt.sessionID,
            diff: evt.diff as never,
          })
          break
        case "deleted":
          out.push({
            kind: "session_deleted",
            v: GpdLog.SCHEMA_VERSION,
            ts: now,
            sessionID: evt.sessionID,
          })
          break
      }
    }

    return out
  }

  export const layer = Layer.effect(
    Service,
    Effect.gen(function* () {
      const bus = yield* Bus.Service
      const sessions = yield* Session.Service

      function enqueue(sessionID: SessionID, evt: QueuedEvent): Effect.Effect<void> {
        return Effect.gen(function* () {
          if (!enabled) return
          const s = yield* InstanceState.get(state)
          const k = coalesceKey(evt)
          const existing = s.queue.get(sessionID)
          if (existing) {
            existing.set(k, evt)
            return
          }
          const m = new Map<string, QueuedEvent>()
          m.set(k, evt)
          s.queue.set(sessionID, m)
          yield* flush(sessionID).pipe(
            Effect.delay(1000),
            Effect.catchCause((cause) =>
              Effect.sync(() => log.error("gpd-logger flush failed", { sessionID, cause })),
            ),
            Effect.forkIn(s.scope),
          )
        })
      }

      const flush = Effect.fn("GpdLogger.flush")(function* (sessionID: SessionID) {
        if (!enabled) return
        const s = yield* InstanceState.get(state)
        const queued = s.queue.get(sessionID)
        if (!queued) return
        s.queue.delete(sessionID)

        const root = yield* resolveRoot(sessions, s.rootCache, sessionID)

        // Pull session info once per flush for parent/init data.
        const sessionInfo = yield* sessions
          .get(sessionID)
          .pipe(Effect.catchCause(() => Effect.succeed(undefined as Session.Info | undefined)))
        const parentSessionID = (sessionInfo?.parentID ?? null) as SessionID | null

        const events = materialise(
          sessionID,
          root,
          parentSessionID,
          sessionInfo,
          Array.from(queued.values()),
          s.initialized,
        )
        if (events.length === 0) return
        yield* Effect.promise(() => GpdLogWriter.append(root, events))
      })

      const state: InstanceState<State> = yield* InstanceState.make<State>(
        Effect.fn("GpdLogger.state")(function* (_ctx) {
          const cache: State = {
            queue: new Map(),
            rootCache: new Map(),
            initialized: new Set(),
            scope: yield* Scope.make(),
          }

          yield* Effect.addFinalizer(() =>
            Scope.close(cache.scope, Exit.void).pipe(
              Effect.andThen(
                Effect.sync(() => {
                  cache.queue.clear()
                  cache.rootCache.clear()
                  cache.initialized.clear()
                }),
              ),
            ),
          )

          if (!enabled) return cache

          const watch = <D extends { type: string }>(
            def: D,
            fn: (evt: { properties: any }) => Effect.Effect<void, unknown>,
          ) =>
            bus.subscribe(def as never).pipe(
              Stream.runForEach((evt) =>
                fn(evt).pipe(
                  Effect.catchCause((cause) =>
                    Effect.sync(() => log.error("gpd-logger subscriber failed", { type: def.type, cause })),
                  ),
                ),
              ),
              Effect.forkScoped,
            )

          yield* watch(Session.Event.Updated, (evt) =>
            Effect.gen(function* () {
              const info = yield* sessions.get(evt.properties.sessionID)
              yield* enqueue(info.id, { kind: "session", sessionID: info.id, info })
            }),
          )
          yield* watch(MessageV2.Event.Updated, (evt) =>
            enqueue(evt.properties.info.sessionID, {
              kind: "message",
              sessionID: evt.properties.info.sessionID,
              info: evt.properties.info,
            }),
          )
          yield* watch(MessageV2.Event.PartUpdated, (evt) =>
            enqueue(evt.properties.part.sessionID, {
              kind: "part",
              sessionID: evt.properties.part.sessionID,
              part: evt.properties.part,
            }),
          )
          yield* watch(Session.Event.Diff, (evt) =>
            enqueue(evt.properties.sessionID, {
              kind: "diff",
              sessionID: evt.properties.sessionID,
              diff: evt.properties.diff,
            }),
          )
          yield* watch(Session.Event.Deleted, (evt) =>
            enqueue(evt.properties.sessionID, {
              kind: "deleted",
              sessionID: evt.properties.sessionID,
            }),
          )

          return cache
        }),
      )

      const init: Interface["init"] = () =>
        Effect.gen(function* () {
          if (!enabled) return
          yield* InstanceState.get(state)
          log.info("initialized", { baseDir: GpdLogWriter.baseDir() })
        })

      return Service.of({ init })
    }),
  )

  export const defaultLayer = Layer.suspend(() =>
    layer.pipe(Layer.provide(Bus.layer), Layer.provide(Session.defaultLayer)),
  )
}
