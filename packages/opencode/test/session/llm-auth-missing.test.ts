import { describe, expect, test } from "bun:test"
import path from "path"
import { Cause, Effect, Exit, Stream } from "effect"
import type { ModelMessage } from "ai"
import { makeRuntime } from "../../src/effect/run-service"
import { LLM } from "../../src/session/llm"
import { Instance } from "../../src/project/instance"
import { Provider } from "../../src/provider/provider"
import { ModelsDev } from "../../src/provider/models"
import { ProviderID, ModelID } from "../../src/provider/schema"
import { Filesystem } from "../../src/util/filesystem"
import { tmpdir } from "../fixture/fixture"
import type { Agent } from "../../src/agent/agent"
import type { MessageV2 } from "../../src/session/message-v2"
import { SessionID, MessageID } from "../../src/session/schema"
import { AppRuntime } from "../../src/effect/app-runtime"

// Regression: GPD 1.1.12 shipped with a silent 401 path. When auth.json
// was empty (Change-API-Key wrote `{}` and never reloaded the UI) the
// sidecar still dispatched the streamText call — just with no
// Authorization header. LiteLLM returned 401 which the frontend
// classifier guessed as auth failure. The fix is a sidecar-local
// fail-fast: Provider.AuthMissingError when every key source comes up
// empty, so the UX is the same but we skip the wasted roundtrip and the
// log tells us why.
const llm = makeRuntime(LLM.Service, LLM.defaultLayer)

async function getModel(providerID: ProviderID, modelID: ModelID) {
  return AppRuntime.runPromise(
    Effect.gen(function* () {
      const provider = yield* Provider.Service
      return yield* provider.getModel(providerID, modelID)
    }),
  )
}

async function loadFixture(providerID: string, modelID: string) {
  const fixturePath = path.join(import.meta.dir, "../tool/fixtures/models-api.json")
  const data = await Filesystem.readJson<Record<string, ModelsDev.Provider>>(fixturePath)
  const provider = data[providerID]
  if (!provider) throw new Error(`Missing provider in fixture: ${providerID}`)
  const model = provider.models[modelID]
  if (!model) throw new Error(`Missing model in fixture: ${modelID}`)
  return { provider, model }
}

describe("session.llm.authMissing", () => {
  test("fails fast with ProviderAuthMissingError when no auth source is available", async () => {
    const providerID = "vivgrid"
    const modelID = "gemini-3.1-pro-preview"
    const fixture = await loadFixture(providerID, modelID)

    // Config intentionally omits options.apiKey, env, and auth.json
    // entries. This matches the 1.1.12 prod state where auth.json was
    // empty `{}` and the provider was config-sourced with no key.
    await using tmp = await tmpdir({
      init: async (dir) => {
        await Bun.write(
          path.join(dir, "opencode.json"),
          JSON.stringify({
            $schema: "https://opencode.ai/config.json",
            enabled_providers: [providerID],
            provider: {
              [providerID]: {
                env: [],
                options: {
                  baseURL: "http://127.0.0.1:65535/v1",
                },
              },
            },
          }),
        )
      },
    })

    await Instance.provide({
      directory: tmp.path,
      fn: async () => {
        const resolved = await getModel(ProviderID.make(providerID), ModelID.make(fixture.model.id))
        const sessionID = SessionID.make("session-auth-missing")
        const agent = {
          name: "test",
          mode: "primary",
          options: {},
          permission: [{ permission: "*", pattern: "*", action: "allow" }],
          temperature: 0.4,
          topP: 0.8,
        } satisfies Agent.Info

        const user = {
          id: MessageID.make("user-1"),
          sessionID,
          role: "user",
          time: { created: Date.now() },
          agent: agent.name,
          model: {
            providerID: ProviderID.make(providerID),
            modelID: resolved.id,
            variant: "high",
          },
        } satisfies MessageV2.User

        const messages: ModelMessage[] = [{ role: "user", content: "Hello" }]

        const exit = await llm.runPromise((svc) =>
          svc
            .stream({
              user,
              sessionID,
              model: resolved,
              agent,
              system: ["You are a helpful assistant."],
              messages,
              tools: {},
            })
            .pipe(Stream.runDrain)
            .pipe(Effect.exit),
        )

        expect(Exit.isFailure(exit)).toBe(true)
        if (!Exit.isFailure(exit)) return
        const failure = Cause.squash(exit.cause)
        expect(Provider.AuthMissingError.isInstance(failure)).toBe(true)
        if (Provider.AuthMissingError.isInstance(failure)) {
          expect(failure.data.providerID).toBe(providerID)
        }
      },
    })
  })
})
