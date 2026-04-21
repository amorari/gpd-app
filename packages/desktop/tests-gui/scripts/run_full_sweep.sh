#!/usr/bin/env bash
# Runs the full test suite N times per marker group, collects JUnit XML.
# Assumes GPD Dev is already running.
set -u  # no -e: we want failures, not aborts

cd "$(dirname "$0")/.."

: "${GPD_APP_PATH:=/Users/amorari/workspace/psi-oss-opencode/packages/desktop/src-tauri/target/debug/bundle/macos/GPD Dev.app}"
export GPD_APP_PATH
export GPD_TEST_SEED_ONBOARDING=1

RUNS_DIR="$(pwd)/runs"
mkdir -p "$RUNS_DIR"

run_group() {
  local label="$1" iters="$2" marker="$3" shift_path="$4"
  echo "=== $label: $iters iterations ==="
  for i in $(seq 1 "$iters"); do
    local xml="$RUNS_DIR/${label}-${i}.xml"
    echo "--- $label iter $i ---"
    if [ -n "$shift_path" ]; then
      uv run pytest "$shift_path" -m "$marker" --junitxml="$xml" 2>&1 | tail -5
    else
      uv run pytest -m "$marker" --junitxml="$xml" 2>&1 | tail -5
    fi
  done
}

# Unit: no GPD dependency
run_group unit 5 "unit" "tests_unit"
# Smoke: 5 iterations
run_group smoke 5 "smoke and not restart" "tests/smoke"
# Surfaces: 3 iterations
run_group surfaces 3 "surfaces" "tests/surfaces"
# IPC: 3 iterations — newest suite
run_group ipc 3 "ipc" "tests/ipc"
# Flows (non-real-backend): 3 iterations
run_group flows 3 "flows and not real_backend" "tests/flows"
# Regression: 3 iterations
run_group regression 3 "regression" "tests/regression"
# Broad: 3 iterations
run_group broad 3 "broad" "tests/broad"
# Lifecycle: 2 iterations (destructive — will quit/relaunch GPD)
run_group lifecycle 2 "lifecycle" "tests/lifecycle"

echo
echo "=== Aggregating ==="
uv run python scripts/flakiness/report.py "$RUNS_DIR" > "$RUNS_DIR/flakiness_report.md"
echo "Report: $RUNS_DIR/flakiness_report.md"
cat "$RUNS_DIR/flakiness_report.md"
