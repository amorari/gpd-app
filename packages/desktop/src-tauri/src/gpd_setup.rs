//! GPD first-run orchestration.
//!
//! On first launch, runs the GPD sidecar to install commands, agents,
//! MCP servers, and LiteLLM provider config into the GPD config directory.
//! Subsequent launches skip this entirely (marker file check).

use std::path::PathBuf;
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

/// Builds the OPENCODE_CONFIG_CONTENT JSON with both provider config and
/// MCP server definitions pointing to the bundled sidecar binary.
pub fn build_config_json(app: &tauri::AppHandle) -> String {
    let sidecar = sidecar_path(app).unwrap_or_default();
    let sidecar_str = sidecar.to_string_lossy();

    // MCP servers - each launched via the sidecar's install subcommand
    // The sidecar binary contains all MCP server modules via PyInstaller
    let mcp_servers = format!(r#"{{
        "gpd-conventions": {{"type":"local","command":["{s}","mcp-serve","conventions"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-errors": {{"type":"local","command":["{s}","mcp-serve","errors"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-patterns": {{"type":"local","command":["{s}","mcp-serve","patterns"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-protocols": {{"type":"local","command":["{s}","mcp-serve","protocols"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-skills": {{"type":"local","command":["{s}","mcp-serve","skills"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-state": {{"type":"local","command":["{s}","mcp-serve","state"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-verification": {{"type":"local","command":["{s}","mcp-serve","verification"],"enabled":true,"environment":{{"LOG_LEVEL":"WARNING"}}}},
        "gpd-arxiv": {{"type":"local","command":["{s}","mcp-serve","arxiv"],"enabled":true}}
    }}"#, s = sidecar_str);

    format!(r#"{{"provider":{{"gpd":{{"name":"GPD (PSI)","api":"{url}","env":["GPD_API_KEY"],"models":{{"claude-opus-4-6":{{"name":"Claude Opus 4.6","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":131072}}}},"claude-sonnet-4-6":{{"name":"Claude Sonnet 4.6","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":65536}}}},"claude-haiku-4-5":{{"name":"Claude Haiku 4.5","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":200000,"output":65536}}}},"gpt-5.4":{{"name":"GPT-5.4","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-mini":{{"name":"GPT-5.4 mini","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-nano":{{"name":"GPT-5.4 nano","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1050000,"output":131072}}}},"gpt-5.4-pro":{{"name":"GPT-5.4 Pro","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1050000,"output":131072}}}},"gpt-5.3-codex":{{"name":"GPT-5.3 Codex","tool_call":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":32768}}}},"gpt-4.1":{{"name":"GPT-4.1","tool_call":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":32768}}}},"gpt-4.1-mini":{{"name":"GPT-4.1 mini","tool_call":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":32768}}}},"o4-mini":{{"name":"o4-mini (reasoning)","tool_call":true,"reasoning":true,"temperature":true,"limit":{{"context":200000,"output":100000}}}},"gemini-3.1-pro-preview":{{"name":"Gemini 3.1 Pro","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":65536}}}},"gemini-3-flash-preview":{{"name":"Gemini 3 Flash","tool_call":true,"reasoning":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":65536}}}},"gemini-3.1-flash-lite-preview":{{"name":"Gemini 3.1 Flash-Lite","tool_call":true,"attachment":true,"temperature":true,"limit":{{"context":1000000,"output":65536}}}}}}}}}},"model":"gpd/claude-sonnet-4-6","enabled_providers":["gpd"],"mcp":{mcp}}}"#,
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

/// Returns the path to the gpd-sidecar binary in the app's resources
fn sidecar_path(app: &AppHandle) -> Result<PathBuf, String> {
    app.path()
        .resolve("gpd-sidecar-bundle/gpd-sidecar", tauri::path::BaseDirectory::Resource)
        .map_err(|e| format!("Failed to resolve GPD sidecar path: {e}"))
}

/// Run the full GPD first-run setup. Non-fatal — errors are logged,
/// and the marker file is only written on full success (retry next launch).
pub async fn run_first_setup(app: AppHandle) -> Result<(), String> {
    let config = config_dir();
    let sidecar = sidecar_path(&app)?;

    if !sidecar.exists() {
        return Err(format!("GPD sidecar not found at {}", sidecar.display()));
    }

    std::fs::create_dir_all(&config)
        .map_err(|e| format!("Failed to create config dir: {e}"))?;

    tracing::info!(
        config = %config.display(),
        sidecar = %sidecar.display(),
        "Starting GPD first-run setup"
    );

    // Step 1: Install commands, agents, MCP server config
    run_sidecar_install(&sidecar, &config).await?;

    // Step 2: Get MCP server config and merge into opencode.json
    let servers_json = run_sidecar_list_servers(&sidecar).await?;
    merge_mcp_config(&config, &servers_json)?;

    // Step 3: Inject LiteLLM provider config
    inject_provider_config(&config)?;

    // Step 4: Mark as initialized
    let marker = config.join(GPD_INIT_MARKER);
    std::fs::write(&marker, "initialized")
        .map_err(|e| format!("Failed to write init marker: {e}"))?;

    tracing::info!("GPD first-run setup completed");
    Ok(())
}

async fn run_sidecar_install(sidecar: &PathBuf, config: &PathBuf) -> Result<(), String> {
    tracing::info!("Running gpd-sidecar install opencode --global --skip-readiness-check");

    let output = timeout(
        Duration::from_secs(60),
        Command::new(sidecar)
            .args(["install", "opencode", "--global", "--skip-readiness-check"])
            .env("OPENCODE_CONFIG_DIR", config)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await
    .map_err(|_| "gpd-sidecar install timed out (60s)".to_string())?
    .map_err(|e| format!("Failed to run gpd-sidecar install: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("gpd-sidecar install failed: {stderr}"));
    }

    tracing::info!("gpd-sidecar install completed");
    Ok(())
}

async fn run_sidecar_list_servers(sidecar: &PathBuf) -> Result<String, String> {
    tracing::info!("Running gpd-sidecar list-servers --json");

    let output = timeout(
        Duration::from_secs(30),
        Command::new(sidecar)
            .args(["list-servers", "--json"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .stdin(Stdio::null())
            .output(),
    )
    .await
    .map_err(|_| "gpd-sidecar list-servers timed out (30s)".to_string())?
    .map_err(|e| format!("Failed to run gpd-sidecar list-servers: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("gpd-sidecar list-servers failed: {stderr}"));
    }

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn merge_mcp_config(config: &PathBuf, servers_json: &str) -> Result<(), String> {
    let path = config.join("opencode.json");

    let servers: serde_json::Value = serde_json::from_str(servers_json)
        .map_err(|e| format!("Failed to parse list-servers output: {e}"))?;

    let mut config_val: serde_json::Value = if path.exists() {
        let content = std::fs::read_to_string(&path)
            .map_err(|e| format!("Failed to read opencode.json: {e}"))?;
        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse opencode.json: {e}"))?
    } else {
        serde_json::json!({})
    };

    // Merge MCP servers
    if let Some(obj) = config_val.as_object_mut() {
        if let serde_json::Value::Object(server_entries) = servers {
            let mcp = obj.entry("mcp").or_insert_with(|| serde_json::json!({}));
            if let Some(mcp_obj) = mcp.as_object_mut() {
                for (name, server_config) in server_entries {
                    mcp_obj.insert(name, server_config);
                }
            }
        }
    }

    let json_str = serde_json::to_string_pretty(&config_val)
        .map_err(|e| format!("Failed to serialize opencode.json: {e}"))?;
    std::fs::write(&path, format!("{json_str}\n"))
        .map_err(|e| format!("Failed to write opencode.json: {e}"))?;

    tracing::info!(path = %path.display(), "Merged MCP server config");
    Ok(())
}

fn inject_provider_config(config: &PathBuf) -> Result<(), String> {
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
                    "claude-opus-4-6": { "name": "Claude Opus 4.6", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 131072 } },
                    "claude-sonnet-4-6": { "name": "Claude Sonnet 4.6", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 65536 } },
                    "claude-haiku-4-5": { "name": "Claude Haiku 4.5", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 200000, "output": 65536 } },
                    "gpt-5.4": { "name": "GPT-5.4", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-mini": { "name": "GPT-5.4 mini", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-nano": { "name": "GPT-5.4 nano", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.4-pro": { "name": "GPT-5.4 Pro", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1050000, "output": 131072 } },
                    "gpt-5.3-codex": { "name": "GPT-5.3 Codex", "tool_call": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 32768 } },
                    "gpt-4.1": { "name": "GPT-4.1", "tool_call": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 32768 } },
                    "gpt-4.1-mini": { "name": "GPT-4.1 mini", "tool_call": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 32768 } },
                    "o4-mini": { "name": "o4-mini (reasoning)", "tool_call": true, "reasoning": true, "temperature": true, "limit": { "context": 200000, "output": 100000 } },
                    "gemini-3.1-pro-preview": { "name": "Gemini 3.1 Pro", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 65536 } },
                    "gemini-3-flash-preview": { "name": "Gemini 3 Flash", "tool_call": true, "reasoning": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 65536 } },
                    "gemini-3.1-flash-lite-preview": { "name": "Gemini 3.1 Flash-Lite", "tool_call": true, "attachment": true, "temperature": true, "limit": { "context": 1000000, "output": 65536 } }
                }
            }));
        }

        // Set default model
        obj.insert("model".to_string(), serde_json::json!("gpd/claude-sonnet-4-6"));

        // Only show GPD provider
        obj.insert("enabled_providers".to_string(), serde_json::json!(["gpd"]));
    }

    let json_str = serde_json::to_string_pretty(&config_val)
        .map_err(|e| format!("Failed to serialize opencode.json: {e}"))?;
    std::fs::write(&path, format!("{json_str}\n"))
        .map_err(|e| format!("Failed to write opencode.json: {e}"))?;

    tracing::info!(path = %path.display(), "Injected LiteLLM provider config");
    Ok(())
}
