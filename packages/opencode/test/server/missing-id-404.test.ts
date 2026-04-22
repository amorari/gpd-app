import { afterEach, describe, expect, test } from "bun:test"
import { Instance } from "../../src/project/instance"
import { Server } from "../../src/server/server"
import { Log } from "../../src/util/log"
import { tmpdir } from "../fixture/fixture"

Log.init({ print: false })

afterEach(async () => {
  await Instance.disposeAll()
})

// Before Task 2.1 these three routes silently 200'd when the ID was
// missing or already resolved — callers couldn't distinguish a stale
// retry from a bogus ID. PR #13 tried to fix it with a route-level
// list()+some() pre-check, which had its own TOCTOU race. Task 2.1
// pushed the check into the service layer (throws NotFoundError),
// which the existing ErrorMiddleware maps to HTTP 404 via the
// NamedError machinery at packages/opencode/src/server/middleware.ts.

describe("404 on nonexistent IDs (Task 2.1)", () => {
  const headers = (tmpPath: string) => ({
    "content-type": "application/json",
    "x-opencode-directory": tmpPath,
  })

  test("permission.reply returns 404 for unknown requestID", async () => {
    await using tmp = await tmpdir({ git: true })
    const app = Server.Default().app
    const res = await app.request("/permission/per_does_not_exist/reply", {
      method: "POST",
      headers: headers(tmp.path),
      body: JSON.stringify({ reply: "once" }),
    })
    expect(res.status).toBe(404)
  })

  test("question.reply returns 404 for unknown requestID", async () => {
    await using tmp = await tmpdir({ git: true })
    const app = Server.Default().app
    const res = await app.request("/question/que_does_not_exist/reply", {
      method: "POST",
      headers: headers(tmp.path),
      body: JSON.stringify({ answers: [["anything"]] }),
    })
    expect(res.status).toBe(404)
  })

  test("question.reject returns 404 for unknown requestID", async () => {
    await using tmp = await tmpdir({ git: true })
    const app = Server.Default().app
    const res = await app.request("/question/que_does_not_exist/reject", {
      method: "POST",
      headers: headers(tmp.path),
    })
    expect(res.status).toBe(404)
  })

  test("session.revert returns 404 for unknown messageID", async () => {
    await using tmp = await tmpdir({ git: true })
    const app = Server.Default().app
    // Create a session so sessionID exists (otherwise sessions.messages
    // throws NotFoundError for session-not-found, which is ALSO 404 but
    // from a different code path — we want to exercise the messageID
    // miss specifically).
    const created = await app.request("/session", {
      method: "POST",
      headers: headers(tmp.path),
      body: JSON.stringify({}),
    })
    expect(created.status).toBe(200)
    const session = await created.json()

    const res = await app.request(`/session/${session.id}/revert`, {
      method: "POST",
      headers: headers(tmp.path),
      body: JSON.stringify({ messageID: "msg_does_not_exist" }),
    })
    expect(res.status).toBe(404)
  })
})
