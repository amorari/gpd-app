// Worker spawned per concurrent Auth.set call in auth-concurrent.test.ts.
// Lives in the package tree so node_modules (effect, proper-lockfile)
// resolve normally. Env-driven XDG_DATA_HOME overrides Global.Path.data
// to the throwaway dir the test passes in.
import { Effect } from "effect"

const providerId = process.argv[2]
const dataDir = process.argv[3]

process.env.XDG_DATA_HOME = dataDir

async function main() {
  const { Auth } = await import("../../src/auth")
  const program = Effect.gen(function* () {
    yield* Auth.Service.use((a) => a.set(providerId, { type: "api", key: "k-" + providerId }))
  }).pipe(Effect.provide(Auth.defaultLayer))
  await Effect.runPromise(program)
}

main().then(
  () => process.exit(0),
  (e) => {
    console.error(e)
    process.exit(1)
  },
)
