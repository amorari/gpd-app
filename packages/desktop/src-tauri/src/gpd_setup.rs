//! GPD first-run orchestration.
//!
//! On first launch:
//! 1. Provisions Python via bundled `uv` (or finds system Python >= 3.11)
//! 2. Creates a GPD venv and installs `get-physics-done[arxiv]`
//! 3. Runs `gpd install opencode --global` to deploy commands, agents, docs
//! 4. Injects LiteLLM provider config into opencode.json
//! 5. Writes .gpd-initialized marker
//!
//! MCP servers run locally via real Python from the venv.
//! Subsequent launches skip all of this (marker file check).

use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;
use tauri::{AppHandle, Manager};
use tokio::process::Command;
use tokio::time::timeout;

/// GPD config directory name under ~/.config/
const GPD_CONFIG_DIR_NAME: &str = "gpd";

/// Marker file written after successful first-run setup
const GPD_INIT_MARKER: &str = ".gpd-initialized";

/// LiteLLM proxy URL
const LITELLM_URL: &str = "https://litellm-production-46bb.up.railway.app/v1";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Builds the OPENCODE_CONFIG_CONTENT JSON with provider config and
/// MCP server definitions pointing to the venv Python interpreter.
pub fn build_config_json() -> String {
    let python = gpd_python();
    // Escape backslashes for JSON string embedding (Windows paths contain `\`).
    // Without this, `\U`, `\v`, `\S`, etc. in paths like
    // `C:\Users\foo\.config\gpd\.venv\Scripts\python.exe` are parsed as invalid
    // JSON escape sequences and the entire OPENCODE_CONFIG_CONTENT is rejected.
    let p = python.to_string_lossy().replace('\\', "\\\\");

    let mcp_servers = format!(r#"{{
        "gpd-conventions": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.conventions_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-errors": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.errors_mcp"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-patterns": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.patterns_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-protocols": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.protocols_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-skills": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.skills_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-state": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.state_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-verification": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.verification_server"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-arxiv": {{"type":"local","command":["{p}","-m","gpd.mcp.servers.arxiv_bridge"],"enabled":true}}
    }}"#);

    let m = r#""modalities":{"input":["text","image","pdf"],"output":["text"]}"#;
    let mg = r#""modalities":{"input":["text","image","pdf","video","audio"],"output":["text"]}"#;
    let mt = r#""modalities":{"input":["text"],"output":["text"]}"#;
    format!(r#"{{"provider":{{"gpd":{{"name":"GPD (PSI)","api":"{url}","env":["GPD_API_KEY"],"models":{{"claude-opus-4-6":{{"name":"Claude Opus 4.6","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":131072}}}},"claude-sonnet-4-6":{{"name":"Claude Sonnet 4.6","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":65536}}}},"claude-haiku-4-5":{{"name":"Claude Haiku 4.5","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":200000,"output":65536}}}},"gpt-5.4":{{"name":"GPT-5.4","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-mini":{{"name":"GPT-5.4 mini","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-nano":{{"name":"GPT-5.4 nano","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-pro":{{"name":"GPT-5.4 Pro","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1050000,"output":131072}}}},"gpt-5.3-codex":{{"name":"GPT-5.3 Codex","tool_call":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":32768}}}},"gpt-4.1":{{"name":"GPT-4.1","tool_call":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":32768}}}},"gpt-4.1-mini":{{"name":"GPT-4.1 mini","tool_call":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":32768}}}},"o4-mini":{{"name":"o4-mini (reasoning)","tool_call":true,"reasoning":true,"temperature":true,{mt},"limit":{{"context":200000,"output":100000}}}},"gemini-3.1-pro-preview":{{"name":"Gemini 3.1 Pro","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{mg},"limit":{{"context":1000000,"output":65536}}}},"gemini-3-flash-preview":{{"name":"Gemini 3 Flash","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,{mg},"limit":{{"context":1000000,"output":65536}}}},"gemini-3.1-flash-lite-preview":{{"name":"Gemini 3.1 Flash-Lite","tool_call":true,"attachment":true,"temperature":true,{m},"limit":{{"context":1000000,"output":65536}}}}}}}}}},"model":"gpd/claude-sonnet-4-6","enabled_providers":["gpd"],"mcp":{mcp}}}"#,
        url = LITELLM_URL,
        mcp = mcp_servers,
    )
}

/// Returns the GPD config directory path (~/.config/gpd/)
pub fn config_dir() -> PathBuf {
    let config_home = std::env::var_os("XDG_CONFIG_HOME")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            dirs::home_dir()
                .expect("cannot determine home directory")
                .join(".config")
        });
    config_home.join(GPD_CONFIG_DIR_NAME)
}

