/**
 * Guard against opening dangerous directories as GPD projects.
 *
 * Returns a translation descriptor if the path is unsafe, otherwise `null`.
 * Callers should refuse to open the project and surface the rejection via
 * `language.t(result.key, result.params)`.  Truthiness-only callers can use
 * `!!rejectUnsafeProjectPath(...)`.
 */
export type ProjectPathRejection = {
  key: string
  params?: Record<string, string>
}

export function rejectUnsafeProjectPath(
  path: string | undefined | null,
  homedir: string | undefined,
): ProjectPathRejection | null {
  if (path == null) return { key: "project.rejection.none" }
  const p = path.trim()
  if (!p) return { key: "project.rejection.none" }

  if (p === "." || p === "..") {
    return { key: "project.rejection.invalid" }
  }

  // Unix / macOS root
  if (p === "/") {
    return { key: "project.rejection.filesystemRoot" }
  }

  // Windows drive roots: C:\, C:/, D:\, etc.
  if (/^[a-zA-Z]:[\\/]?$/.test(p)) {
    return { key: "project.rejection.driveRoot" }
  }

  // Unexpanded tilde
  if (p === "~") {
    return { key: "project.rejection.unexpandedTilde" }
  }

  // User's home directory itself + standard "catch-all" subdirectories
  // (Documents, Downloads, Desktop, etc.) that are NOT appropriate as a
  // project root.  Subdirectories inside these are fine.
  if (homedir) {
    const h = homedir.replace(/[\\/]+$/, "")
    const n = p.replace(/[\\/]+$/, "")
    if (n === h) {
      return { key: "project.rejection.homeDir" }
    }
    const forbiddenHomeSubdirs = [
      "Documents", "Downloads", "Desktop", "Library", "Applications",
      "Music", "Pictures", "Movies", "Public", "Videos",
    ]
    for (const sub of forbiddenHomeSubdirs) {
      if (n === `${h}/${sub}` || n === `${h}\\${sub}`) {
        return { key: "project.rejection.homeSubdir", params: { sub } }
      }
    }
  }

  // Parents of typical home directories (Unix: /Users, /home)
  const forbiddenParents = ["/Users", "/home", "/Applications", "/System", "/Library", "/private", "/var", "/tmp", "/etc", "/bin", "/usr", "/opt"]
  const normalized = p.replace(/[\\/]+$/, "")
  if (forbiddenParents.includes(normalized)) {
    return { key: "project.rejection.systemDir" }
  }

  return null
}
