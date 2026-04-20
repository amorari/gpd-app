/**
 * Guard against opening dangerous directories as GPD projects.
 *
 * Returns an error string if the path is unsafe, otherwise `null`.
 * Callers should refuse to open the project and surface the error to the user.
 */
export function rejectUnsafeProjectPath(path: string | undefined | null, homedir: string | undefined): string | null {
  if (path == null) return "No directory selected."
  const p = path.trim()
  if (!p) return "No directory selected."

  if (p === "." || p === "..") {
    return "That directory can't be opened as a project."
  }

  // Unix / macOS root
  if (p === "/") {
    return "The filesystem root (/) cannot be opened as a project."
  }

  // Windows drive roots: C:\, C:/, D:\, etc.
  if (/^[a-zA-Z]:[\\/]?$/.test(p)) {
    return "A drive root cannot be opened as a project."
  }

  // Unexpanded tilde
  if (p === "~") {
    return "Please choose a specific project folder, not your home directory."
  }

  // User's home directory itself
  if (homedir) {
    const h = homedir.replace(/[\\/]+$/, "")
    const n = p.replace(/[\\/]+$/, "")
    if (n === h) {
      return "Please choose a specific project folder, not your home directory."
    }
  }

  // Parents of typical home directories (Unix: /Users, /home)
  const forbiddenParents = ["/Users", "/home", "/Applications", "/System", "/Library", "/private", "/var", "/tmp", "/etc", "/bin", "/usr", "/opt"]
  const normalized = p.replace(/[\\/]+$/, "")
  if (forbiddenParents.includes(normalized)) {
    return "That system directory cannot be opened as a project."
  }

  return null
}
