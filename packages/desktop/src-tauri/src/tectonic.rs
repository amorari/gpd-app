//! On-demand installer for the Tectonic TeX engine.
//!
//! Tectonic (https://tectonic-typesetting.github.io) ships as a self-contained
//! ~80 MB binary for common desktop platforms. Rather than asking physics
//! professors to install MacTeX / MiKTeX / TeX Live before using GPD's
//! publication workflow, we download a matching prebuilt Tectonic archive
//! from the upstream GitHub release and extract the `tectonic` binary into
//! `~/.config/gpd/.capabilities/tectonic/bin/tectonic`. That path is added to
//! the PATH-style lookup in the doctor probe so Tectonic shows up as
//! available immediately after install.
//!
//! We never download the binary at app startup or first-run — only when the
//! user explicitly clicks "Install Tectonic" in the Dependency Manager panel.

use futures::StreamExt;
use serde::Deserialize;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use tauri::AppHandle;
use tauri_specta::Event;

/// Tectonic binary target we install into. The Dependency Manager panel and
/// the `/health/doctor` server route agree on this path.
const CAPABILITIES_SUBDIR: &str = ".capabilities/tectonic/bin";

/// GitHub API endpoint that returns metadata for the latest published release.
const LATEST_RELEASE_URL: &str =
    "https://api.github.com/repos/tectonic-typesetting/tectonic/releases/latest";

/// Upstream install page, used in error messages when no prebuilt asset
/// matches the user's platform.
const MANUAL_INSTALL_URL: &str = "https://tectonic-typesetting.github.io/en-US/install.html";

/// Progress payload emitted under the `tectonic-download-progress` event
/// while the Tectonic archive is being streamed from GitHub.
///
/// Fields are typed as `f64` (rather than `u64`) because TypeScript's
/// `number` is a double and the specta TypeScript exporter forbids
/// `BigInt`-backed integers by default. Tectonic archives are ~20-30 MB,
/// which is well inside the safe-integer range for `f64`.
#[derive(
    Clone, serde::Serialize, serde::Deserialize, specta::Type, tauri_specta::Event,
)]
pub struct TectonicDownloadProgress {
    /// Bytes downloaded so far.
    pub loaded: f64,
    /// Total bytes advertised by the server, or 0 if unknown.
    pub total: f64,
}

#[derive(Deserialize)]
struct GithubRelease {
    tag_name: String,
    assets: Vec<GithubAsset>,
}

#[derive(Deserialize)]
struct GithubAsset {
    name: String,
    browser_download_url: String,
}

/// Download (if not already present) and install the Tectonic binary.
///
/// Returns the absolute path to the installed binary on success. Re-invoking
/// this command with an already-installed binary is a cheap no-op: it skips
/// the network request entirely, confirms the binary runs, and returns the
/// cached path.
#[tauri::command]
#[specta::specta]
pub async fn install_tectonic(app: AppHandle) -> Result<String, String> {
    let install_dir = capabilities_bin_dir()?;
    let binary_path = install_dir.join(binary_filename());

    // Cache: if the binary already exists and runs, return immediately.
    if binary_path.exists() && binary_runs(&binary_path).await {
        tracing::info!(path = %binary_path.display(), "Tectonic already installed");
        return Ok(binary_path.to_string_lossy().to_string());
    }

    std::fs::create_dir_all(&install_dir)
        .map_err(|e| format!("Failed to create Tectonic install dir {}: {e}", install_dir.display()))?;

    let asset_pattern = platform_asset_pattern()
        .ok_or_else(|| format!(
            "Tectonic is not available as a prebuilt binary for this platform. \
             See {MANUAL_INSTALL_URL} for manual install instructions."
        ))?;

    let release = fetch_latest_release().await?;
    let asset = release
        .assets
        .iter()
        .find(|a| asset_pattern.matches(&a.name))
        .ok_or_else(|| format!(
            "Tectonic release {} has no asset matching this platform. See {MANUAL_INSTALL_URL}.",
            release.tag_name
        ))?;

    tracing::info!(
        version = release.tag_name,
        asset = asset.name,
        url = asset.browser_download_url,
        "Downloading Tectonic"
    );

    let archive_bytes = download_with_progress(&app, &asset.browser_download_url).await?;

    extract_binary(&archive_bytes, &asset.name, &binary_path)?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = std::fs::metadata(&binary_path)
            .map_err(|e| format!("Failed to stat installed binary: {e}"))?
            .permissions();
        perms.set_mode(0o755);
        std::fs::set_permissions(&binary_path, perms)
            .map_err(|e| format!("Failed to chmod installed binary: {e}"))?;
    }

    if !binary_runs(&binary_path).await {
        let hint = if cfg!(target_os = "macos") {
            " On macOS, Gatekeeper may have blocked execution of the downloaded binary. \
              Open System Settings → Privacy & Security and approve the `tectonic` binary, \
              or run `xattr -d com.apple.quarantine` on the installed path."
        } else {
            ""
        };
        return Err(format!(
            "Tectonic was downloaded to {} but failed to execute.{hint}",
            binary_path.display()
        ));
    }

    tracing::info!(path = %binary_path.display(), "Tectonic installed");
    Ok(binary_path.to_string_lossy().to_string())
}

