export const deepLinkEvent = "opencode:deep-link"

/**
 * Schemes the app accepts in deep links. `gpd://` is the Tauri-registered
 * protocol (see `packages/desktop/src-tauri/tauri.conf.json`); `opencode://`
 * is the upstream legacy scheme we still accept for backward compat.
 *
 * Any parser that sidesteps this allowlist (e.g. a scheme-agnostic
 * `new URL(input)` that only checks `hostname`) must be rejected in
 * review: `https://session/<id>` would pass such a check and feed
 * `session.get` on user-controlled input. See
 * `docs/PR-REVIEW-2026-04-22.md` § PR #20.
 */
const APP_SCHEMES = ["gpd://", "opencode://"] as const

const parseUrl = (input: string) => {
  if (!input.startsWith("opencode://")) return
  if (typeof URL.canParse === "function" && !URL.canParse(input)) return
  try {
    return new URL(input)
  } catch {
    return
  }
}

/**
 * Accepts both `gpd://` and `opencode://` URLs. Use for helpers that
 * the Tauri desktop app can legitimately invoke via its own registered
 * scheme. For helpers that must be pinned to a single scheme, use the
 * private `parseUrl` above.
 */
const parseAppSchemeUrl = (input: string) => {
  if (!APP_SCHEMES.some((s) => input.startsWith(s))) return
  if (typeof URL.canParse === "function" && !URL.canParse(input)) return
  try {
    return new URL(input)
  } catch {
    return
  }
}

export const parseDeepLink = (input: string) => {
  const url = parseUrl(input)
  if (!url) return
  if (url.hostname !== "open-project") return
  const directory = url.searchParams.get("directory")
  if (!directory) return
  return directory
}

export const parseNewSessionDeepLink = (input: string) => {
  const url = parseUrl(input)
  if (!url) return
  if (url.hostname !== "new-session") return
  const directory = url.searchParams.get("directory")
  if (!directory) return
  const prompt = url.searchParams.get("prompt") || undefined
  if (!prompt) return { directory }
  return { directory, prompt }
}

export const collectOpenProjectDeepLinks = (urls: string[]) =>
  urls.map(parseDeepLink).filter((directory): directory is string => !!directory)

export const collectNewSessionDeepLinks = (urls: string[]) =>
  urls.map(parseNewSessionDeepLink).filter((link): link is { directory: string; prompt?: string } => !!link)

/**
 * Parse a `gpd://session/<sessionID>` or `opencode://session/<sessionID>`
 * deep link. The session ID lives at the first pathname segment, not the
 * hostname (URL.hostname on `foo://bar/baz` gives `bar`, so we look at
 * `url.pathname.replace(/^\//, "")` for the id). Returns `undefined`
 * for any scheme not on the app allowlist.
 */
export const parseSessionDeepLink = (input: string) => {
  const url = parseAppSchemeUrl(input)
  if (!url) return
  if (url.hostname !== "session") return
  const id = url.pathname.replace(/^\/+/, "").replace(/\/+$/, "")
  if (!id) return
  return id
}

/**
 * When multiple session deep links arrive in a batch, only the LAST one
 * should determine the final navigation. A fire-and-forget loop that
 * calls `session.get` per link and navigates on every completion is
 * last-response-wins, not last-link-wins: a slow stale lookup can yank
 * the UI back to an older session after a newer link was clicked or
 * the user performed another navigation.
 *
 * Callers that receive a batch of pending URLs (e.g. drained from
 * `drainPendingDeepLinks`) should pipe session-shaped links through
 * this helper before resolving.
 */
export const collectSessionDeepLinks = (urls: string[]) =>
  urls.map(parseSessionDeepLink).filter((id): id is string => !!id)

export const lastSessionDeepLink = (urls: string[]): string | undefined => {
  const ids = collectSessionDeepLinks(urls)
  return ids.length ? ids[ids.length - 1] : undefined
}

type OpenCodeWindow = Window & {
  __OPENCODE__?: {
    deepLinks?: string[]
  }
}

export const drainPendingDeepLinks = (target: OpenCodeWindow) => {
  const pending = target.__OPENCODE__?.deepLinks ?? []
  if (pending.length === 0) return []
  if (target.__OPENCODE__) target.__OPENCODE__.deepLinks = []
  return pending
}
