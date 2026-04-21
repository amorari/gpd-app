import { UI } from "../ui"
import { cmd } from "./cmd"

function token(key: string, env: NodeJS.ProcessEnv) {
  const val = env[key]?.trim()
  if (val) return val
  throw new Error(`Missing Slack token in ${key}`)
}

export async function postSlackMessage(
  input: {
    channel: string
    text: string
    thread?: string
    token_env?: string
  },
  env: NodeJS.ProcessEnv = process.env,
  fetcher: typeof fetch = fetch,
) {
  const key = input.token_env ?? "SLACK_USER_TOKEN"
  const res = await fetcher("https://slack.com/api/chat.postMessage", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token(key, env)}`,
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify({
      channel: input.channel,
      text: input.text,
      ...(input.thread ? { thread_ts: input.thread } : {}),
    }),
  })

  if (!res.ok) {
    throw new Error(`Slack HTTP error: ${res.status}`)
  }

  const data = (await res.json()) as {
    ok?: boolean
    error?: string
    channel?: string
    ts?: string
  }

  if (!data.ok) {
    throw new Error(`Slack API error: ${data.error ?? "unknown_error"}`)
  }

  return {
    channel: data.channel ?? input.channel,
    ts: data.ts ?? "",
  }
}

export const SlackSendCommand = cmd({
  command: "send <channel> <text>",
  describe: "send a Slack message",
  builder: (yargs) =>
    yargs
      .positional("channel", {
        describe: "Slack channel ID",
        type: "string",
      })
      .positional("text", {
        describe: "message text",
        type: "string",
      })
      .option("thread", {
        describe: "reply in an existing thread by thread timestamp",
        type: "string",
      })
      .option("token-env", {
        describe: "environment variable containing the Slack token",
        type: "string",
        default: "SLACK_USER_TOKEN",
      }),
  handler: async (args) => {
    if (!args.channel) {
      throw new Error("Missing channel")
    }

    if (!args.text) {
      throw new Error("Missing text")
    }

    const data = await postSlackMessage({
      channel: args.channel,
      text: args.text,
      thread: args.thread,
      token_env: args.tokenEnv,
    })

    UI.println(`Sent to ${data.channel} at ${data.ts}`)
  },
})

export const SlackCommand = cmd({
  command: "slack",
  describe: "send Slack messages",
  builder: (yargs) => yargs.command(SlackSendCommand).demandCommand(),
  async handler() {},
})