// ---------------------------------------------------------------------------
// Platform detection
// ---------------------------------------------------------------------------

/// A substring pattern used to select the right release asset for the current
/// platform. We match on the archive filename (as published by the Tectonic
/// release pipeline) rather than hardcoding a URL, so users always receive the
/// newest build.
struct AssetPattern {
    /// Substring that must appear in the asset name.
    needle: &'static str,
    /// Extension that must end the asset name.
    ext: &'static str,
}

impl AssetPattern {
    fn matches(&self, name: &str) -> bool {
        name.contains(self.needle) && name.ends_with(self.ext)
    }
}

fn platform_asset_pattern() -> Option<AssetPattern> {
    // Tectonic release asset names follow the pattern
    //   tectonic-<version>-<rust-triple>.{tar.gz,zip}
    // e.g. tectonic-0.16.9-aarch64-apple-darwin.tar.gz
    #[cfg(all(target_os = "macos", target_arch = "aarch64"))]
    {
        return Some(AssetPattern {
            needle: "aarch64-apple-darwin",
            ext: ".tar.gz",
        });
    }
    #[cfg(all(target_os = "macos", target_arch = "x86_64"))]
    {
        return Some(AssetPattern {
            needle: "x86_64-apple-darwin",
            ext: ".tar.gz",
        });
    }
    #[cfg(all(target_os = "windows", target_arch = "x86_64"))]
    {
        // Prefer the MSVC build on Windows. The GNU build exists for edge
        // cases but MSVC matches how most Windows apps are linked.
        return Some(AssetPattern {
            needle: "x86_64-pc-windows-msvc",
            ext: ".zip",
        });
    }
    #[cfg(all(target_os = "linux", target_arch = "x86_64"))]
    {
        // The musl build has no glibc dependency, which matters because GPD
        // may be launched on older distros. Match musl first; gnu also works
        // but is less portable.
        return Some(AssetPattern {
            needle: "x86_64-unknown-linux-musl",
            ext: ".tar.gz",
        });
    }
    #[allow(unreachable_code)]
    None
}

fn binary_filename() -> &'static str {
    if cfg!(windows) { "tectonic.exe" } else { "tectonic" }
}

// ---------------------------------------------------------------------------
// Filesystem layout
// ---------------------------------------------------------------------------

fn gpd_config_dir() -> Result<PathBuf, String> {
    let base = std::env::var_os("XDG_CONFIG_HOME")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            // dirs::home_dir returns None only on very unusual systems.
            dirs::home_dir()
                .map(|h| h.join(".config"))
                .unwrap_or_else(|| PathBuf::from("."))
        });
    Ok(base.join("gpd"))
}

fn capabilities_bin_dir() -> Result<PathBuf, String> {
    Ok(gpd_config_dir()?.join(CAPABILITIES_SUBDIR))
}

// ---------------------------------------------------------------------------
// HTTP
// ---------------------------------------------------------------------------

fn http_client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        // GitHub rejects requests without a User-Agent header.
        .user_agent(concat!("gpd-desktop/", env!("CARGO_PKG_VERSION")))
        .build()
        .map_err(|e| format!("Failed to build HTTP client: {e}"))
}

async fn fetch_latest_release() -> Result<GithubRelease, String> {
    let client = http_client()?;
    let resp = client
        .get(LATEST_RELEASE_URL)
        .header("Accept", "application/vnd.github+json")
        .send()
        .await
        .map_err(|e| format!("Failed to fetch Tectonic release metadata: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!(
            "GitHub returned {} when fetching Tectonic release metadata",
            resp.status()
        ));
    }

    resp.json::<GithubRelease>()
        .await
        .map_err(|e| format!("Failed to parse Tectonic release metadata: {e}"))
}

