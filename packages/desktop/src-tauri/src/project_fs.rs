//! Filesystem helpers for the "Create New Project" flow.
//!
//! Creates a new directory under a chosen parent. Refuses to overwrite an
//! existing directory so we don't clobber user data.

use std::path::PathBuf;

#[tauri::command]
#[specta::specta]
pub fn create_project_directory(parent: String, name: String) -> Result<String, String> {
    let trimmed = name.trim();
    if trimmed.is_empty() {
        return Err("Project name cannot be empty.".to_string());
    }
    if trimmed.contains('/') || trimmed.contains('\\') {
        return Err("Project name can't contain / or \\ characters.".to_string());
    }
    if trimmed == "." || trimmed == ".." {
        return Err("Project name can't be `.` or `..`.".to_string());
    }

    let parent_path = PathBuf::from(&parent);
    if !parent_path.is_dir() {
        return Err(format!("The folder {parent} doesn't exist. Choose another location."));
    }

    let target = parent_path.join(trimmed);
    if target.exists() {
        return Err(format!(
            "A file or folder named `{trimmed}` already exists in that location. Choose a different name."
        ));
    }

    std::fs::create_dir(&target)
        .map_err(|e| format!("Couldn't create the folder {}. Check permissions and disk space. ({e})", target.display()))?;

    Ok(target.to_string_lossy().to_string())
}

/// Reports whether the main app process can read the given project folder.
///
/// Used by the macOS TCC flow: the Tauri main process is the "responsible
/// process" for TCC attribution, so running the probe here (rather than in
/// the sidecar) lets the OS correctly attribute a subsequent NSOpenPanel
/// grant to the signed app bundle. The sidecar inherits the grant via
/// process-parentage.
///
/// Returns:
///   - `Ok("ok")` when the directory exists and is readable
///   - `Ok("locked")` when macOS (or another OS) denies access (EACCES/EPERM)
///   - `Ok("missing")` when the path doesn't exist
///   - `Err(...)` for any other failure the UI should surface
#[tauri::command]
#[specta::specta]
pub fn check_project_accessible(path: String) -> Result<String, String> {
    let p = PathBuf::from(&path);
    match std::fs::read_dir(&p) {
        Ok(_) => Ok("ok".to_string()),
        Err(err) => {
            use std::io::ErrorKind;
            match err.kind() {
                ErrorKind::PermissionDenied => Ok("locked".to_string()),
                ErrorKind::NotFound => Ok("missing".to_string()),
                _ => {
                    let os_code = err.raw_os_error().unwrap_or(0);
                    // macOS EPERM (1) is surfaced as `Other` by Rust, not
                    // `PermissionDenied`, so check the raw errno as well.
                    if os_code == 1 || os_code == 13 {
                        return Ok("locked".to_string());
                    }
                    Err(format!("{err}"))
                }
            }
        }
    }
}
