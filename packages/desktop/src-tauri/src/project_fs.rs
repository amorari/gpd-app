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
        return Err("Project name cannot contain path separators.".to_string());
    }
    if trimmed == "." || trimmed == ".." {
        return Err("Project name cannot be `.` or `..`.".to_string());
    }

    let parent_path = PathBuf::from(&parent);
    if !parent_path.is_dir() {
        return Err(format!("Parent folder does not exist: {parent}"));
    }

    let target = parent_path.join(trimmed);
    if target.exists() {
        return Err(format!(
            "A file or folder named `{trimmed}` already exists in that location."
        ));
    }

    std::fs::create_dir(&target)
        .map_err(|e| format!("Failed to create `{}`: {e}", target.display()))?;

    Ok(target.to_string_lossy().to_string())
}
