/**
 * Terms-of-Service and Privacy Policy content rendered in the acceptance gate.
 *
 * [PLACEHOLDER — DO NOT SHIP TO EXTERNAL USERS]
 *
 * This file exists so PSI legal can replace the text in one place without
 * touching any other code. The string + CURRENT_TOS_VERSION constant are the
 * contract with both tos-section.tsx (renderer) and the LiteLLM server-side
 * acceptance endpoint (which records the version, not the text).
 *
 * When legal delivers real text:
 *   1. Replace TOS_TEXT below.
 *   2. Bump CURRENT_TOS_VERSION to a user-facing version string (e.g. "1.0").
 *   3. Remove the [PLACEHOLDER — DO NOT SHIP] banner from TOS_TEXT.
 *   4. Every user on the previous version will be re-prompted at next launch.
 */

/** Increment this on any MATERIAL TOS change (data-use, liability, new fees).
 *  Non-material edits (typo fix, rewording) should NOT bump — re-prompting
 *  users for trivial changes trains them to click-through.
 *
 *  The string is stored verbatim in the server-side acceptance row, so it
 *  is the legal anchor for "which TOS did this user agree to". */
export const CURRENT_TOS_VERSION = "0.0-placeholder"

/** localStorage key under which the last-accepted TOS version is cached.
 *  SetupGate compares this against CURRENT_TOS_VERSION on every launch to
 *  decide whether to re-prompt. Wiping this key (via dev tools) simulates
 *  a fresh install without touching the LiteLLM auth state. */
export const TOS_ACCEPTED_VERSION_STORAGE_KEY = "gpd.tos.acceptedVersion"

/** localStorage key under which the LiteLLM virtual key is cached for the
 *  sole purpose of re-POSTing acceptance on a TOS version bump without
 *  re-prompting the user.
 *
 *  Same trust envelope as `~/.local/share/opencode/auth.json` (both are
 *  per-user filesystem-scoped on the same device; any attacker with FS
 *  access to one has access to both). We do NOT consider this a new
 *  secret surface. Cleared on key reset / sign-out.
 *
 *  Not load-bearing for the main chat flow — the sidecar reads auth.json,
 *  not this localStorage entry. If this ever falls out of sync with
 *  auth.json the TOS upgrade gate will show an error and fall back to
 *  the welcome screen. */
export const KEY_CACHE_STORAGE_KEY = "gpd.apiKey"

/** Human-readable TOS text. Rendered as pre-wrap text; line-breaks shown. */
export const TOS_TEXT = `[PLACEHOLDER — DO NOT SHIP TO EXTERNAL USERS]

By clicking "I agree" you accept the GPD Terms of Service and Privacy Policy.

1. The GPD application is provided by PSI Inc. for physics research use. You
   access upstream AI providers (Anthropic, OpenAI, Google) through a
   PSI-managed proxy.

2. Your session prompts, tool outputs, and file contents are stored in
   PSI-controlled cloud storage for up to 24 months. This data is used for
   operations, debugging, billing reconciliation, and abuse detection. Your
   IP address and browser user-agent are captured at the moment of
   acceptance and retained as part of this record. You may request deletion
   of your data at any time by contacting support@psi.inc.

3. The software is provided "as is" with no warranty. PSI is not liable for
   research output, model hallucinations, or damages arising from use of
   the application.

4. By accepting, you confirm you are authorized to use PSI's research
   infrastructure under your institutional agreement with PSI.

Revision ${CURRENT_TOS_VERSION}.`
