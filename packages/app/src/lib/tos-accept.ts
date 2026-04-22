/**
 * POST a TOS acceptance to the LiteLLM `/gpd/tos-accept` endpoint.
 *
 * One acceptance = one row in the server-side `gpd_tos_acceptance` table.
 * The server derives user_id + key_last4 from the bearer token and captures
 * the client IP from X-Forwarded-For, so the client supplies only the
 * version strings and lets the browser send its own User-Agent.
 *
 * Throws on any non-2xx. Callers should surface the message to the user
 * (it is either a local validation error like "missing tos_version" or a
 * transient network failure).
 *
 * No retry here — the welcome-screen flow holds the key in memory and can
 * surface a retry-able error to the user. Long-running retries would leave
 * the user staring at a spinner with no way to act.
 *
 * Hard-codes the LiteLLM base URL to match
 * `packages/opencode/src/sink/http-writer.ts:30`. If that ever moves to an
 * env-var, update both sites.
 */
const LITELLM_TOS_ACCEPT_URL =
  "https://litellm-production-46bb.up.railway.app/gpd/tos-accept"

export type TosAcceptInput = {
  /** LiteLLM virtual key — user just typed, or fetched via Auth.Service. */
  key: string
  /** Must match CURRENT_TOS_VERSION at the moment of acceptance. */
  tosVersion: string
  /** SHA-256 hex of the exact TOS_TEXT the user saw. */
  tosTextSha256: string
  /** SHA-256 hex of the exact PRIVACY_TEXT the user saw. Split per GDPR
   *  Art. 7(2) granular-consent requirement. */
  privacyTextSha256: string
  /** Desktop build version, for audit trail. Optional. */
  appVersion?: string
  /** True iff the user scrolled BOTH the TOS and Privacy regions to
   *  their bottom before checking agreement. Defense against "I never
   *  saw clause 7" disputes (Specht v. Netscape class). */
  viewedInFull?: boolean
}

export async function postTosAccept(input: TosAcceptInput): Promise<void> {
  if (!input.key) throw new Error("missing LiteLLM key")
  if (!input.tosVersion) throw new Error("missing tosVersion")
  if (!/^[0-9a-f]{64}$/.test(input.tosTextSha256)) {
    throw new Error("tosTextSha256 must be 64 lowercase hex chars")
  }
  if (!/^[0-9a-f]{64}$/.test(input.privacyTextSha256)) {
    throw new Error("privacyTextSha256 must be 64 lowercase hex chars")
  }

  const params = new URLSearchParams({
    tos_version: input.tosVersion,
    tos_text_sha256: input.tosTextSha256,
    privacy_text_sha256: input.privacyTextSha256,
  })
  if (input.appVersion) params.set("app_version", input.appVersion)
  if (input.viewedInFull) params.set("viewed_in_full", "1")

  const res = await fetch(`${LITELLM_TOS_ACCEPT_URL}?${params.toString()}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${input.key}`,
      // Content-Length 0 — LiteLLM's auth dep requires that the body be
      // drainable; empty is fine and leaves the request tiny.
      "Content-Type": "application/json",
    },
    body: "{}",
  })

  if (!res.ok) {
    let detail = ""
    try {
      const body = (await res.json()) as { detail?: string; error?: { message?: string } }
      detail = body.detail ?? body.error?.message ?? ""
    } catch {
      // non-JSON body; fall through to generic error text
    }
    throw new Error(
      `TOS acceptance failed (HTTP ${res.status})${detail ? `: ${detail}` : ""}`,
    )
  }
}
