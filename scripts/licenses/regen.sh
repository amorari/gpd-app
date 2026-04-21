#!/usr/bin/env bash
# Regenerate THIRD_PARTY_NOTICES.md from package manifests.
#
# Inputs: packages/{desktop,app,opencode,ui}/package.json + bun.lock for npm;
#         packages/desktop/src-tauri/Cargo.{toml,lock} for Rust.
# Output: THIRD_PARTY_NOTICES.md at repo root.
#
# Prereqs: bun, license-checker-rseidelsohn (bun add -g), cargo-license
# (cargo install cargo-license). CI workflow installs them before invoking.

set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
WORK=$(mktemp -d -t gpd-notices-XXXXXX)
trap 'rm -rf "$WORK"' EXIT

cd "$ROOT"

echo "→ npm licenses (production-only, shipped workspaces)"
for pkg in desktop app opencode ui; do
  license-checker-rseidelsohn \
    --start "$ROOT/packages/$pkg" \
    --production \
    --json \
    --out "$WORK/npm-$pkg.json" >/dev/null
done

jq -s 'add | to_entries | sort_by(.key) | unique_by(.key) | from_entries' \
  "$WORK"/npm-*.json > "$WORK/npm-merged.json"
echo "  $(jq 'length' "$WORK/npm-merged.json") unique npm packages"

echo "→ cargo licenses (runtime deps only)"
( cd "$ROOT/packages/desktop/src-tauri" \
  && cargo license --json --avoid-build-deps --avoid-dev-deps ) \
  > "$WORK/cargo.json"
echo "  $(jq 'length' "$WORK/cargo.json") cargo crates"

echo "→ build THIRD_PARTY_NOTICES.md"
cp "$WORK/npm-merged.json" /tmp/gpd-notices-npm-merged.json
cp "$WORK/cargo.json"       /tmp/gpd-notices-cargo.json
# The builder reads from /tmp/gpd-notices/ paths; mirror them.
mkdir -p /tmp/gpd-notices
cp "$WORK/npm-merged.json" /tmp/gpd-notices/npm-merged.json
cp "$WORK/cargo.json"       /tmp/gpd-notices/cargo.json

bun "$ROOT/scripts/licenses/build-notices.ts"
echo "✓ $ROOT/THIRD_PARTY_NOTICES.md updated"
