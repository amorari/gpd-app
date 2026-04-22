/**
 * Guard against opening dangerous directories as GPD projects.
 *
 * Returns a translation descriptor if the path is unsafe, otherwise `null`.
 * Callers should refuse to open the project and surface the rejection via
 * `language.t(result.key, result.params)`.  Truthiness-only callers can use
 * `!!rejectUnsafeProjectPath(...)`.
 *
 * **Trust model.** `rejectUnsafeProjectPath` is a synchronous string guard.
 * It normalizes `..` segments, URL-decodes, collapses repeated separators,
 * and trims before comparing. It does NOT follow symlinks, resolve alias
 * paths, or case-fold on case-insensitive filesystems. A crafted symlink
 * or alias that points at a forbidden root will bypass it.
 *
 * For URL-driven / untrusted path registration (the only case where this
 * check is a load-bearing trust boundary rather than a UX hint), callers
 * MUST first `canonicalizeProjectPath(path, platform)` — which follows
 * symlinks and resolves `.`/`..` segments via the real filesystem — and
 * pass the canonical result into this function. See Task 1.3 / Task 3.3.
 */
export type ProjectPathRejection = {
  key: string
  params?: Record<string, string>
}

/**
 * Best-effort pure-string normalization. Handles:
 *  - URL-decoding (single pass)
 *  - Trimming leading/trailing whitespace
 *  - Collapsing repeated separators (`//`, `\\\\`)
 *  - Resolving `.` and `..` segments (without touching the filesystem)
 *  - Stripping a single trailing separator (but not the root `/`)
 *
 * Works for POSIX and Windows inputs. Cannot defeat symlink aliases or
 * case-insensitive-filesystem tricks; for those, canonicalize first.
 */
function normalizePath(input: string): string {
  let p = input.trim()
  if (!p) return p

  // URL-decode once. If the input contains `%2e%2e` or `%2f`, this is the
  // only chance to catch it before segment comparison. Malformed escapes
  // fall through unchanged.
  try {
    p = decodeURIComponent(p)
  } catch {
    // ignore — keep raw
  }

  // Detect which separator dominates. Windows paths may mix `\` and `/`.
  const isWindows = /^[a-zA-Z]:[\\/]/.test(p) || p.startsWith("\\\\")
  const sep = isWindows ? "\\" : "/"

  // Normalize separators to the dominant style so segment splitting is
  // consistent. `<home>/Documents/..` and `<home>\\Documents\\..` must
  // normalize to the same result.
  const altSep = sep === "/" ? "\\" : "/"
  p = p.replace(new RegExp(altSep.replace(/[\\]/g, "\\\\"), "g"), sep)

  // Collapse repeated separators. `//a//b` → `/a/b`. Preserve a leading
  // `//` on UNC paths (`\\\\server\\share`) which are Windows-only.
  const uncPrefix = isWindows && p.startsWith("\\\\") ? "\\\\" : ""
  if (uncPrefix) {
    p = uncPrefix + p.slice(2).replace(/\\+/g, "\\")
  } else {
    const repeated = sep === "/" ? /\/+/g : /\\+/g
    p = p.replace(repeated, sep)
  }

  // Resolve `.` and `..` segments. Pure string logic — no FS access.
  const segments = p.split(sep)
  const leadingEmpty = segments[0] === "" // absolute POSIX path
  const resolved: string[] = []
  for (const seg of segments) {
    if (seg === "" || seg === ".") continue
    if (seg === "..") {
      // Don't pop past the root (would be a silent "escape" upward).
      if (resolved.length > 0 && resolved[resolved.length - 1] !== "..") {
        resolved.pop()
      } else if (!leadingEmpty) {
        // Relative path — record the `..` for accurate comparison.
        resolved.push("..")
      }
      // Absolute path: `..` at root is a no-op (POSIX `cd /` + `cd ..` == `/`).
      continue
    }
    resolved.push(seg)
  }
  const joined = resolved.join(sep)

  if (uncPrefix) return uncPrefix + joined
  if (leadingEmpty) return sep + joined
  return joined
}

