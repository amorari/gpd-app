#!/usr/bin/env bash
# Usage: run_mutation_test.sh <path-to-module>
# Runs mutmut against the target module, reports survived mutants to stderr.
#
# Example:
#   scripts/run_mutation_test.sh gpd_tests/helpers/ipc.py
#
# Intended for targeted CI jobs — pick one module per job, not the whole tree.
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <path-to-module>" >&2
    exit 2
fi

TARGET="$1"

if [[ ! -e "$TARGET" ]]; then
    echo "error: target '$TARGET' not found" >&2
    exit 2
fi

# `mutmut run` exits non-zero when mutants survive; swallow so we can still
# print results. The `results` output is what the CI job should parse.
uv run mutmut run --paths-to-mutate "$TARGET" || true
uv run mutmut results
