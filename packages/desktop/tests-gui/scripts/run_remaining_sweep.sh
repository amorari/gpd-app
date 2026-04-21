#!/usr/bin/env bash
# Continue the sweep from ipc onward (unit/smoke/surfaces already done).
set -u

cd "$(dirname "$0")/.."

: "${GPD_APP_PATH:=/Users/amorari/workspace/psi-oss-opencode/packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app}"
export GPD_APP_PATH
export GPD_TEST_SEED_ONBOARDING=1

RUNS_DIR="$(pwd)/runs"
mkdir -p "$RUNS_DIR"

# Clean up the partial ipc-1.xml and ipc-2.xml from the killed sweep
rm -f "$RUNS_DIR/ipc-1.xml" "$RUNS_DIR/ipc-2.xml"

run_group() {
  local label="$1" iters="$2" marker="$3" path="$4"
  echo "=== $label: $iters iterations ==="
  for i in $(seq 1 "$iters"); do
    local xml="$RUNS_DIR/${label}-${i}.xml"
    echo "--- $label iter $i ---"
    # pytest has its own per-test timeouts via pytest-timeout; rely on those.
    # macOS has no `timeout` binary by default.
    uv run pytest "$path" -m "$marker" --junitxml="$xml" 2>&1 | tail -8
    echo "rc=$?"
  done
}

run_group ipc 3 "ipc" "tests/ipc"
run_group flows 3 "flows and not real_backend" "tests/flows"
run_group regression 3 "regression" "tests/regression"
run_group broad 3 "broad" "tests/broad"
run_group lifecycle 2 "lifecycle" "tests/lifecycle"

echo
echo "=== Aggregating ==="
uv run python scripts/flakiness/report.py "$RUNS_DIR" > "$RUNS_DIR/flakiness_report.md"
echo "Report: $RUNS_DIR/flakiness_report.md"
cat "$RUNS_DIR/flakiness_report.md"
