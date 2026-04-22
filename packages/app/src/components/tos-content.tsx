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

/** SHA-256 hex of `TOS_TEXT` below, computed at commit time.
 *
 *  Every acceptance POST includes this so server-side rows tie back to the
 *  exact text the user saw, even if the source file is later edited or the
 *  git history is rewritten. Build-time guard in `.github/workflows/gpd-release.yml`
 *  (`tos-guard` job) re-hashes TOS_TEXT and fails the release if the constant
 *  is stale.
 *
 *  Regenerate locally after editing TOS_TEXT:
 *    python3 -c "import re,hashlib,pathlib; s=pathlib.Path('packages/app/src/components/tos-content.tsx').read_text(); \
 *      print(hashlib.sha256(re.search(r'export const TOS_TEXT = \`([^\`]+)\`', s).group(1).encode()).hexdigest())" */
export const TOS_TEXT_SHA256 =
  "1b0116a7af40bef52924cffb9b56519674bf05e67a26a234f8c890642bdc3480"

/** SHA-256 hex of `PRIVACY_TEXT` — same update/verify discipline as above. */
export const PRIVACY_TEXT_SHA256 =
  "91feda6952b4cdd0ac394fdcb0a037dd0eab6cf503b7b8dcae563d7852e36a7e"

/** localStorage key under which the last-accepted TOS version is cached.
 *  SetupGate compares this against CURRENT_TOS_VERSION on every launch to
 *  decide whether to re-prompt. Wiping this key (via dev tools) simulates
 *  a fresh install without touching the LiteLLM auth state. */
export const TOS_ACCEPTED_VERSION_STORAGE_KEY = "gpd.tos.acceptedVersion"

// NOTE: the previous `KEY_CACHE_STORAGE_KEY = "gpd.apiKey"` constant has
// been REMOVED. We no longer cache the raw LiteLLM virtual key in WebKit/
// WebView2 localStorage because:
//
//   * WebView's localStorage sandboxing differs across macOS / Windows /
//     Linux (leveldb ACLs on Windows + NFS home-dirs are the problem
//     cases); we couldn't uniformly verify the "same trust envelope as
//     auth.json" claim.
//   * An XSS escape in the webview would exfil the key; auth.json is
//     protected by 0600 FS permissions regardless.
//
// The TOS version-bump gate now asks Tauri (`platform.readGpdKey()`) to
// re-read auth.json at acceptance time. Key stays in exactly one place.

/** Human-readable Terms-of-Service text. Rendered as pre-wrap; line-breaks shown.
 *
 *  Contract of use. Legal terms governing the relationship between the
 *  researcher and PSI. Scope, warranty disclaimers, liability, institutional
 *  authorization. Privacy practices live in `PRIVACY_TEXT` below (split per
 *  GDPR Art. 7(2) granular-consent requirement). */
export const TOS_TEXT = `[PLACEHOLDER — DO NOT SHIP TO EXTERNAL USERS]

GPD Terms of Service

1. The GPD application is provided by PSI Inc. for physics research use.
   You access upstream AI providers (Anthropic, OpenAI, Google) through a
   PSI-managed proxy; this is part of PSI's research infrastructure.

2. The software is provided "as is" with no warranty. PSI is not liable
   for research output, model hallucinations, or damages arising from use
   of the application.

3. By accepting, you confirm you are authorized to use PSI's research
   infrastructure under your institutional agreement with PSI.

4. These terms are governed by [jurisdiction — legal to fill in]. Disputes
   are [arbitration / courts — legal to fill in].

Revision ${CURRENT_TOS_VERSION}.`

/** Human-readable Privacy Policy. Separate document per GDPR Art. 7(2) —
 *  privacy consent must be clearly distinguishable from contract
 *  acceptance. Two scroll + checkbox affordances client-side. */
export const PRIVACY_TEXT = `[PLACEHOLDER — DO NOT SHIP TO EXTERNAL USERS]

GPD Privacy Policy

1. Data you send through GPD — session prompts, tool outputs, file
   contents, diffs — is stored in PSI-controlled cloud storage for up to
   24 months. The lawful basis is PSI's legitimate interest in operating,
   debugging, reconciling billing, and detecting abuse, together with
   explicit consent for research-aggregate uses.

2. Upstream AI providers (Anthropic, OpenAI, Google) act as processors
   for the content of your prompts and receive the text you send for the
   sole purpose of generating a completion. PSI contractually binds
   these processors to not retain your content.

3. Your IP address and browser user-agent are captured at the moment
   of acceptance for audit. Identifying fields (IP, user-agent, token
   hash) are erased on account deletion; the minimal legal-audit record
   (user id, TOS version, text hash, timestamp) is retained per GDPR
   Art. 17(3)(e) for legal-claim defence.

4. You may exercise any of these rights at any time:
     - access (copy of your data)
     - rectification (correcting inaccuracies)
     - erasure (right to be forgotten, subject to Art. 17(3)(e))
     - portability (machine-readable export)
     - withdrawal of consent (without affecting prior lawful processing)
   Contact: privacy@psi.inc. Data Protection Officer: [legal to name].

5. Your data may be transferred to and processed in the United States
   (Google Cloud Platform us-central1). International transfers rely on
   [SCCs / adequacy decision — legal to document].

Revision ${CURRENT_TOS_VERSION}.`
