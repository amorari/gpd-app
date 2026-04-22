/**
 * Canonical workspace-key normalization.
 *
 * The frontend keeps per-directory state across many parallel maps
 * (vcsCache, metaCache, iconCache, children, lifecycle, pins, disposers,
 * persisted `Persist.workspace(dir, ...)` stores, SDK-client cache).
 * If any of these key off a non-canonical form of the directory string,
 * `/repo` and `/repo/` end up with parallel state — the PR #20 symptom
 * where SSE events target the trailing-slash alias, but vcsCache /
 * sdkFor / pins keep using the non-slash variant, leaking duplicate
 * SDK clients and occasionally evicting a live store mid-event.
 *
 * `workspaceKey` centralizes the normalization. Call it at every
 * keyed boundary before inserting, looking up, or deleting.
 *
 * **Rules (pure string, no filesystem access):**
 *   - `null` / empty / whitespace → empty string. Callers must reject
 *     empty keys before using them (an empty string is never a valid
 *     workspace dir).
 *   - Normalize `\` → `/` for cross-platform consistency. On Windows,
 *     downstream consumers that need a native-separator form can
 *     convert back; the KEY space is POSIX-shaped.
 *   - Collapse repeated separators (`///` → `/`). Preserve a leading
 *     `//` on Windows UNC paths if present (`\\\\server\\share`
 *     → `//server/share`).
 *   - Strip a single trailing separator (but preserve `/` / `//server/`).
 *   - Preserve case. We deliberately do NOT case-fold even on
 *     case-insensitive filesystems here: the persisted stores and the
 *     server-emitted `directory` tag in Bus events both preserve the
 *     user's supplied case, so canonicalizing to lower-case would
 *     break round-tripping with the server. If case-insensitive
 *     aliasing becomes a real problem, handle it at the canonicalize
 *     step (see `canonicalizeAndReject` in `utils/project-path.ts`)
 *     rather than the key layer.
 */
export function workspaceKey(dir: string | undefined | null): string {
  if (dir == null) return ""
  const trimmed = dir.trim()
  if (!trimmed) return ""

  // UNC prefix `\\server\share` or `//server/share` — preserve the
  // leading double-slash when we collapse.
  const uncMatch = trimmed.match(/^[\\/]{2,}/)
  const uncPrefix = uncMatch ? "//" : ""

  // Normalize separators to POSIX.
  let p = trimmed.replace(/\\/g, "/")

  // Collapse repeated separators (but not the leading UNC pair).
  if (uncPrefix) {
    p = uncPrefix + p.slice(2).replace(/\/+/g, "/")
  } else {
    p = p.replace(/\/+/g, "/")
  }

  // Strip a single trailing `/` unless the whole path is just `/` or the
  // UNC server prefix `//server` (no path segment — leave as-is).
  if (p.length > 1 && p.endsWith("/")) {
    // `//server/` has length >= 3 and contains one dir. Keep the slash
    // to avoid collapsing `//server/` into `//server` which looks like
    // an incomplete UNC prefix. Same for bare `//server`.
    if (uncPrefix) {
      const tail = p.slice(uncPrefix.length)
      if (tail.indexOf("/") === tail.length - 1) {
        // Only one `/` in the tail and it's trailing — this is the
        // server-name case. Keep as-is.
        return p
      }
    }
    p = p.slice(0, -1)
  }

  return p
}
