//! Tauri commands that kick off platform-specific installers for the
//! Dependency Manager panel in Settings.
//!
//! Commands never run with elevated privileges. On Linux we refuse to
//! execute anything and instead surface a shell snippet the user can
//! copy-paste themselves. `sudo` is never invoked.

use std::process::Stdio;
use tokio::process::Command;

/// Result returned to the frontend after an install command is spawned.
#[derive(Clone, serde::Serialize, specta::Type)]
#[serde(rename_all = "camelCase")]
pub struct InstallResult {
    /// Whether the installer was launched successfully. This does not
    /// guarantee the install finished — some installers detach and run
    /// out-of-band (e.g. xcode-select's GUI prompt).
    pub launched: bool,
    /// Human-readable message describing what happened.
    pub message: String,
}

impl InstallResult {
    fn ok(message: impl Into<String>) -> Self {
        Self {
            launched: true,
            message: message.into(),
        }
    }
}

/// Kick off git install on macOS by prompting for the Command Line Tools
/// via `xcode-select --install`. This shows the standard OS dialog and
/// does not require sudo.
#[tauri::command]
#[specta::specta]
pub async fn install_git_macos() -> Result<InstallResult, String> {
    if !cfg!(target_os = "macos") {
        return Err("install_git_macos is only available on macOS".to_string());
    }

    let output = Command::new("xcode-select")
        .arg("--install")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .output()
        .await
        .map_err(|e| format!("Failed to run xcode-select: {e}"))?;

    let stderr = String::from_utf8_lossy(&output.stderr);
    let stdout = String::from_utf8_lossy(&output.stdout);

    // Already installed → xcode-select exits non-zero with a specific
    // message. We still treat this as a "launched" success because the
    // user's git install is effectively already done.
    if !output.status.success() {
        let combined = format!("{stderr}{stdout}").to_lowercase();
        if combined.contains("already installed") || combined.contains("command line tools are already") {
            return Ok(InstallResult::ok(
                "Xcode Command Line Tools are already installed.",
            ));
        }
        return Err(format!("xcode-select exited with error: {stderr}"));
    }

    Ok(InstallResult::ok(
        "Launched macOS Command Line Tools installer. A system dialog will guide the install.",
    ))
}

/// Kick off git install on Windows using winget. Runs non-elevated —
/// winget will prompt for UAC if needed.
#[tauri::command]
#[specta::specta]
pub async fn install_git_windows() -> Result<InstallResult, String> {
    if !cfg!(target_os = "windows") {
        return Err("install_git_windows is only available on Windows".to_string());
    }

    let output = Command::new("winget")
        .args([
            "install",
            "--id",
            "Git.Git",
            "-e",
            "--source",
            "winget",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .output()
        .await
        .map_err(|e| format!("Failed to run winget: {e}"))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();

    if !output.status.success() {
        return Err(format!(
            "winget exited with error.\nstdout: {stdout}\nstderr: {stderr}"
        ));
    }

    Ok(InstallResult::ok("winget completed git installation."))
}

/// Linux: we never execute package managers. The frontend surfaces a
/// copyable shell snippet and this command simply reports which command
/// was presented (kept for parity with the Win/macOS commands).
#[tauri::command]
#[specta::specta]
pub fn linux_install_hint(tool: String) -> String {
    match tool.as_str() {
        "git" => "sudo apt install git".to_string(),
        "python" => "sudo apt install python3 python3-venv".to_string(),
        "python-venv" => "sudo apt install python3-venv".to_string(),
        "latex" => "sudo apt install texlive-latex-recommended texlive-latex-extra".to_string(),
        "tectonic" => "See https://tectonic-typesetting.github.io/en-US/install.html".to_string(),
        "pdf-tools" => "sudo apt install poppler-utils qpdf".to_string(),
        _ => "".to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // --- linux_install_hint ---

    #[test]
    fn known_tool_git_returns_nonempty_hint() {
        let hint = linux_install_hint("git".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'git', got empty string");
        assert!(hint.contains("git"), "expected hint to mention 'git', got: {hint:?}");
    }

    #[test]
    fn known_tool_python_returns_nonempty_hint() {
        let hint = linux_install_hint("python".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'python'");
        assert!(hint.contains("python3"), "expected hint to mention 'python3', got: {hint:?}");
    }

    #[test]
    fn known_tool_python_venv_returns_nonempty_hint() {
        let hint = linux_install_hint("python-venv".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'python-venv'");
        assert!(hint.contains("python3-venv"), "expected hint to mention 'python3-venv', got: {hint:?}");
    }

    #[test]
    fn known_tool_latex_returns_nonempty_hint() {
        let hint = linux_install_hint("latex".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'latex'");
        assert!(hint.contains("texlive"), "expected hint to mention 'texlive', got: {hint:?}");
    }

    #[test]
    fn known_tool_tectonic_returns_nonempty_hint() {
        let hint = linux_install_hint("tectonic".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'tectonic'");
        assert!(hint.contains("tectonic"), "expected hint to mention 'tectonic', got: {hint:?}");
    }

    #[test]
    fn known_tool_pdf_tools_returns_nonempty_hint() {
        let hint = linux_install_hint("pdf-tools".to_string());
        assert!(!hint.is_empty(), "expected a non-empty hint for 'pdf-tools'");
        assert!(hint.contains("poppler"), "expected hint to mention 'poppler', got: {hint:?}");
    }

    #[test]
    fn unknown_tool_returns_empty_string() {
        let hint = linux_install_hint("nonexistent-tool".to_string());
        assert!(hint.is_empty(), "expected empty string for unknown tool, got: {hint:?}");
    }

    #[test]
    fn unknown_tool_empty_string_returns_empty() {
        let hint = linux_install_hint("".to_string());
        assert!(hint.is_empty(), "expected empty string for empty tool name, got: {hint:?}");
    }

    #[test]
    fn tool_lookup_is_case_sensitive() {
        // "Git" (capital G) is not a registered key — should return ""
        let hint_upper = linux_install_hint("Git".to_string());
        let hint_lower = linux_install_hint("git".to_string());
        assert!(hint_upper.is_empty(), "expected empty for 'Git' (wrong case), got: {hint_upper:?}");
        assert!(!hint_lower.is_empty(), "expected non-empty for 'git', got: {hint_lower:?}");
    }
}