/// Returns true if GPD has already been initialized
pub fn is_initialized() -> bool {
    config_dir().join(GPD_INIT_MARKER).exists()
}

/// Returns true when the GPD venv is present and usable.
///
/// All three of the following must hold:
/// 1. The venv Python binary exists on disk.
/// 2. That binary can execute `import gpd; print('ok')` within 5 seconds.
/// 3. The `.gpd-initialized` marker file exists.
///
/// The function is intentionally synchronous-looking from the caller's
/// perspective because it blocks until the probe completes or times out.
pub async fn is_venv_valid() -> bool {
    let marker = config_dir().join(GPD_INIT_MARKER);
    if !marker.exists() {
        return false;
    }

    let python = gpd_python();
    if !python.exists() {
        return false;
    }

    let result = timeout(
        Duration::from_secs(5),
        Command::new(&python)
            .args(["-c", "import gpd; print('ok')"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await;

    match result {
        Ok(Ok(output)) => output.status.success(),
        _ => false,
    }
}

/// Tauri command: delete the init marker and re-run first-run setup.
///
/// Only the `.venv` directory is removed so project files in
/// `~/.config/gpd/` are preserved. Emits progress via the existing
/// `GpdFirstRunComplete` event when done.
#[tauri::command]
#[specta::specta]
pub async fn repair_gpd_venv(app: tauri::AppHandle) -> Result<(), String> {
    let config = config_dir();
    let marker = config.join(GPD_INIT_MARKER);
    let venv = gpd_venv_dir();

    tracing::info!("Repair requested: removing GPD venv and init marker");

    // Remove the venv directory (not other project files).
    if venv.exists() {
        std::fs::remove_dir_all(&venv)
            .map_err(|e| format!("Failed to remove GPD venv: {e}"))?;
        tracing::info!("Removed GPD venv at {}", venv.display());
    }

    // Remove the marker so the setup is unconditionally re-run.
    if marker.exists() {
        std::fs::remove_file(&marker)
            .map_err(|e| format!("Failed to remove init marker: {e}"))?;
    }

    run_first_setup(app).await
}

/// Run the full GPD first-run setup. Non-fatal — errors are logged,
/// and the marker file is only written on full success (retry next launch).
pub async fn run_first_setup(app: AppHandle) -> Result<(), String> {
    let config = config_dir();
    let uv = uv_path(&app)?;

    if !uv.exists() {
        return Err(format!("Bundled uv not found at {}", uv.display()));
    }

    std::fs::create_dir_all(&config)
        .map_err(|e| format!("Failed to create config dir: {e}"))?;

    tracing::info!(
        config = %config.display(),
        uv = %uv.display(),
        "Starting GPD first-run setup"
    );

    // Step 1: Ensure Python >= 3.11 is available
    let python = ensure_python(&uv).await?;

    // Step 2: Create GPD venv and install get-physics-done
    ensure_gpd_installed(&uv, &python).await?;

    // Step 3: Install commands, agents, reference docs
    run_gpd_install(&config).await?;

    // Step 4: Inject LiteLLM provider config
    inject_provider_config(&config)?;

    // Step 5: Mark as initialized
    let marker = config.join(GPD_INIT_MARKER);
    std::fs::write(&marker, "initialized")
        .map_err(|e| format!("Failed to write init marker: {e}"))?;

    tracing::info!("GPD first-run setup completed");
    Ok(())
}

// ---------------------------------------------------------------------------
// Python provisioning
// ---------------------------------------------------------------------------

/// Returns the path to the bundled uv binary in the app's resources
fn uv_path(app: &AppHandle) -> Result<PathBuf, String> {
    let bin_name = if cfg!(windows) { "uv.exe" } else { "uv" };
    app.path()
        .resolve(format!("uv-bundle/{bin_name}"), tauri::path::BaseDirectory::Resource)
        .map_err(|e| format!("Failed to resolve uv path: {e}"))
}

/// GPD venv location: ~/.config/gpd/.venv/
fn gpd_venv_dir() -> PathBuf {
    config_dir().join(".venv")
}

/// The Python interpreter inside the GPD venv
fn gpd_python() -> PathBuf {
    let venv = gpd_venv_dir();
    if cfg!(windows) {
        venv.join("Scripts").join("python.exe")
    } else {
        venv.join("bin").join("python")
    }
}

/// Ensure a Python >= 3.11 interpreter is available.
/// First checks system Python. If none found, uses bundled uv to install one.
async fn ensure_python(uv: &Path) -> Result<PathBuf, String> {
    // Try system python3 first
    let python_cmd = if cfg!(windows) { "python" } else { "python3" };
    if let Ok(output) = Command::new(python_cmd)
        .args(["--version"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .output()
        .await
    {
        if output.status.success() {
            let version = String::from_utf8_lossy(&output.stdout);
            if is_python_3_11_or_later(&version) {
                tracing::info!("Using system Python: {}", version.trim());
                return Ok(PathBuf::from(python_cmd));
            }
        }
    }

    // No suitable system Python — install via uv
    tracing::info!("No system Python >= 3.11 found, installing via uv");

    let output = timeout(
        Duration::from_secs(120),
        Command::new(uv)
            .args(["python", "install", "3.12", "--quiet"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await
    .map_err(|_| "uv python install timed out (120s)".to_string())?
    .map_err(|e| format!("Failed to run uv python install: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("uv python install failed: {stderr}"));
    }

    // Locate the installed interpreter
    let find_output = Command::new(uv)
        .args(["python", "find", "3.12"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .stdin(Stdio::null())
        .output()
        .await
        .map_err(|e| format!("uv python find failed: {e}"))?;

    let python_path = String::from_utf8_lossy(&find_output.stdout).trim().to_string();
    if python_path.is_empty() {
        return Err("uv python find returned empty path".to_string());
    }

    tracing::info!("uv-provisioned Python at: {python_path}");
    Ok(PathBuf::from(python_path))
}

fn is_python_3_11_or_later(version_output: &str) -> bool {
    let trimmed = version_output.trim();
    if let Some(rest) = trimmed.strip_prefix("Python ") {
        let parts: Vec<&str> = rest.split('.').collect();
        if parts.len() >= 2 {
            if let (Ok(3), Ok(minor)) = (parts[0].parse::<u32>(), parts[1].parse::<u32>()) {
                return minor >= 11;
            }
        }
    }
    false
}

// ---------------------------------------------------------------------------
// GPD package installation
// ---------------------------------------------------------------------------

/// Create a dedicated GPD venv and install get-physics-done into it.
async fn ensure_gpd_installed(uv: &Path, python: &Path) -> Result<(), String> {
    let venv = gpd_venv_dir();

    if !venv.exists() {
        tracing::info!("Creating GPD venv at {}", venv.display());

        let output = timeout(
            Duration::from_secs(30),
            Command::new(uv)
                .args(["venv", &venv.to_string_lossy(), "-p", &python.to_string_lossy()])
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .stdin(Stdio::null())
                .output(),
        )
        .await
        .map_err(|_| "uv venv creation timed out (30s)".to_string())?
        .map_err(|e| format!("Failed to create venv: {e}"))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("uv venv creation failed: {stderr}"));
        }
    }

    tracing::info!("Installing get-physics-done[arxiv] into GPD venv");

    let output = timeout(
        Duration::from_secs(300),
        Command::new(uv)
            .args([
                "pip", "install",
                "get-physics-done[arxiv] @ git+https://github.com/psi-oss/get-physics-done.git@main",
                "-p", &gpd_python().to_string_lossy(),
                "--quiet",
            ])
            .env("UV_HTTP_TIMEOUT", "120")
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await
    .map_err(|_| "GPD pip install timed out (180s)".to_string())?
    .map_err(|e| format!("Failed to install get-physics-done: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("GPD pip install failed: {stderr}"));
    }

    tracing::info!("get-physics-done installed successfully");

    // Symlink the bundled uv into the GPD config bin directory so the agent
    // can use `uv` to create per-project venvs and install packages on demand.
    // This way professors get project-level isolation (e.g., one project with
    // scipy, another with scikit-learn) without polluting the global GPD venv.
    let gpd_bin = config_dir().join("bin");
    let _ = std::fs::create_dir_all(&gpd_bin);
    let uv_link = gpd_bin.join("uv");
    if !uv_link.exists() {
        #[cfg(unix)]
        {
            let _ = std::os::unix::fs::symlink(uv, &uv_link);
            tracing::info!(link = %uv_link.display(), target = %uv.display(), "Symlinked uv into GPD bin");
        }
        #[cfg(windows)]
        {
            let _ = std::fs::copy(uv, &uv_link);
            tracing::info!(link = %uv_link.display(), "Copied uv into GPD bin");
        }
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// GPD command/agent installation
// ---------------------------------------------------------------------------

/// Run `gpd install opencode --global` using the venv Python.
async fn run_gpd_install(config: &Path) -> Result<(), String> {
    let python = gpd_python();

    tracing::info!("Running gpd install opencode --global --skip-readiness-check");

    let output = timeout(
        Duration::from_secs(60),
        Command::new(&python)
            .args(["-m", "gpd.cli", "install", "opencode", "--global", "--skip-readiness-check"])
            .env("OPENCODE_CONFIG_DIR", config)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await
    .map_err(|_| "gpd install timed out (60s)".to_string())?
    .map_err(|e| format!("Failed to run gpd install: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("gpd install opencode failed: {stderr}"));
    }

    tracing::info!("gpd install opencode completed");
    Ok(())
}

// ---------------------------------------------------------------------------
// Provider config injection
// ---------------------------------------------------------------------------

fn inject_provider_config(config: &Path) -> Result<(), String> {
    let path = config.join("opencode.json");

    let mut config_val: serde_json::Value = if path.exists() {
        let content = std::fs::read_to_string(&path)
            .map_err(|e| format!("Failed to read opencode.json: {e}"))?;
        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse opencode.json: {e}"))?
    } else {
        serde_json::json!({})
    };

    if let Some(obj) = config_val.as_object_mut() {
        // Add provider
        let provider = obj.entry("provider").or_insert_with(|| serde_json::json!({}));
        if let Some(provider_obj) = provider.as_object_mut() {
            provider_obj.insert("gpd".to_string(), serde_json::json!({
                "name": "GPD (PSI)",
                "api": LITELLM_URL,
                "env": ["GPD_API_KEY"],
                "models": {
                    "claude-opus-4-6": { "name": "Claude Opus 4.6", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 131072 } },
                    "claude-sonnet-4-6": { "name": "Claude Sonnet 4.6", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 65536 } },
                    "claude-haiku-4-5": { "name": "Claude Haiku 4.5", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 200000, "output": 65536 } },
                    "gpt-5.4": { "name": "GPT-5.4", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-mini": { "name": "GPT-5.4 mini", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-nano": { "name": "GPT-5.4 nano", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-pro": { "name": "GPT-5.4 Pro", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.3-codex": { "name": "GPT-5.3 Codex", "tool_call": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 32768 } },
                    "gpt-4.1": { "name": "GPT-4.1", "tool_call": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 32768 } },
                    "gpt-4.1-mini": { "name": "GPT-4.1 mini", "tool_call": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 32768 } },
                    "o4-mini": { "name": "o4-mini (reasoning)", "tool_call": true, "reasoning": true, "temperature": true, "modalities": { "input": ["text"], "output": ["text"] }, "limit": { "context": 200000, "output": 100000 } },
                    "gemini-3.1-pro-preview": { "name": "Gemini 3.1 Pro", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf", "video", "audio"], "output": ["text"] }, "limit": { "context": 1000000, "output": 65536 } },
                    "gemini-3-flash-preview": { "name": "Gemini 3 Flash", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf", "video", "audio"], "output": ["text"] }, "limit": { "context": 1000000, "output": 65536 } },
                    "gemini-3.1-flash-lite-preview": { "name": "Gemini 3.1 Flash-Lite", "tool_call": true, "attachment": true, "temperature": true, "modalities": { "input": ["text", "image", "pdf"], "output": ["text"] }, "limit": { "context": 1000000, "output": 65536 } }
                }
            }));
        }

        // Set default model
        obj.insert("model".to_string(), serde_json::json!("gpd/claude-sonnet-4-6"));

        // Only show GPD provider
        obj.insert("enabled_providers".to_string(), serde_json::json!(["gpd"]));

        // Auto-approve all permissions (professors shouldn't see permission prompts)
        obj.insert("permission".to_string(), serde_json::json!("allow"));

        // Overwrite MCP server entries with the correct venv Python path.
        // `gpd install opencode` may write MCP entries pointing to an older
        // Python venv (e.g. ~/.gpd/venv). We always use our managed venv
        // at ~/.config/gpd/.venv/ which has the latest GPD + arxiv packages.
        let python = gpd_python();
        let p = python.to_string_lossy();
        let mcp_json: serde_json::Value = serde_json::json!({
            "gpd-conventions": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.conventions_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-errors": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.errors_mcp"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-patterns": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.patterns_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-protocols": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.protocols_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-skills": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.skills_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-state": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.state_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-verification": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.verification_server"],"enabled":true,"environment":{"LOG_LEVEL":"WARNING"}},
            "gpd-arxiv": {"type":"local","command":[&*p,"-m","gpd.mcp.servers.arxiv_bridge"],"enabled":true}
        });
        obj.insert("mcp".to_string(), mcp_json);
    }

    let json_str = serde_json::to_string_pretty(&config_val)
        .map_err(|e| format!("Failed to serialize opencode.json: {e}"))?;
    std::fs::write(&path, format!("{json_str}\n"))
        .map_err(|e| format!("Failed to write opencode.json: {e}"))?;

    tracing::info!(path = %path.display(), "Injected LiteLLM provider config");
    Ok(())
}

// ---------------------------------------------------------------------------
// Tests — run with `cargo test -p opencode-desktop`
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_config_json_is_valid_json() {
        let json = build_config_json();
        let parsed: serde_json::Value =
            serde_json::from_str(&json).expect("build_config_json() produced invalid JSON");

        // Verify top-level structure
        let obj = parsed.as_object().expect("config should be an object");
        assert!(obj.contains_key("provider"), "missing 'provider' key");
        assert!(obj.contains_key("model"), "missing 'model' key");
        assert!(obj.contains_key("enabled_providers"), "missing 'enabled_providers' key");
        assert!(obj.contains_key("mcp"), "missing 'mcp' key");
    }

    #[test]
    fn build_config_json_has_all_14_models() {
        let json = build_config_json();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let models = parsed["provider"]["gpd"]["models"].as_object().unwrap();
        assert_eq!(models.len(), 14, "expected 14 models, got {}", models.len());

        let expected = [
            "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5",
            "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4-pro",
            "gpt-5.3-codex", "gpt-4.1", "gpt-4.1-mini", "o4-mini",
            "gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-3.1-flash-lite-preview",
        ];
        for name in &expected {
            assert!(models.contains_key(*name), "missing model: {name}");
        }
    }

    #[test]
    fn build_config_json_has_8_mcp_servers() {
        let json = build_config_json();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let mcp = parsed["mcp"].as_object().unwrap();
        assert_eq!(mcp.len(), 8, "expected 8 MCP servers, got {}", mcp.len());

        let expected = [
            "gpd-conventions", "gpd-errors", "gpd-patterns", "gpd-protocols",
            "gpd-skills", "gpd-state", "gpd-verification", "gpd-arxiv",
        ];
        for name in &expected {
            assert!(mcp.contains_key(*name), "missing MCP server: {name}");
        }
    }

    #[test]
    fn build_config_json_mcp_paths_use_gpd_venv() {
        let json = build_config_json();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let mcp = parsed["mcp"].as_object().unwrap();
        let expected_python = gpd_python().to_string_lossy().to_string();

        for (name, cfg) in mcp {
            let cmd = cfg["command"].as_array()
                .unwrap_or_else(|| panic!("MCP server {name} missing 'command' array"));
            let python_path = cmd[0].as_str()
                .unwrap_or_else(|| panic!("MCP server {name} command[0] is not a string"));
            assert_eq!(python_path, expected_python,
                "MCP server {name} uses wrong Python: {python_path}");
        }
    }

    /// Verify that `is_venv_valid` returns false when the expected Python
    /// binary does not exist.  We override the venv lookup by checking that
    /// `gpd_python()` points to a path that does not exist on a clean CI
    /// runner (the real venv is never present in unit-test contexts).
    #[tokio::test]
    async fn is_venv_valid_returns_false_when_binary_missing() {
        // The marker file won't exist in CI either, so this exercises the
        // "binary missing" path. Either way the function must return false.
        let result = is_venv_valid().await;
        // In a CI environment neither the marker nor the binary exist, so the
        // result is definitely false. On a developer machine with a real GPD
        // install the result could be true — but the important invariant is
        // that a *non-existent* binary always produces false.
        let python = gpd_python();
        if !python.exists() {
            assert!(!result, "is_venv_valid should be false when Python binary is absent");
        }
    }

    #[test]
    fn build_config_json_provider_name_is_gpd() {
        let json = build_config_json();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let name = parsed["provider"]["gpd"]["name"].as_str().unwrap();
        assert_eq!(name, "GPD (PSI)");
        assert!(!json.contains("OpenCode"), "config JSON must not contain 'OpenCode'");
    }

    #[test]
    fn build_config_json_model_values_are_valid() {
        // Verify every model has parseable nested objects (catches format string
        // escaping bugs like {{"input":...}} which produce invalid JSON)
        let json = build_config_json();
        let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
        let models = parsed["provider"]["gpd"]["models"].as_object().unwrap();
        for (name, model) in models {
            assert!(model["name"].is_string(), "model {name} missing 'name'");
            assert!(model["limit"].is_object(), "model {name} missing 'limit' object");
            let limit = model["limit"].as_object().unwrap();
            assert!(limit["context"].is_number(), "model {name} limit missing 'context'");
            assert!(limit["output"].is_number(), "model {name} limit missing 'output'");
        }
    }
}
