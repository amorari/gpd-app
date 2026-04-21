#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# cargo-llvm-cov normally uses `rustup component add llvm-tools-preview` to
# supply llvm-cov/llvm-profdata. On machines that install Rust via Homebrew
# (no rustup), fall back to Homebrew's llvm formula if available.
if ! command -v rustup >/dev/null 2>&1; then
  if [[ -z "${LLVM_COV:-}" ]] && [[ -x /opt/homebrew/opt/llvm/bin/llvm-cov ]]; then
    export LLVM_COV=/opt/homebrew/opt/llvm/bin/llvm-cov
  fi
  if [[ -z "${LLVM_PROFDATA:-}" ]] && [[ -x /opt/homebrew/opt/llvm/bin/llvm-profdata ]]; then
    export LLVM_PROFDATA=/opt/homebrew/opt/llvm/bin/llvm-profdata
  fi
fi

cargo llvm-cov clean --workspace
cargo llvm-cov --html --workspace --ignore-filename-regex='vendor/'
echo
echo "HTML report: $(pwd)/target/llvm-cov/html/index.html"