export function rejectUnsafeProjectPath(
  path: string | undefined | null,
  homedir: string | undefined,
): ProjectPathRejection | null {
  if (path == null) return { key: "project.rejection.none" }
  const raw = path.trim()
  if (!raw) return { key: "project.rejection.none" }

  // Pre-normalization sentinel checks (these catch inputs that only have
  // meaning BEFORE normalization strips them — e.g. lone `.` or `~`).
  if (raw === "." || raw === ".." || raw === "./" || raw === "../") {
    return { key: "project.rejection.invalid" }
  }
  if (raw === "~") {
    return { key: "project.rejection.unexpandedTilde" }
  }

  const p = normalizePath(raw)
  if (!p) return { key: "project.rejection.none" }

  if (p === "." || p === "..") {
    return { key: "project.rejection.invalid" }
  }

  // Unix / macOS root
  if (p === "/") {
    return { key: "project.rejection.filesystemRoot" }
  }

  // Windows drive roots: C:, C:\, C:/, D:\, etc.
  if (/^[a-zA-Z]:[\\/]?$/.test(p)) {
    return { key: "project.rejection.driveRoot" }
  }

  // User's home directory itself + standard "catch-all" subdirectories
  // (Documents, Downloads, Desktop, etc.) that are NOT appropriate as a
  // project root.  Subdirectories inside these are fine.
  if (homedir) {
    const h = normalizePath(homedir).replace(/[\\/]+$/, "")
    const n = p.replace(/[\\/]+$/, "")
    if (n === h) {
      return { key: "project.rejection.homeDir" }
    }
    const forbiddenHomeSubdirs = [
      "Documents",
      "Downloads",
      "Desktop",
      "Library",
      "Applications",
      "Music",
      "Pictures",
      "Movies",
      "Public",
      "Videos",
    ]
    for (const sub of forbiddenHomeSubdirs) {
      if (n === `${h}/${sub}` || n === `${h}\\${sub}`) {
        return { key: "project.rejection.homeSubdir", params: { sub } }
      }
    }
  }

  // Parents of typical home directories (Unix: /Users, /home) + system roots.
  const forbiddenParents = [
    "/Users",
    "/home",
    "/Applications",
    "/System",
    "/Library",
    "/private",
    "/var",
    "/tmp",
    "/etc",
    "/bin",
    "/usr",
    "/opt",
  ]
  const normalized = p.replace(/[\\/]+$/, "")
  if (forbiddenParents.includes(normalized)) {
    return { key: "project.rejection.systemDir" }
  }

  return null
}

/**
 * Minimal shape of the platform API we need. Decoupled from the full
 * `PlatformAPI` interface so this module stays free of UI deps.
 */
export type CanonicalizePlatform = {
  canonicalizeProjectPath?: (path: string) => Promise<string | null>
}

/**
 * Async companion to `rejectUnsafeProjectPath`. Canonicalizes the input
 * via the platform (follows symlinks, resolves `.`/`..` segments with
 * real filesystem truth) BEFORE running the string-level rejection
 * check. Use this at trust-boundary entry points — URL-driven project
 * open, deep-link routing, anywhere the path originates outside the
 * app's own persisted store.
 *
 * Returns:
 *   - `{ ok: true, path: <canonical> }` when the path passed both
 *     canonicalization and the string check.
 *   - `{ ok: false, reason: "unreachable" }` when the path cannot be
 *     canonicalized (missing, permission denied, or no platform
 *     capability — e.g. in a web context without Tauri).
 *   - `{ ok: false, reason: "rejected", rejection }` when the path
 *     resolved but landed in a forbidden location.
 *
 * Callers must handle `unreachable` distinctly from `rejected`: the
 * former is a UX failure to surface ("directory not found / not
 * readable"), the latter is a security outcome ("not a project root").
 */
export type CanonicalizeResult =
  | { ok: true; path: string }
  | { ok: false; reason: "unreachable" }
  | { ok: false; reason: "rejected"; rejection: ProjectPathRejection }

export async function canonicalizeAndReject(
  path: string | undefined | null,
  homedir: string | undefined,
  platform: CanonicalizePlatform,
): Promise<CanonicalizeResult> {
  if (path == null) {
    return { ok: false, reason: "rejected", rejection: { key: "project.rejection.none" } }
  }
  const raw = path.trim()
  if (!raw) {
    return { ok: false, reason: "rejected", rejection: { key: "project.rejection.none" } }
  }

  if (!platform.canonicalizeProjectPath) {
    // Web / missing capability — we have no way to verify. Callers on
    // trust-boundary paths should treat this as a hard-fail.
    return { ok: false, reason: "unreachable" }
  }

  const canonical = await platform.canonicalizeProjectPath(raw).catch(() => null)
  if (!canonical) {
    return { ok: false, reason: "unreachable" }
  }

  const rejection = rejectUnsafeProjectPath(canonical, homedir)
  if (rejection) {
    return { ok: false, reason: "rejected", rejection }
  }

  return { ok: true, path: canonical }
}
