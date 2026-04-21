#!/usr/bin/env bash
# verify-pbs-hashes.sh — regenerate the PBS SHA256 pin table.
#
# Prints the SHA256 of every python-build-standalone tarball the GPD
# installers might download, in a form ready to paste back into
# install-gpd/install (bash) and install-gpd/windows_11/install.ps1.
#
# Two modes, auto-selected:
#
#   1. Fast path — fetch upstream SHA256SUMS for the release and grep
#      out only our triples. One HTTP round-trip, no multi-GB download.
#   2. Slow path — curl each tarball and pipe through sha256sum/shasum.
#      Used only if --download is passed or SHA256SUMS is unreachable.
#
# Requires: curl; one of sha256sum (Linux) or `shasum -a 256` (macOS).
# Accepts no flags for the default fast path; pass --download to force
# full re-verification by streaming every tarball.

set -euo pipefail

PBS_TAG="${PBS_TAG:-20250409}"
PBS_PYTHON="${PBS_PYTHON:-3.13.3}"
PBS_BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}"

# Triples every installer flavor may request. Keep in sync with
# pbs_triple (install) / $triple switch (install.ps1). Windows aarch64
# is NOT published by upstream for tag 20250409 — install.ps1 bails
# out earlier for that arch.
TRIPLES=(
    "x86_64-unknown-linux-gnu"
    "aarch64-unknown-linux-gnu"
    "x86_64-apple-darwin"
    "aarch64-apple-darwin"
    "x86_64-pc-windows-msvc"
)

# Label for each triple when emitting the bash/PS pin constants.
label_for() {
    case "$1" in
        x86_64-unknown-linux-gnu)   echo "LINUX_X64" ;;
        aarch64-unknown-linux-gnu)  echo "LINUX_ARM64" ;;
        x86_64-apple-darwin)        echo "DARWIN_X64" ;;
        aarch64-apple-darwin)       echo "DARWIN_ARM64" ;;
        x86_64-pc-windows-msvc)     echo "WINDOWS_X64" ;;
        aarch64-pc-windows-msvc)    echo "WINDOWS_ARM64" ;;
        *)                          echo "UNKNOWN" ;;
    esac
}

sha256_of_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        echo "ERROR: need sha256sum or shasum -a 256" >&2
        exit 1
    fi
}

# Fast path: pull the combined SHA256SUMS file for this release tag and
# emit only the triples we care about.
fetch_from_sums() {
    local sums_url="${PBS_BASE_URL}/SHA256SUMS"
    local sums
    sums="$(curl -fsSL --max-time 30 "$sums_url" 2>/dev/null)" || return 1

    for triple in "${TRIPLES[@]}"; do
        local filename="cpython-${PBS_PYTHON}+${PBS_TAG}-${triple}-install_only.tar.gz"
        local hash
        hash="$(awk -v f="$filename" '$2 == f {print $1; exit}' <<<"$sums")"
        if [[ -z "$hash" ]]; then
            printf '# MISSING: %s (not in %s)\n' "$filename" "$sums_url" >&2
            continue
        fi
        printf '%s  %s\n' "$hash" "$filename"
    done
}

# Slow path: download each tarball and hash it locally. Use if upstream
# SHA256SUMS is unreachable or the user explicitly wants to re-verify
# the bytes (via --download).
fetch_from_downloads() {
    local tmp
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT

    for triple in "${TRIPLES[@]}"; do
        local filename="cpython-${PBS_PYTHON}+${PBS_TAG}-${triple}-install_only.tar.gz"
        local url="${PBS_BASE_URL}/${filename}"
        local dest="${tmp}/${filename}"
        printf '# Downloading %s ...\n' "$filename" >&2
        if ! curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url"; then
            printf '# MISSING: %s (download failed from %s)\n' "$filename" "$url" >&2
            continue
        fi
        printf '%s  %s\n' "$(sha256_of_file "$dest")" "$filename"
    done
}

main() {
    local mode="sums"
    case "${1:-}" in
        --download) mode="downloads" ;;
        --help|-h)
            sed -n '2,20p' "$0"
            exit 0
            ;;
    esac

    local raw
    if [[ "$mode" == "sums" ]]; then
        raw="$(fetch_from_sums)" || raw=""
        if [[ -z "$raw" ]]; then
            printf '# SHA256SUMS fetch failed; falling back to full download.\n' >&2
            raw="$(fetch_from_downloads)"
        fi
    else
        raw="$(fetch_from_downloads)"
    fi

    [[ -n "$raw" ]] || { echo "ERROR: no hashes produced" >&2; exit 1; }

    printf '\n# Paste into install-gpd/install (bash):\n'
    printf '# ───────────────────────────────────────\n'
    while IFS= read -r line; do
        local hash filename triple label
        hash="$(awk '{print $1}' <<<"$line")"
        filename="$(awk '{print $2}' <<<"$line")"
        # Recover triple from the filename shape.
        triple="$(sed -E "s/^cpython-${PBS_PYTHON}\+${PBS_TAG}-(.+)-install_only\.tar\.gz$/\1/" <<<"$filename")"
        label="$(label_for "$triple")"
        printf 'PBS_SHA256_%s="%s"\n' "$label" "$hash"
    done <<<"$raw"

    printf '\n# Paste into install-gpd/windows_11/install.ps1:\n'
    printf '# ─────────────────────────────────────────────\n'
    printf '$PbsSha256 = @{\n'
    while IFS= read -r line; do
        local hash filename triple
        hash="$(awk '{print $1}' <<<"$line")"
        filename="$(awk '{print $2}' <<<"$line")"
        triple="$(sed -E "s/^cpython-${PBS_PYTHON}\+${PBS_TAG}-(.+)-install_only\.tar\.gz$/\1/" <<<"$filename")"
        # Only emit Windows triples for the PS hashtable; Unix-only
        # triples stay in the bash-side constants above.
        case "$triple" in
            *windows-msvc)
                printf '    "%s" = "%s"\n' "$triple" "$hash"
                ;;
        esac
    done <<<"$raw"
    printf '}\n'
}

main "$@"