/// Stream the asset into memory while emitting progress events. The downloaded
/// archives are small (~20–30 MB compressed) so buffering in RAM is fine and
/// avoids a temp-file roundtrip.
async fn download_with_progress(app: &AppHandle, url: &str) -> Result<Vec<u8>, String> {
    let client = http_client()?;
    let resp = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("Failed to start Tectonic download: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!(
            "Tectonic download returned HTTP {}",
            resp.status()
        ));
    }

    let total = resp.content_length().unwrap_or(0);
    let mut buf: Vec<u8> = Vec::with_capacity(total as usize);
    let mut stream = resp.bytes_stream();
    let mut loaded: u64 = 0;

    // Initial tick so the UI can render a determinate bar the moment the
    // request succeeds, even if the server hasn't sent any body bytes yet.
    let _ = TectonicDownloadProgress {
        loaded: loaded as f64,
        total: total as f64,
    }
    .emit(app);

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| format!("Tectonic download interrupted: {e}"))?;
        loaded += chunk.len() as u64;
        buf.extend_from_slice(&chunk);
        let _ = TectonicDownloadProgress {
            loaded: loaded as f64,
            total: total as f64,
        }
        .emit(app);
    }

    Ok(buf)
}

// ---------------------------------------------------------------------------
// Extraction
// ---------------------------------------------------------------------------

/// Walks the archive (tar.gz or zip) and writes the first entry named
/// `tectonic` (or `tectonic.exe`) to `dest`. The upstream archives put the
/// binary at the top level, but we search every entry so a minor packaging
/// change upstream doesn't break us.
fn extract_binary(bytes: &[u8], archive_name: &str, dest: &Path) -> Result<(), String> {
    let bin_name = binary_filename();

    if archive_name.ends_with(".zip") {
        let mut zip = zip::ZipArchive::new(Cursor::new(bytes))
            .map_err(|e| format!("Failed to open Tectonic zip: {e}"))?;
        for i in 0..zip.len() {
            let mut file = zip
                .by_index(i)
                .map_err(|e| format!("Failed to read zip entry {i}: {e}"))?;
            let file_name = match file.enclosed_name() {
                Some(n) => n.to_path_buf(),
                None => continue,
            };
            if file_name.file_name().and_then(|n| n.to_str()) == Some(bin_name) {
                let mut out = std::fs::File::create(dest)
                    .map_err(|e| format!("Failed to create {}: {e}", dest.display()))?;
                std::io::copy(&mut file, &mut out)
                    .map_err(|e| format!("Failed to write Tectonic binary: {e}"))?;
                return Ok(());
            }
        }
        Err(format!("No `{bin_name}` entry found inside {archive_name}"))
    } else if archive_name.ends_with(".tar.gz") || archive_name.ends_with(".tgz") {
        let decoder = flate2::read::GzDecoder::new(Cursor::new(bytes));
        let mut archive = tar::Archive::new(decoder);
        for entry in archive
            .entries()
            .map_err(|e| format!("Failed to read tar archive: {e}"))?
        {
            let mut entry =
                entry.map_err(|e| format!("Failed to read tar entry: {e}"))?;
            let path = entry
                .path()
                .map_err(|e| format!("Failed to resolve tar entry path: {e}"))?
                .to_path_buf();
            if path.file_name().and_then(|n| n.to_str()) == Some(bin_name) {
                let mut out = std::fs::File::create(dest)
                    .map_err(|e| format!("Failed to create {}: {e}", dest.display()))?;
                std::io::copy(&mut entry, &mut out)
                    .map_err(|e| format!("Failed to write Tectonic binary: {e}"))?;
                return Ok(());
            }
        }
        Err(format!("No `{bin_name}` entry found inside {archive_name}"))
    } else {
        Err(format!(
            "Unrecognised Tectonic archive format: {archive_name}"
        ))
    }
}

// ---------------------------------------------------------------------------
// Sanity check
// ---------------------------------------------------------------------------

/// Spawn `tectonic --version` and return true iff it exits 0. Used both to
/// decide whether we can skip a re-download and as a post-install check that
/// catches Gatekeeper quarantine / wrong-arch binaries before the user sees a
/// cryptic error later.
async fn binary_runs(path: &Path) -> bool {
    let mut cmd = tokio::process::Command::new(path);
    cmd.arg("--version");
    cmd.stdout(std::process::Stdio::null());
    cmd.stderr(std::process::Stdio::null());
    cmd.stdin(std::process::Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW — keep the probe invisible on Windows.
        cmd.creation_flags(0x08000000);
    }
    matches!(cmd.status().await, Ok(s) if s.success())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn asset_pattern_matches_extension() {
        let p = AssetPattern {
            needle: "aarch64-apple-darwin",
            ext: ".tar.gz",
        };
        assert!(p.matches("tectonic-0.16.9-aarch64-apple-darwin.tar.gz"));
        assert!(!p.matches("tectonic-0.16.9-aarch64-apple-darwin.zip"));
        assert!(!p.matches("tectonic-0.16.9-x86_64-apple-darwin.tar.gz"));
    }

    #[test]
    fn capabilities_dir_under_config() {
        let dir = capabilities_bin_dir().unwrap();
        assert!(dir.ends_with(".capabilities/tectonic/bin"));
    }
}
