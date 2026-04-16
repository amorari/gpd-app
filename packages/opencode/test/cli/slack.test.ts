import { afterEach, expect, mock, test } from "bun:test"
import { postSlackMessage } from "../../src/cli/cmd/slack"

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

test("posts a message with the user token", async () => {
  const calls: RequestInit[] = []
  globalThis.fetch = mock((input: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {})
    expect(input.toString()).toBe("https://slack.com/api/chat.postMessage")
    return Promise.resolve(
      new Response(
        JSON.stringify({
          ok: true,
          channel: "C123",
          ts: "123.456",
        }),
        { status: 200 },
      ),
    )
  }) as unknown as typeof fetch

  const result = await postSlackMessage(
    {
      channel: "C123",
      text: "testing",
    },
    {
      SLACK_USER_TOKEN: "xoxp-test",
    },
  )

  expect(result.channel).toBe("C123")
  expect(result.ts).toBe("123.456")
  expect(calls).toHaveLength(1)
  expect(calls[0]?.method).toBe("POST")
  expect(calls[0]?.headers).toEqual({
    Authorization: "Bearer xoxp-test",
    "Content-Type": "application/json; charset=utf-8",
  })
  expect(calls[0]?.body).toBe(JSON.stringify({ channel: "C123", text: "testing" }))
})

test("includes thread_ts when provided", async () => {
  let body: string | undefined
  globalThis.fetch = mock((_input: string | URL | Request, init?: RequestInit) => {
    body = init?.body as string | undefined
    return Promise.resolve(
      new Response(
        JSON.stringify({
          ok: true,
          channel: "C123",
          ts: "123.456",
        }),
        { status: 200 },
      ),
    )
  }) as unknown as typeof fetch

  await postSlackMessage(
    {
      channel: "C123",
      text: "testing",
      thread: "111.222",
    },
    {
      SLACK_USER_TOKEN: "xoxp-test",
    },
  )

  expect(body).toBe(JSON.stringify({ channel: "C123", text: "testing", thread_ts: "111.222" }))
})

test("fails when the token is missing", async () => {
  await expect(
    postSlackMessage({
      channel: "C123",
      text: "testing",
    }),
  ).rejects.toThrow("Missing Slack token in SLACK_USER_TOKEN")
})

test("fails when Slack rejects the request", async () => {
  globalThis.fetch = mock(() =>
    Promise.resolve(
      new Response(
        JSON.stringify({
          ok: false,
          error: "channel_not_found",
        }),
        { status: 200 },
      ),
    ),
  ) as unknown as typeof fetch

  await expect(
    postSlackMessage(
      {
        channel: "C123",
        text: "testing",
      },
      {
        SLACK_USER_TOKEN: "xoxp-test",
      },
    ),
  ).rejects.toThrow("Slack API error: channel_not_found")
})
