# GPD CLI uninstaller for Windows 11
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File uninstall.ps1
#   powershell -ExecutionPolicy Bypass -File uninstall.ps1 -Yes
#
# Removes everything created by install.ps1:
#   - $HOME\.gpd\ directory (bin, python, venv, config)
#   - User PATH entry pointing to .gpd\bin
#   - GPD desktop app (runs Tauri NSIS uninstaller silently)
#   - Tauri GUI state at %APPDATA%\inc.psi.gpd\
#   - Tauri WebView data (localStorage/cookies/cache) at %LOCALAPPDATA%\inc.psi.gpd\
#   - "gpd" entry in %APPDATA%\opencode\auth.json (preserves other providers)
#   - gpd-specific files in %APPDATA%\opencode\
#
# Does NOT remove Git or MiKTeX -- many things depend on them. Instructions
# for manual removal are printed at the end.

#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

# -- Configuration ---------------------------------------------------------

$GpdHome   = if ($env:GPD_HOME) { $env:GPD_HOME } else { Join-Path $HOME ".gpd" }
$GpdBinDir = Join-Path $GpdHome "bin"

$TauriInstallDir = Join-Path $env:LOCALAPPDATA "Programs\GPD"
$TauriUninstaller = Join-Path $TauriInstallDir "uninstall.exe"

$TauriStateDir = Join-Path $env:APPDATA "inc.psi.gpd"

# Tauri on Windows stores WebView2 data (localStorage incl. the
# "gpd.key.saved" flag, cookies, cache, IndexedDB) under LocalAppData.
# Without wiping this, a reinstall keeps the previous run's
# "already-onboarded" signal and the GUI skips its own welcome -- which
# looks like a bug to users re-testing after an uninstall.
$TauriWebViewDir = Join-Path $env:LOCALAPPDATA "inc.psi.gpd"

$XdgData    = if ($env:XDG_DATA_HOME) { $env:XDG_DATA_HOME } else { $env:APPDATA }
$OpenCodeDir = Join-Path $XdgData "opencode"
$AuthFile    = Join-Path $OpenCodeDir "auth.json"

# Files in the opencode config dir that are gpd-specific and safe to remove.
$GpdManifestFile = Join-Path $OpenCodeDir "gpd-file-manifest.json"
$OpenCodeJson    = Join-Path $OpenCodeDir "opencode.json"

# -- Logging ---------------------------------------------------------------

