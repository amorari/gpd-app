#!/usr/bin/env bash
# Usage:
#   rust_coverage_filter.sh <command_name> [--json]
#
# Runs cargo-llvm-cov for the workspace (tests only, debug, not release) and
# filters the report to only the function(s) matching <command_name>.
# Without --json: prints a compact terminal summary (lines covered / total).
# With --json: emits
#   {"command": "...", "matches": [ {"function": "...", "file": "...",
#    "lines_covered": N, "lines_total": M, "coverage_pct": 0.0-100.0}, ... ]}
#
# Honors COV_JSON_PATH env var: if set, reuses an existing llvm-cov JSON
# export instead of re-running cargo llvm-cov. This is the path the unit
# tests and repeated filters use to avoid the multi-minute rebuild cost.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: rust_coverage_filter.sh <command_name> [--json]" >&2
  exit 2
fi

CMD="$1"
shift
JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# Same homebrew-Rust fallback as rust_coverage.sh: cargo-llvm-cov expects
# llvm-cov/llvm-profdata from rustup's llvm-tools-preview; on Homebrew Rust
# boxes we point it at Homebrew's llvm formula.
if ! command -v rustup >/dev/null 2>&1; then
  if [ -z "${LLVM_COV:-}" ] && [ -x /opt/homebrew/opt/llvm/bin/llvm-cov ]; then
    export LLVM_COV=/opt/homebrew/opt/llvm/bin/llvm-cov
  fi
  if [ -z "${LLVM_PROFDATA:-}" ] && [ -x /opt/homebrew/opt/llvm/bin/llvm-profdata ]; then
    export LLVM_PROFDATA=/opt/homebrew/opt/llvm/bin/llvm-profdata
  fi
fi

# Let callers reuse an already-generated JSON (saves the minutes cargo llvm-cov
# spends rebuilding). If not provided, run cargo llvm-cov ourselves.
if [ -n "${COV_JSON_PATH:-}" ]; then
  JSON_OUT="$COV_JSON_PATH"
  CLEANUP_JSON=0
else
  JSON_OUT="$(mktemp -t rustcov.XXXXXX)"
  CLEANUP_JSON=1
  # shellcheck disable=SC2064
  trap "[ \"$CLEANUP_JSON\" = 1 ] && rm -f '$JSON_OUT' || true" EXIT
  # Emit the llvm-cov JSON export. Send cargo's own progress to stderr so
  # stdout stays clean for the downstream parser.
  cargo llvm-cov --workspace --json --ignore-filename-regex='vendor/' \
    --output-path "$JSON_OUT" >&2
fi

python3 "$SCRIPT_DIR/_cov_filter_impl.py" "$CMD" "$JSON_OUT" "$JSON"