function Write-Log {
    param([string]$Message)
    Write-Host "  i " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "  + " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  ! " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Err {
    param([string]$Message)
    Write-Host "  x " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Skip {
    param([string]$Message)
    Write-Host "  - " -ForegroundColor DarkGray -NoNewline
    Write-Host $Message -ForegroundColor DarkGray
}

# -- Banner ----------------------------------------------------------------

function Write-Banner {
    Write-Host ""
    Write-Host " ██████╗ ██████╗ ██████╗ " -ForegroundColor Cyan
    Write-Host "██╔════╝ ██╔══██╗██╔══██╗" -ForegroundColor Cyan
    Write-Host "██║  ███╗██████╔╝██║  ██║" -ForegroundColor Cyan
    Write-Host "██║   ██║██╔═══╝ ██║  ██║" -ForegroundColor Cyan
    Write-Host "╚██████╔╝██║     ██████╔╝" -ForegroundColor Cyan
    Write-Host " ╚═════╝ ╚═╝     ╚═════╝ " -ForegroundColor Cyan
    Write-Host ""
    Write-Host " Get Physics Done" -NoNewline -ForegroundColor White
    Write-Host " -- CLI Uninstaller" -ForegroundColor DarkGray
    Write-Host ""
}

# -- Discovery -------------------------------------------------------------

function Get-PathContainsGpd {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if (-not $currentPath) { return $false }
    return ($currentPath.Split(";") -contains $GpdBinDir)
}

# Inspect auth.json and decide whether the "gpd" entry is present. Returns
# $true if at least one key needs to be removed, $false otherwise.
function Test-AuthHasGpd {
    if (-not (Test-Path $AuthFile)) { return $false }
    try {
        $data = Get-Content $AuthFile -Raw | ConvertFrom-Json
    } catch {
        return $false
    }
    if ($null -eq $data) { return $false }
    $names = @()
    $data.PSObject.Properties | ForEach-Object { $names += $_.Name }
    return ($names -contains "gpd")
}

# Inspect opencode.json and decide whether it looks gpd-only (so we can
# safely delete it). Returns $true if the file only configures the gpd
# provider. If there are other providers/settings, return $false and leave
# it alone.
function Test-OpenCodeJsonIsGpdOnly {
    if (-not (Test-Path $OpenCodeJson)) { return $false }
    try {
        $data = Get-Content $OpenCodeJson -Raw | ConvertFrom-Json
    } catch {
        return $false
    }
    if ($null -eq $data) { return $false }

    # If there's no "provider" key we can't be sure it's ours -- leave it.
    if (-not ($data.PSObject.Properties.Name -contains "provider")) {
        return $false
    }

    $providerNames = @()
    $data.provider.PSObject.Properties | ForEach-Object { $providerNames += $_.Name }

    # Only delete if gpd is the sole provider.
    return ($providerNames.Count -eq 1 -and $providerNames[0] -eq "gpd")
}

# -- Removal actions -------------------------------------------------------

function Remove-TauriDesktop {
    if (Test-Path $TauriUninstaller) {
        Write-Log "Running GPD desktop uninstaller..."
        try {
            $proc = Start-Process -FilePath $TauriUninstaller `
                -ArgumentList "/S" -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                Write-Warn "Desktop uninstaller exit code $($proc.ExitCode)"
            } else {
                Write-Success "GPD desktop app uninstalled"
            }
        } catch {
            Write-Warn "Failed to run desktop uninstaller: $_"
        }

        # Clean up the install dir if the uninstaller left it behind.
        if (Test-Path $TauriInstallDir) {
            try {
                Remove-Item -Path $TauriInstallDir -Recurse -Force -ErrorAction Stop
                Write-Success "Removed leftover $TauriInstallDir"
            } catch {
                Write-Warn "Could not remove $TauriInstallDir -- $_"
            }
        }
    }
    elseif (Test-Path $TauriInstallDir) {
        # Install dir exists but no uninstaller.exe -- just wipe it.
        Write-Log "Removing GPD desktop install directory (no uninstaller found)..."
        try {
            Remove-Item -Path $TauriInstallDir -Recurse -Force -ErrorAction Stop
            Write-Success "Removed $TauriInstallDir"
        } catch {
            Write-Warn "Could not remove $TauriInstallDir -- $_"
        }
    }
    else {
        Write-Skip "GPD desktop app not installed"
    }
}

function Remove-TauriState {
    if (Test-Path $TauriStateDir) {
        try {
            Remove-Item -Path $TauriStateDir -Recurse -Force -ErrorAction Stop
            Write-Success "Removed Tauri state dir $TauriStateDir"
        } catch {
            Write-Warn "Could not remove $TauriStateDir -- $_"
        }
    } else {
        Write-Skip "No Tauri state dir at $TauriStateDir"
    }

    # WebView2 data dir (localStorage, cookies, cache) — see explanation
    # where $TauriWebViewDir is declared.
    if (Test-Path $TauriWebViewDir) {
        try {
            Remove-Item -Path $TauriWebViewDir -Recurse -Force -ErrorAction Stop
            Write-Success "Removed Tauri WebView data $TauriWebViewDir"
        } catch {
            Write-Warn "Could not remove $TauriWebViewDir -- $_"
        }
    } else {
        Write-Skip "No Tauri WebView data at $TauriWebViewDir"
    }
}

function Remove-GpdFromPath {
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if (-not $currentPath) {
        Write-Skip "User PATH is empty"
        return
    }

    $parts = $currentPath.Split(";")
    if (-not ($parts -contains $GpdBinDir)) {
        Write-Skip "$GpdBinDir not on user PATH"
        return
    }

    $newParts = $parts | Where-Object { $_ -ne $GpdBinDir -and $_ -ne "" }
    $newPath = ($newParts -join ";")

    try {
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
        Write-Success "Removed $GpdBinDir from user PATH"
    } catch {
        Write-Warn "Could not update user PATH -- $_"
    }

    # Also update this session so the caller sees the change immediately.
    $sessionParts = $env:PATH.Split(";") | Where-Object { $_ -ne $GpdBinDir -and $_ -ne "" }
    $env:PATH = ($sessionParts -join ";")
}

function Remove-AuthJsonGpdEntry {
    if (-not (Test-Path $AuthFile)) {
        Write-Skip "No auth.json at $AuthFile"
        return
    }

    try {
        $data = Get-Content $AuthFile -Raw | ConvertFrom-Json
    } catch {
        Write-Warn "Could not parse $AuthFile -- leaving alone"
        return
    }

    if ($null -eq $data) {
        Write-Skip "auth.json is empty"
        return
    }

    $hasGpd = $false
    $data.PSObject.Properties | ForEach-Object {
        if ($_.Name -eq "gpd") { $hasGpd = $true }
    }

    if (-not $hasGpd) {
        Write-Skip "auth.json has no 'gpd' entry"
        return
    }

    # Rebuild as hashtable without the "gpd" key so ConvertTo-Json emits a
    # clean object (dropping PSObject metadata).
    $newData = @{}
    $data.PSObject.Properties | ForEach-Object {
        if ($_.Name -ne "gpd") {
            $newData[$_.Name] = $_.Value
        }
    }

    try {
        if ($newData.Count -eq 0) {
            # If that was the only provider, write an empty object rather
            # than deleting the file -- opencode expects auth.json to exist
            # (or be absent entirely; we err on the side of "no surprise").
            "{}" | Set-Content -Path $AuthFile -Encoding UTF8
        } else {
            $newData | ConvertTo-Json -Depth 5 | Set-Content -Path $AuthFile -Encoding UTF8
        }
        Write-Success "Removed 'gpd' entry from $AuthFile"
    } catch {
        Write-Warn "Could not rewrite $AuthFile -- $_"
    }
}

function Remove-OpenCodeGpdFiles {
    if (-not (Test-Path $OpenCodeDir)) {
        Write-Skip "No opencode config dir at $OpenCodeDir"
        return
    }

    # gpd-file-manifest.json -- always gpd-specific.
    if (Test-Path $GpdManifestFile) {
        try {
            Remove-Item -Path $GpdManifestFile -Force -ErrorAction Stop
            Write-Success "Removed $GpdManifestFile"
        } catch {
            Write-Warn "Could not remove $GpdManifestFile -- $_"
        }
    } else {
        Write-Skip "No gpd-file-manifest.json"
    }

    # opencode.json -- only remove if its only provider is gpd.
    if (Test-Path $OpenCodeJson) {
        if (Test-OpenCodeJsonIsGpdOnly) {
            try {
                Remove-Item -Path $OpenCodeJson -Force -ErrorAction Stop
                Write-Success "Removed $OpenCodeJson (only provider was gpd)"
            } catch {
                Write-Warn "Could not remove $OpenCodeJson -- $_"
            }
        } else {
            Write-Skip "Kept $OpenCodeJson (has non-gpd providers or unknown shape)"
        }
    } else {
        Write-Skip "No opencode.json"
    }
}

function Remove-GpdHome {
    if (Test-Path $GpdHome) {
        try {
            Remove-Item -Path $GpdHome -Recurse -Force -ErrorAction Stop
            Write-Success "Removed $GpdHome"
        } catch {
            Write-Warn "Could not remove $GpdHome -- $_"
            Write-Warn "Some files may be in use. Close all gpd/opencode processes and retry."
        }
    } else {
        Write-Skip "$GpdHome already removed"
    }
}

# -- Main ------------------------------------------------------------------

function Invoke-GpdUninstall {
    Write-Banner

    # Discovery pass -- print what will be touched.
    $found = $false

    if (Test-Path $GpdHome) {
        Write-Log "Found GPD directory: $GpdHome"
        $found = $true
    }

    if ((Test-Path $TauriUninstaller) -or (Test-Path $TauriInstallDir)) {
        Write-Log "Found GPD desktop app: $TauriInstallDir"
        $found = $true
    }

    if (Test-Path $TauriStateDir) {
        Write-Log "Found Tauri state dir: $TauriStateDir"
        $found = $true
    }

    if (Test-Path $TauriWebViewDir) {
        Write-Log "Found Tauri WebView data: $TauriWebViewDir"
        $found = $true
    }

    if (Get-PathContainsGpd) {
        Write-Log "Found PATH entry: $GpdBinDir"
        $found = $true
    }

    if (Test-AuthHasGpd) {
        Write-Log "Found 'gpd' entry in $AuthFile"
        $found = $true
    }

    if (Test-Path $GpdManifestFile) {
        Write-Log "Found gpd-file-manifest.json in $OpenCodeDir"
        $found = $true
    }

    if ((Test-Path $OpenCodeJson) -and (Test-OpenCodeJsonIsGpdOnly)) {
        Write-Log "Found gpd-only opencode.json in $OpenCodeDir"
        $found = $true
    }

    if (-not $found) {
        Write-Host ""
        Write-Host "  Nothing to remove -- GPD does not appear to be installed." -ForegroundColor DarkGray
        Write-Host ""
        return
    }

    # Confirm.
    Write-Host ""
    if (-not $Yes) {
        if (-not [Environment]::UserInteractive -or [Console]::IsInputRedirected) {
            Write-Warn "Non-interactive session -- re-run with -Yes to confirm removal."
            return
        }
        Write-Host "  Remove GPD and all its files? " -NoNewline -ForegroundColor White
        Write-Host "[y/N] " -NoNewline
        $confirm = Read-Host
        if ($confirm -notmatch '^[Yy]$') {
            Write-Host "  Cancelled." -ForegroundColor DarkGray
            Write-Host ""
            return
        }
    }
    Write-Host ""

    # Order matters:
    #   1. Tauri desktop uninstaller -- needs its own files intact.
    #   2. Tauri state dir.
    #   3. PATH entry -- harmless before .gpd removal, but cleanest first.
    #   4. auth.json / opencode config cleanup -- files in %APPDATA%.
    #   5. .gpd dir -- last, since anything else could live inside it.
    Remove-TauriDesktop
    Remove-TauriState
    Remove-GpdFromPath
    Remove-AuthJsonGpdEntry
    Remove-OpenCodeGpdFiles
    Remove-GpdHome

    # Final message.
    Write-Host ""
    Write-Host "  GPD has been uninstalled." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Git and MiKTeX were NOT removed -- other tools likely depend on them." -ForegroundColor DarkGray
    Write-Host "  To remove them manually:" -ForegroundColor DarkGray
    Write-Host "    winget uninstall Git.Git" -ForegroundColor White
    Write-Host "    winget uninstall MiKTeX.MiKTeX" -ForegroundColor White
    Write-Host ""
    Write-Host "  Open a new terminal to clear the cached PATH." -ForegroundColor DarkGray
    Write-Host ""
}

# -- Entry point -----------------------------------------------------------

Invoke-GpdUninstall
