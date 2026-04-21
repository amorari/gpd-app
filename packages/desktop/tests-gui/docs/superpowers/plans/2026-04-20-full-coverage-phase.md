# GPD Full-Coverage Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking. Dispatch fresh subagent per task with worktree isolation. Cherry-pick is a no-op — worktrees auto-merge on completion.

**Goal:** Close the five largest coverage gaps after Phase 1-5 + wave-2 fixes: (1) CI actually running with coverage reports, (2) contract coverage for the 28-command Tauri IPC surface, (3) real-backend LLM flows beyond the single existing test, (4) session persistence/lifecycle tests, (5) flakiness detection cron + triage Gate 4 automation.

**Architecture:** Five sequential phases (A-E). Phase A lays foundation (coverage instrumentation + first real CI run) so subsequent phases can measure their impact. Phases B-D add tests that exercise real product surfaces (Tauri commands, LLM flows, session lifecycle). Phase E automates the quality signal (flakiness + triage Gate 4). Phase F is optional cleanup. Each phase has 3-5 tasks; each task is a single commit.

**Tech Stack:** Python 3.13 + pytest + uv + httpx + AppleScript; coverage.py; cargo-llvm-cov for Rust; GitHub Actions (macos-15); tauri-plugin-mcp IPC; opencode-cli sidecar HTTP.

**Rough effort estimate:** 15-20 hours across all phases. Phases A+E+F are mechanical; B+C+D require real-backend (LiteLLM key) runs.

**Branch model:** Continue on `feature/gui-test-suite`. Each task commits directly. Rebase onto `origin/gpd` between phases. No PR until the whole phase group is green locally.

---

## File Structure

### New directories
- `packages/desktop/tests-gui/tests/ipc/` — Tauri command contract tests (Phase B)
- `packages/desktop/tests-gui/tests/lifecycle/` — session persistence tests (Phase D)
- `packages/desktop/tests-gui/scripts/flakiness/` — quarantine + triage-gate-4 helpers (Phase E)

### New files (by phase)

**Phase A — Coverage foundation**
- `packages/desktop/tests-gui/.coveragerc` — coverage.py config
- `packages/desktop/tests-gui/scripts/run_coverage.sh` — `uv run pytest --cov=gpd_tests --cov-report=html --cov-report=term` wrapper
- `packages/desktop/src-tauri/scripts/rust_coverage.sh` — `cargo llvm-cov --html` wrapper (release+debug)

**Phase B — Tauri command contract**
- `packages/desktop/tests-gui/gpd_tests/helpers/ipc.py` — `invoke_via_mcp(command, args, window_label="main") -> Any`
- `packages/desktop/tests-gui/tests/ipc/test_project_fs.py` — covers `project_fs.rs` commands
- `packages/desktop/tests-gui/tests/ipc/test_server.py` — covers `server.rs` commands
- `packages/desktop/tests-gui/tests/ipc/test_tex_compiler.py` — covers 8 `tex_compiler.rs` commands
- `packages/desktop/tests-gui/tests/ipc/test_lib_commands.py` — covers `lib.rs` / `gpd_setup.rs` commands
- `packages/desktop/tests-gui/tests/ipc/test_dependencies.py` — covers `dependencies.rs` + `tectonic.rs`
- `packages/desktop/tests-gui/tests/ipc/test_markdown.py` — covers `markdown.rs` + `cli.rs`

**Phase C — Real-backend LLM flows**
- `packages/desktop/tests-gui/tests/flows/test_tool_use_flow.py`
- `packages/desktop/tests-gui/tests/flows/test_abort_flow.py`
- `packages/desktop/tests-gui/tests/flows/test_multi_turn_flow.py`
- `packages/desktop/tests-gui/tests/flows/test_concurrent_sessions_flow.py`

**Phase D — Session persistence**
- `packages/desktop/tests-gui/tests/lifecycle/__init__.py`
- `packages/desktop/tests-gui/tests/lifecycle/conftest.py` — adds `restart_between_steps` fixture
- `packages/desktop/tests-gui/tests/lifecycle/test_session_persistence.py`
- `packages/desktop/tests-gui/tests/lifecycle/test_sidecar_respawn.py`

**Phase E — Flakiness + Gate 4**
- `.github/workflows/gpd-tests-flakiness.yml` — nightly cron
- `packages/desktop/tests-gui/scripts/flakiness/__init__.py`
- `packages/desktop/tests-gui/scripts/flakiness/report.py` — parses junit XML across N runs
- `packages/desktop/tests-gui/scripts/flakiness/quarantine.py` — adds `@pytest.mark.skip("quarantined: flake X/50")` via AST rewriting
- `packages/desktop/tests-gui/scripts/triage_gate4.py` — takes a test name + timestamp, grep-filters `git log --since=...` to touched paths
- `packages/desktop/tests-gui/conftest.py` — add `pytest_runtest_makereport` hook that writes `artifacts/triage_hint_{nodeid}.md` on failure

### Modified files
- `packages/desktop/tests-gui/pyproject.toml` — add `coverage[toml]` + `pytest-cov` as dev deps
- `packages/desktop/tests-gui/pytest.ini` — register `ipc` + `lifecycle` markers
- `packages/desktop/tests-gui/README.md` — document coverage + flakiness + ipc entry points
- `.github/workflows/gpd-tests-gui.yml` — add coverage artifact upload step
- `packages/desktop/src-tauri/Cargo.toml` — `[dev-dependencies]` add `llvm-tools-preview` if needed

---

## Phase A: Coverage Foundation

### Task A1: Wire Python coverage (coverage.py + pytest-cov)

**Files:**
- Modify: `packages/desktop/tests-gui/pyproject.toml` — add `pytest-cov` to `[tool.uv.dev-dependencies]`
- Create: `packages/desktop/tests-gui/.coveragerc`
- Create: `packages/desktop/tests-gui/scripts/run_coverage.sh`

- [ ] **Step 1: Add pytest-cov dep**

In `pyproject.toml` add `"pytest-cov>=5.0"` to the `[tool.uv.dev-dependencies]` list (or `[dependency-groups.dev]` — match whichever convention is already in the file).

Run: `cd packages/desktop/tests-gui && uv sync`

- [ ] **Step 2: Write `.coveragerc`**

```ini
[run]
source = gpd_tests
branch = True
omit =
    */__init__.py
    */tests_unit/*
    */tests/*
    */scripts/*
    */vendor/*
parallel = True

[report]
exclude_lines =
    pragma: no cover
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
show_missing = True
skip_covered = False
precision = 1

[html]
directory = coverage_html
```

- [ ] **Step 3: Create run_coverage.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest tests_unit \
  --cov=gpd_tests \
  --cov-branch \
  --cov-report=html \
  --cov-report=term-missing \
  --cov-report=xml \
  "$@"
echo
echo "HTML report: $(pwd)/coverage_html/index.html"
```

`chmod +x packages/desktop/tests-gui/scripts/run_coverage.sh`

- [ ] **Step 4: Run coverage locally, commit baseline**

Run: `bash packages/desktop/tests-gui/scripts/run_coverage.sh`
Expected: all 100 unit tests pass; terminal shows per-module coverage %.
Record the overall % in the commit message (e.g. "baseline 68%").

- [ ] **Step 5: Commit**

```bash
git add packages/desktop/tests-gui/pyproject.toml \
        packages/desktop/tests-gui/uv.lock \
        packages/desktop/tests-gui/.coveragerc \
        packages/desktop/tests-gui/scripts/run_coverage.sh
git commit -m "ci(coverage): add coverage.py + pytest-cov with baseline report"
```

### Task A2: Wire Rust coverage (cargo-llvm-cov)

**Files:**
- Create: `packages/desktop/src-tauri/scripts/rust_coverage.sh`
- Modify: `packages/desktop/src-tauri/Cargo.toml` — only if llvm-tools needs to be pinned

- [ ] **Step 1: Install cargo-llvm-cov locally**

Run: `cargo install cargo-llvm-cov`
If this warns about needing `llvm-tools-preview`: `rustup component add llvm-tools-preview`

- [ ] **Step 2: Create rust_coverage.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cargo llvm-cov clean --workspace
cargo llvm-cov --html --workspace --ignore-filename-regex='vendor/'
echo
echo "HTML report: $(pwd)/target/llvm-cov/html/index.html"
```

`chmod +x packages/desktop/src-tauri/scripts/rust_coverage.sh`

- [ ] **Step 3: Smoke test locally (debug build only — release takes too long)**

Run: `bash packages/desktop/src-tauri/scripts/rust_coverage.sh`
Expected: unit tests within src-tauri crates run under instrumentation; HTML report generated.
NOTE: if there are zero Rust unit tests today this will report 0% — that's fine, it confirms wiring.

- [ ] **Step 4: Commit**

```bash
git add packages/desktop/src-tauri/scripts/rust_coverage.sh
git commit -m "ci(coverage): add cargo-llvm-cov wrapper for Rust coverage reports"
```

### Task A3: Coverage artifact upload in CI

**Files:**
- Modify: `.github/workflows/gpd-tests-gui.yml`

- [ ] **Step 1: Read current workflow, find the smoke job's test step**

Read: `.github/workflows/gpd-tests-gui.yml`

- [ ] **Step 2: Replace the plain pytest invocation with the coverage wrapper**

Change `uv run pytest ...` inside the smoke-and-flows job's test step to `bash packages/desktop/tests-gui/scripts/run_coverage.sh <args>`. Keep the same marker arguments.

- [ ] **Step 3: Add upload-artifact step after test step**

```yaml
      - name: Upload coverage HTML
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-html-${{ matrix.job || 'smoke' }}
          path: packages/desktop/tests-gui/coverage_html/
          retention-days: 14

      - name: Upload coverage XML (for external tools)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-xml-${{ matrix.job || 'smoke' }}
          path: packages/desktop/tests-gui/coverage.xml
          retention-days: 14
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/gpd-tests-gui.yml
git commit -m "ci: upload coverage HTML and XML artifacts from smoke job"
```

### Task A4: First real CI run — push + observe + fix

**This task is driven by the actual CI result — don't prescribe fixes in advance.**

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feature/gui-test-suite
```

**This is a remote/shared-state action — PAUSE and confirm with the user before running `git push`. After confirmation, proceed.**

- [ ] **Step 2: Open the Actions tab, watch the smoke-and-flows job**

Expected outcomes:
- **Best case:** green, coverage artifact uploads, done. Move to Phase B.
- **Likely case:** one or more environment bugs (secret masking, brew install timing, sidecar probe, runner macOS version). Capture the failing step + log in a scratch note.
- **Worst case:** the test infrastructure itself breaks (conftest imports fail, fixture ordering issues only visible in CI). Treat as a Phase-A bug, fix before moving on.

- [ ] **Step 3: For each failure, open a dedicated subtask**

Don't fix multiple unrelated failures in one commit. Per-failure:
1. Reproduce locally if possible (may need `act` or a self-hosted macOS runner).
2. Fix.
3. Commit with message: `ci: fix <specific failure>`.
4. Push.
5. Re-observe.

- [ ] **Step 4: Once green, record the coverage baseline**

Download the HTML artifact, record the overall % in a note at the top of this plan file under "Phase A Results". This becomes the baseline we compare against after Phases B-D.

---

## Phase B: Tauri Command Contract Coverage

### Task B1: Enumerate every `#[tauri::command]` into a machine-readable catalog

**Files:**
- Create: `packages/desktop/tests-gui/tests/ipc/__init__.py` (empty)
- Create: `packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json`

- [ ] **Step 1: Write a one-shot extractor**

Create `packages/desktop/tests-gui/scripts/extract_tauri_commands.py`:

```python
"""Extract every #[tauri::command] from src-tauri/src/*.rs into a catalog.

Output schema:
  [{"name": str, "file": str, "line": int, "signature": str, "async": bool}]

Usage: python scripts/extract_tauri_commands.py > gpd_tests/fixtures/tauri_commands.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def extract(rs_file: Path) -> list[dict]:
    text = rs_file.read_text()
    results = []
    pattern = re.compile(
        r"#\[tauri::command\][^\n]*\n"
        r"(?P<sig>\s*(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>\w+)[^{]*)\{",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        sig = m.group("sig").strip()
        name = m.group("name")
        line = text[: m.start()].count("\n") + 1
        results.append(
            {
                "name": name,
                "file": rs_file.name,
                "line": line,
                "signature": sig,
                "async": "async fn" in sig,
            }
        )
    return results


def main() -> int:
    src_dir = Path(__file__).resolve().parents[3] / "src-tauri" / "src"
    all_commands = []
    for rs in sorted(src_dir.glob("*.rs")):
        all_commands.extend(extract(rs))
    json.dump(all_commands, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it and save the output**

```bash
cd packages/desktop/tests-gui
uv run python scripts/extract_tauri_commands.py > gpd_tests/fixtures/tauri_commands.json
```

Expected: 28 entries (matches `grep -c` count today). If count differs from 28 it means commands were added/removed since this plan — update the count in the README and move on.

- [ ] **Step 3: Write an invariant test**

Create `packages/desktop/tests-gui/tests_unit/test_tauri_commands_catalog.py`:

```python
"""The catalog must match the live source. Regenerate if this fails."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.unit
def test_catalog_matches_source():
    repo = Path(__file__).resolve().parents[3]
    script = repo / "packages/desktop/tests-gui/scripts/extract_tauri_commands.py"
    fixture = repo / "packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json"

    result = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
        check=True,
    )
    live = json.loads(result.stdout)
    stored = json.loads(fixture.read_text())
    assert live == stored, (
        "tauri_commands.json is stale — "
        "rerun: uv run python scripts/extract_tauri_commands.py > "
        "gpd_tests/fixtures/tauri_commands.json"
    )
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests_unit -q
git add packages/desktop/tests-gui/tests/ipc/__init__.py \
        packages/desktop/tests-gui/scripts/extract_tauri_commands.py \
        packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json \
        packages/desktop/tests-gui/tests_unit/test_tauri_commands_catalog.py
git commit -m "test(ipc): enumerate Tauri commands into a machine-readable catalog"
```

### Task B2: Build the `invoke_via_mcp` helper

**Files:**
- Create: `packages/desktop/tests-gui/gpd_tests/helpers/ipc.py`
- Create: `packages/desktop/tests-gui/tests_unit/test_helpers_ipc.py`

- [ ] **Step 1: Write the failing unit test first**

`tests_unit/test_helpers_ipc.py`:

```python
"""Shape-only tests for invoke_via_mcp. Validates we build the right Tauri
__TAURI_INTERNALS__.invoke() call string."""
from unittest.mock import MagicMock

import pytest

from gpd_tests.helpers.ipc import invoke_via_mcp


@pytest.mark.unit
def test_invoke_builds_correct_js():
    mcp = MagicMock()
    mcp.execute_js.return_value = '"result"'

    invoke_via_mcp(mcp, "read_project_file", {"path": "/tmp/x"})

    js = mcp.execute_js.call_args.args[0]
    assert "__TAURI_INTERNALS__.invoke" in js
    assert '"read_project_file"' in js
    assert '"/tmp/x"' in js


@pytest.mark.unit
def test_invoke_returns_parsed_json():
    mcp = MagicMock()
    mcp.execute_js.return_value = '{"ok": true, "value": 42}'

    result = invoke_via_mcp(mcp, "some_cmd", {})

    assert result == {"ok": True, "value": 42}


@pytest.mark.unit
def test_invoke_raises_on_tauri_error():
    from gpd_tests.helpers.ipc import IPCError

    mcp = MagicMock()
    mcp.execute_js.return_value = '{"__tauri_error__": "permission denied"}'

    with pytest.raises(IPCError, match="permission denied"):
        invoke_via_mcp(mcp, "cmd", {})
```

Run: `uv run pytest tests_unit/test_helpers_ipc.py -v`
Expected: FAIL (module not created yet).

- [ ] **Step 2: Implement `gpd_tests/helpers/ipc.py`**

```python
"""Invoke a Tauri command via MCP execute_js.

Tauri exposes `window.__TAURI_INTERNALS__.invoke(cmd, args)` which returns a
Promise. We wrap it in an async IIFE and return the JSON-serialized result.
Errors thrown by the command land in the Promise rejection path; we catch and
re-serialize as {"__tauri_error__": message} so execute_js doesn't timeout.
"""
from __future__ import annotations

import json
from typing import Any, Protocol


class IPCError(RuntimeError):
    """A Tauri command returned an error or threw an exception."""


class _MCPLike(Protocol):
    def execute_js(self, js: str, window_label: str = "main") -> str: ...


def invoke_via_mcp(
    mcp: _MCPLike,
    command: str,
    args: dict[str, Any] | None = None,
    *,
    window_label: str = "main",
) -> Any:
    args_json = json.dumps(args or {})
    cmd_json = json.dumps(command)
    js = f"""
(async () => {{
  try {{
    const r = await window.__TAURI_INTERNALS__.invoke({cmd_json}, {args_json});
    return JSON.stringify(r === undefined ? null : r);
  }} catch (e) {{
    return JSON.stringify({{ __tauri_error__: String(e && e.message ? e.message : e) }});
  }}
}})()
"""
    raw = mcp.execute_js(js, window_label=window_label)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise IPCError(f"non-JSON response from {command!r}: {raw!r}") from e

    if isinstance(parsed, dict) and "__tauri_error__" in parsed:
        raise IPCError(parsed["__tauri_error__"])
    return parsed
```

- [ ] **Step 3: Run unit tests, verify pass**

Run: `uv run pytest tests_unit/test_helpers_ipc.py -v`
Expected: PASS (3/3).

- [ ] **Step 4: Commit**

```bash
git add packages/desktop/tests-gui/gpd_tests/helpers/ipc.py \
        packages/desktop/tests-gui/tests_unit/test_helpers_ipc.py
git commit -m "feat(helpers): add invoke_via_mcp for Tauri command contract tests"
```

### Task B3: Contract tests for `project_fs.rs` (2 commands)

**Files:**
- Create: `packages/desktop/tests-gui/tests/ipc/test_project_fs.py`
- Modify: `packages/desktop/tests-gui/pytest.ini` — add `ipc` marker

- [ ] **Step 1: Add `ipc` marker to pytest.ini**

Add a line to the markers block:

```
    ipc: Tauri command contract test (requires GPD debug build)
```

- [ ] **Step 2: Read the two commands to understand their signatures**

Read: `packages/desktop/src-tauri/src/project_fs.rs` (entire file). Note each command's name, required args, and return type. The catalog fixture from Task B1 lists two entries — verify names and line numbers match.

- [ ] **Step 3: Write tests**

```python
"""Contract tests for project_fs.rs commands. Run against debug build."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from gpd_tests.helpers.ipc import IPCError, invoke_via_mcp


@pytest.mark.ipc
def test_read_project_file_happy_path(mcp):
    """read_project_file returns the file contents as a string."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("hello from contract test")
        path = f.name
    try:
        # Call whichever command reads files — name from project_fs.rs
        result = invoke_via_mcp(mcp, "read_project_file", {"path": path})
        assert "hello from contract test" in result
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.ipc
def test_read_project_file_rejects_outside_project(mcp):
    """A path outside the allowed project roots should fail."""
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, "read_project_file", {"path": "/etc/passwd"})


@pytest.mark.ipc
def test_write_project_file_happy_path(mcp):
    # If project_fs exposes a write command, test it here. If not, delete this
    # test and add a # TODO comment referencing project_fs.rs:53.
    ...
```

Adjust command names to match what's actually in `project_fs.rs` (the catalog fixture is authoritative).

- [ ] **Step 4: Run with GPD debug build running**

Run: `GPD_APP_PATH=/Applications/GPD\ Dev.app uv run pytest tests/ipc/test_project_fs.py -m ipc -v`
Expected: all pass (assuming GPD debug is running; skip gracefully otherwise via existing `mcp` fixture).

- [ ] **Step 5: Commit**

```bash
git add packages/desktop/tests-gui/pytest.ini \
        packages/desktop/tests-gui/tests/ipc/test_project_fs.py
git commit -m "test(ipc): contract tests for project_fs.rs commands"
```

### Task B4: Contract tests for `server.rs` (4 commands)

**Files:**
- Create: `packages/desktop/tests-gui/tests/ipc/test_server.py`

- [ ] **Step 1: Read `server.rs` end-to-end**

Note command names, args, return types. These relate to the opencode-cli sidecar — they might duplicate what we already test via HTTP. The point of contract tests is to verify the *Tauri wrapper* behaves correctly, not the server.

- [ ] **Step 2: Write tests (one per command)**

Follow the shape of Task B3: happy-path + one failure mode per command. Keep each test under 20 lines. Use `pytest.mark.ipc`.

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/ipc/test_server.py -m ipc -v
git add packages/desktop/tests-gui/tests/ipc/test_server.py
git commit -m "test(ipc): contract tests for server.rs commands"
```

### Task B5: Contract tests for `tex_compiler.rs` (8 commands — the biggest)

Same pattern. 8 commands means 8 happy-path tests + targeted failure tests where meaningful. Commit as one file.

### Task B6: Contract tests for `lib.rs` + `gpd_setup.rs` commands (9 total)

Same pattern. Split into two test files if cleaner, else one.

### Task B7: Contract tests for `dependencies.rs` + `tectonic.rs` (4 commands) + `markdown.rs` + `cli.rs` (2 commands)

Same pattern. Commit as one or two files.

### Task B8: Negative-space sweep — invoke-with-wrong-args + invoke-nonexistent

**Files:**
- Create: `packages/desktop/tests-gui/tests/ipc/test_ipc_negative.py`

- [ ] **Step 1: For each command in the catalog, add one "wrong-type argument" test**

Parametrize over the catalog fixture:

```python
@pytest.mark.ipc
@pytest.mark.parametrize("cmd", [c["name"] for c in CATALOG])
def test_command_rejects_wrong_arg_type(mcp, cmd):
    # Pass `null` instead of whatever the command expects.
    with pytest.raises(IPCError):
        invoke_via_mcp(mcp, cmd, {"__bogus__": None})
```

- [ ] **Step 2: Add one test for a made-up command name**

```python
@pytest.mark.ipc
def test_nonexistent_command_errors(mcp):
    with pytest.raises(IPCError, match="command"):
        invoke_via_mcp(mcp, "this_command_does_not_exist_xyzzy", {})
```

- [ ] **Step 3: Run + commit**

```bash
uv run pytest tests/ipc/test_ipc_negative.py -m ipc -v
git add packages/desktop/tests-gui/tests/ipc/test_ipc_negative.py
git commit -m "test(ipc): negative-space sweep across all 28 commands"
```

---

## Phase C: Real-backend LLM Flows

All tests in this phase require `GPD_TEST_ANTHROPIC_KEY` (or the LiteLLM-compatible key). Mark every test `@pytest.mark.flows @pytest.mark.real_backend`.

### Task C1: Tool-use flow (read-file tool)

**Files:**
- Create: `packages/desktop/tests-gui/tests/flows/test_tool_use_flow.py`

- [ ] **Step 1: Write the failing test**

```python
"""Send a message that triggers tool use. Assert the tool is invoked and the
assistant response includes the tool's result."""
import os
import tempfile
from pathlib import Path

import pytest

from gpd_tests.helpers.llm_tolerant import extract_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_assistant_reads_file_via_tool(http, real_backend_ready):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", dir=Path.home() / "tmp" if (Path.home() / "tmp").exists() else None, delete=False
    ) as f:
        sentinel = "psi-marker-7f3a2b"
        f.write(f"This file contains the sentinel: {sentinel}")
        path = f.name

    try:
        ses = http.create_session(directory=str(Path(path).parent))
        http.send_message(
            ses["id"],
            parts=[{
                "type": "text",
                "text": (
                    f"Read the file at {path} and report the unique sentinel "
                    "string you find inside. Don't invent one."
                ),
            }],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        msgs = http.messages(ses["id"])
        assistant_text = extract_text(msgs, role="assistant")
        assert sentinel in assistant_text, (
            f"assistant didn't echo the sentinel; full text: {assistant_text!r}"
        )
    finally:
        Path(path).unlink(missing_ok=True)
        http.delete_session(ses["id"])
```

- [ ] **Step 2: Run**

```bash
GPD_TEST_ANTHROPIC_KEY=<key> uv run pytest tests/flows/test_tool_use_flow.py \
  -m "flows and real_backend" -v
```

Expected: PASS (assistant reads file, quotes sentinel).

- [ ] **Step 3: Commit**

```bash
git add packages/desktop/tests-gui/tests/flows/test_tool_use_flow.py
git commit -m "test(flows): tool-use flow — assistant reads file via tool and quotes sentinel"
```

### Task C2: Mid-response abort flow

**Files:**
- Create: `packages/desktop/tests-gui/tests/flows/test_abort_flow.py`

- [ ] **Step 1: Understand abort endpoint**

Check the opencode-cli server source (`packages/opencode/src/server/server.ts` or similar) for an abort/cancel endpoint. It's usually `POST /session/:id/abort` or a signal via disconnecting the SSE stream.

- [ ] **Step 2: Add `abort()` to `HTTPClient` if missing**

If there's no `abort` method in `opencode_http.py`, add it. Write a unit test in `tests_unit/test_driver_http.py` covering the request shape before adding the real call.

- [ ] **Step 3: Write the abort flow test**

```python
import time
import threading

import pytest

from gpd_tests.helpers.llm_tolerant import extract_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_abort_stops_generation(http, real_backend_ready):
    ses = http.create_session()

    def _send():
        http.send_message(
            ses["id"],
            parts=[{
                "type": "text",
                "text": "Count from 1 to 1000 with one number per line, very slowly.",
            }],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )

    t = threading.Thread(target=_send, daemon=True)
    t.start()
    time.sleep(2.0)  # let some tokens flow
    http.abort(ses["id"])  # adjust to actual method
    t.join(timeout=10)

    msgs = http.messages(ses["id"])
    text = extract_text(msgs, role="assistant")
    # Should have at least some content but not reach "1000"
    assert len(text) > 0
    assert "1000" not in text
    http.delete_session(ses["id"])
```

- [ ] **Step 4: Run + commit**

### Task C3: Multi-turn conversation with context retention

**Files:**
- Create: `packages/desktop/tests-gui/tests/flows/test_multi_turn_flow.py`

- [ ] **Step 1: Write test**

```python
import pytest

from gpd_tests.helpers.llm_tolerant import extract_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_three_turn_context_retention(http, real_backend_ready):
    ses = http.create_session()
    try:
        # Turn 1: establish a fact
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "My favorite color is octarine. Remember this."}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        # Turn 2: unrelated
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "What is 2+2?"}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        # Turn 3: recall
        http.send_message(
            ses["id"],
            parts=[{"type": "text", "text": "What is my favorite color?"}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )

        msgs = http.messages(ses["id"])
        # Last assistant message should include "octarine"
        last_assistant = [m for m in msgs if m["info"]["role"] == "assistant"][-1]
        text = "".join(p.get("text", "") for p in last_assistant["parts"] if p.get("type") == "text")
        assert "octarine" in text.lower()
    finally:
        http.delete_session(ses["id"])
```

- [ ] **Step 2: Run + commit**

### Task C4: Concurrent sessions (parallel generation)

**Files:**
- Create: `packages/desktop/tests-gui/tests/flows/test_concurrent_sessions_flow.py`

- [ ] **Step 1: Write test**

```python
import concurrent.futures

import pytest

from gpd_tests.helpers.llm_tolerant import extract_text


@pytest.mark.flows
@pytest.mark.real_backend
def test_two_sessions_do_not_cross_contaminate(http, real_backend_ready):
    ses_a = http.create_session()
    ses_b = http.create_session()

    def _ask(ses_id: str, word: str) -> str:
        http.send_message(
            ses_id,
            parts=[{"type": "text", "text": f"Echo this exact word back: {word}"}],
            model_id="claude-4-7",
            provider_id="anthropic",
            agent="default",
        )
        return extract_text(http.messages(ses_id), role="assistant")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fa = ex.submit(_ask, ses_a["id"], "alpha-7f3a")
            fb = ex.submit(_ask, ses_b["id"], "bravo-2c4e")
            ta = fa.result(timeout=60)
            tb = fb.result(timeout=60)
        assert "alpha-7f3a" in ta
        assert "bravo-2c4e" in tb
        assert "alpha-7f3a" not in tb
        assert "bravo-2c4e" not in ta
    finally:
        http.delete_session(ses_a["id"])
        http.delete_session(ses_b["id"])
```

- [ ] **Step 2: Run + commit**

---

## Phase D: Session Persistence & Lifecycle

### Task D1: Session persists across app quit/relaunch

**Files:**
- Create: `packages/desktop/tests-gui/tests/lifecycle/__init__.py`
- Create: `packages/desktop/tests-gui/tests/lifecycle/conftest.py`
- Create: `packages/desktop/tests-gui/tests/lifecycle/test_session_persistence.py`
- Modify: `packages/desktop/tests-gui/pytest.ini` — add `lifecycle` marker

- [ ] **Step 1: Add marker**

Add to pytest.ini markers:
```
    lifecycle: session lifecycle test (destructive — quits + relaunches GPD)
```

- [ ] **Step 2: Write the test**

```python
"""After quitting and relaunching GPD, sessions must persist."""
import pytest

from gpd_tests.helpers.llm_tolerant import extract_text


@pytest.mark.lifecycle
@pytest.mark.flows
@pytest.mark.real_backend
def test_session_survives_quit_relaunch(http, app_state, real_backend_ready):
    ses = http.create_session()
    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "Remember the number 847392. Acknowledge."}],
        model_id="claude-4-7",
        provider_id="anthropic",
        agent="default",
    )
    pre_msgs = http.messages(ses["id"])
    assert len(pre_msgs) >= 2

    app_state.quit()
    app_state.wait_quit(timeout=15)
    app_state.launch()

    # After relaunch, the sidecar has been restarted — rediscover creds/port
    # via the session-scoped http fixture's bootstrap.
    post_msgs = http.messages(ses["id"])
    assert len(post_msgs) == len(pre_msgs)
    assert extract_text(post_msgs, role="user") == extract_text(pre_msgs, role="user")

    # Continue the conversation — memory should persist
    http.send_message(
        ses["id"],
        parts=[{"type": "text", "text": "What number did I ask you to remember?"}],
        model_id="claude-4-7",
        provider_id="anthropic",
        agent="default",
    )
    final = http.messages(ses["id"])
    last = [m for m in final if m["info"]["role"] == "assistant"][-1]
    text = "".join(p.get("text", "") for p in last["parts"] if p.get("type") == "text")
    assert "847392" in text
    http.delete_session(ses["id"])
```

Note: this test depends on `http` fixture being able to reconnect after relaunch. If it can't (because port/creds come from the old PID), extend the `http` fixture in the root conftest to accept a `rediscover()` method that re-runs `discover_sidecar_port` + `discover_sidecar_credentials`.

- [ ] **Step 3: Run + commit**

### Task D2: Multiple sessions all persist

**Files:**
- Create: `packages/desktop/tests-gui/tests/lifecycle/test_session_list_persistence.py`

- [ ] **Step 1: Write test**

```python
import pytest


@pytest.mark.lifecycle
def test_multiple_sessions_persist(http, app_state):
    # Create 3 sessions; don't send messages (keep cheap)
    ses_ids = [http.create_session()["id"] for _ in range(3)]
    pre = {s["id"] for s in http.sessions()}
    for sid in ses_ids:
        assert sid in pre

    app_state.quit()
    app_state.wait_quit(timeout=15)
    app_state.launch()

    post = {s["id"] for s in http.sessions()}
    for sid in ses_ids:
        assert sid in post, f"session {sid} lost across restart"

    # Cleanup
    for sid in ses_ids:
        http.delete_session(sid)
```

- [ ] **Step 2: Run + commit**

### Task D3: Sidecar respawn after kill

**Files:**
- Create: `packages/desktop/tests-gui/tests/lifecycle/test_sidecar_respawn.py`

- [ ] **Step 1: Write test**

```python
"""Killing the opencode-cli sidecar should trigger a respawn and continued service."""
import signal
import subprocess
import time

import pytest


@pytest.mark.lifecycle
def test_sidecar_respawns_after_sigkill(http, app_state):
    pre = http.health()
    assert pre["healthy"] is True

    # Find sidecar PID
    out = subprocess.run(
        ["pgrep", "-f", "opencode-cli.*serve"],
        capture_output=True, text=True, check=False,
    )
    pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    assert pids, "no opencode-cli running — test preconditions broken"
    old_pid = pids[0]

    # Kill it
    import os as _os
    _os.kill(old_pid, signal.SIGKILL)

    # Wait up to 30s for respawn
    deadline = time.monotonic() + 30
    new_pid = None
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True, text=True, check=False,
        )
        pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        candidates = [p for p in pids if p != old_pid]
        if candidates:
            new_pid = candidates[0]
            break
        time.sleep(0.5)
    assert new_pid is not None, "sidecar did not respawn within 30s"

    # http fixture must rediscover — touch it
    post = http.health()
    assert post["healthy"] is True
```

- [ ] **Step 2: Run + commit**

---

## Phase E: Flakiness Detection + Triage Gate 4 Automation

### Task E1: Nightly flakiness cron

**Files:**
- Create: `.github/workflows/gpd-tests-flakiness.yml`

- [ ] **Step 1: Write workflow**

```yaml
name: GPD tests — flakiness sweep

on:
  schedule:
    - cron: '17 7 * * *'  # daily at 07:17 UTC
  workflow_dispatch:

jobs:
  flakiness:
    runs-on: macos-15
    strategy:
      matrix:
        iteration: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    steps:
      - uses: actions/checkout@v4
      - name: Setup uv
        uses: astral-sh/setup-uv@v4
      - name: Install rust
        uses: dtolnay/rust-toolchain@stable
      - name: Setup bun
        uses: oven-sh/setup-bun@v1
      - name: Build debug app
        run: cd packages/desktop && bun install && bun tauri build --debug
      - name: Launch debug app
        run: open ./packages/desktop/src-tauri/target/debug/bundle/macos/GPD\ Dev.app
      - name: Wait for sidecar
        run: bash packages/desktop/tests-gui/scripts/wait_sidecar.sh 60
      - name: Run smoke N times
        run: |
          cd packages/desktop/tests-gui
          uv sync
          uv run pytest tests/smoke -m smoke \
            --junitxml=junit-${{ matrix.iteration }}.xml \
            -v || true
      - uses: actions/upload-artifact@v4
        with:
          name: junit-${{ matrix.iteration }}
          path: packages/desktop/tests-gui/junit-${{ matrix.iteration }}.xml
          retention-days: 7

  aggregate:
    needs: flakiness
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          path: junit/
      - name: Run flakiness report
        run: |
          python packages/desktop/tests-gui/scripts/flakiness/report.py junit/ \
            > flakiness_report.md
      - uses: actions/upload-artifact@v4
        with:
          name: flakiness-report
          path: flakiness_report.md
      - name: Post to PR / issue if anything is flaky
        # use github-script or gh CLI
        run: |
          if grep -q '^FLAKY' flakiness_report.md; then
            gh issue create --title "Flakiness detected" --body-file flakiness_report.md
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

(Matrix gives 10 runs — enough signal without burning runner budget. Ratchet up later.)

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/gpd-tests-flakiness.yml
git commit -m "ci(flakiness): nightly smoke sweep with aggregation + auto-issue"
```

### Task E2: Flakiness report aggregator

**Files:**
- Create: `packages/desktop/tests-gui/scripts/flakiness/__init__.py`
- Create: `packages/desktop/tests-gui/scripts/flakiness/report.py`
- Create: `packages/desktop/tests-gui/tests_unit/test_flakiness_report.py`

- [ ] **Step 1: Write the failing unit test**

```python
"""Report must correctly bucket test outcomes across N runs."""
from pathlib import Path
import textwrap

import pytest

from scripts.flakiness.report import aggregate


JUNIT_PASS = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest">
        <testcase name="test_a" classname="tests.smoke.test_x"/>
        <testcase name="test_b" classname="tests.smoke.test_y"/>
      </testsuite>
    </testsuites>
    """)

JUNIT_FAIL = textwrap.dedent("""\
    <?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest">
        <testcase name="test_a" classname="tests.smoke.test_x"/>
        <testcase name="test_b" classname="tests.smoke.test_y">
          <failure message="boom">tb</failure>
        </testcase>
      </testsuite>
    </testsuites>
    """)


@pytest.mark.unit
def test_all_pass_reports_no_flakes(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_PASS)
    result = aggregate(tmp_path)
    assert result["stable"] == ["tests.smoke.test_x::test_a", "tests.smoke.test_y::test_b"]
    assert result["flaky"] == []


@pytest.mark.unit
def test_mixed_pass_fail_reports_flaky(tmp_path):
    (tmp_path / "r1.xml").write_text(JUNIT_PASS)
    (tmp_path / "r2.xml").write_text(JUNIT_FAIL)
    (tmp_path / "r3.xml").write_text(JUNIT_PASS)
    result = aggregate(tmp_path)
    # test_b: 2/3 passed, 1/3 failed → flaky
    assert "tests.smoke.test_y::test_b" in [f["id"] for f in result["flaky"]]
    entry = next(f for f in result["flaky"] if f["id"] == "tests.smoke.test_y::test_b")
    assert entry["pass_count"] == 2
    assert entry["fail_count"] == 1
```

Run: `uv run pytest tests_unit/test_flakiness_report.py -v`
Expected: FAIL (module not created).

- [ ] **Step 2: Implement `report.py`**

```python
"""Aggregate JUnit XML files into a flakiness report.

Categories:
  - stable: passed in all runs
  - flaky: passed in at least one and failed in at least one
  - broken: failed in all runs

Output: dict with three keys. When run as script, formats as markdown.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any


def aggregate(junit_dir: Path) -> dict[str, Any]:
    passed_counts: dict[str, int] = defaultdict(int)
    failed_counts: dict[str, int] = defaultdict(int)
    total_runs = 0

    for xml_file in sorted(junit_dir.glob("*.xml")):
        total_runs += 1
        tree = ET.parse(xml_file)
        for tc in tree.iter("testcase"):
            tid = f"{tc.get('classname')}::{tc.get('name')}"
            failed = tc.find("failure") is not None or tc.find("error") is not None
            if failed:
                failed_counts[tid] += 1
            else:
                passed_counts[tid] += 1

    all_ids = set(passed_counts) | set(failed_counts)
    stable = sorted(tid for tid in all_ids if failed_counts[tid] == 0)
    broken = sorted(tid for tid in all_ids if passed_counts[tid] == 0)
    flaky_ids = sorted(tid for tid in all_ids if passed_counts[tid] > 0 and failed_counts[tid] > 0)
    flaky = [
        {
            "id": tid,
            "pass_count": passed_counts[tid],
            "fail_count": failed_counts[tid],
            "total_runs": total_runs,
        }
        for tid in flaky_ids
    ]
    return {"stable": stable, "flaky": flaky, "broken": broken, "total_runs": total_runs}


def to_markdown(agg: dict[str, Any]) -> str:
    lines = [f"# Flakiness report ({agg['total_runs']} runs)"]
    if agg["flaky"]:
        lines.append("")
        lines.append("## FLAKY")
        for f in agg["flaky"]:
            lines.append(f"- `{f['id']}` — {f['pass_count']}/{f['total_runs']} passed")
    if agg["broken"]:
        lines.append("")
        lines.append("## BROKEN")
        for tid in agg["broken"]:
            lines.append(f"- `{tid}` — failed all runs")
    if not agg["flaky"] and not agg["broken"]:
        lines.append("")
        lines.append("_All tests stable._")
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: report.py <junit_dir>", file=sys.stderr)
        return 2
    agg = aggregate(Path(sys.argv[1]))
    sys.stdout.write(to_markdown(agg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run unit tests, verify pass, commit**

### Task E3: Triage Gate 4 helper

**Files:**
- Create: `packages/desktop/tests-gui/scripts/triage_gate4.py`
- Create: `packages/desktop/tests-gui/tests_unit/test_triage_gate4.py`

- [ ] **Step 1: Write the failing test**

```python
"""triage_gate4 takes a test file and timestamp, returns recent product-code commits."""
import subprocess
from unittest.mock import patch

import pytest

from scripts.triage_gate4 import find_related_commits


@pytest.mark.unit
def test_find_related_commits_filters_to_product_paths():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = (
            "abc123 fix(server): foo\n"
            "def456 test(ipc): bar\n"
            "ghi789 feat(ui): baz\n"
        )
        mock_run.return_value.returncode = 0
        results = find_related_commits(
            since="2026-04-19",
            paths=["packages/desktop/src-tauri/", "packages/desktop/src/"],
        )
        assert len(results) >= 1
        assert all("sha" in r and "subject" in r for r in results)
```

- [ ] **Step 2: Implement**

```python
"""Triage Gate 4: given a failing test + time window, surface product-code
commits that landed in the window. Helps tell "harness bug" from "product regression".
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any


def find_related_commits(
    since: str,
    paths: list[str] | None = None,
    repo_root: str | None = None,
) -> list[dict[str, Any]]:
    cmd = ["git", "log", f"--since={since}", "--pretty=format:%H\t%s"]
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    r = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    results = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        results.append({"sha": sha, "subject": subject})
    return results


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: triage_gate4.py <since_iso_date>", file=sys.stderr)
        return 2
    commits = find_related_commits(
        since=sys.argv[1],
        paths=["packages/desktop/src-tauri/", "packages/desktop/src/"],
    )
    if not commits:
        print(f"No product-code commits since {sys.argv[1]}.")
        return 0
    print(f"Product-code commits since {sys.argv[1]}:")
    for c in commits:
        print(f"  {c['sha'][:8]} {c['subject']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run + commit**

### Task E4: Wire Gate 4 into pytest failures

**Files:**
- Modify: `packages/desktop/tests-gui/conftest.py`

- [ ] **Step 1: Add a makereport hook**

At the end of `conftest.py`, add:

```python
def pytest_runtest_makereport(item, call):
    """On failure, write a triage hint markdown to artifacts/ linking product commits."""
    if call.when != "call" or call.excinfo is None:
        return
    try:
        from scripts.triage_gate4 import find_related_commits
    except ImportError:
        return  # script not yet available — silent skip
    import datetime as _dt
    from pathlib import Path as _Path

    now = _dt.datetime.now()
    yesterday = (now - _dt.timedelta(hours=24)).date().isoformat()
    commits = find_related_commits(
        since=yesterday,
        paths=["packages/desktop/src-tauri/", "packages/desktop/src/"],
    )
    if not commits:
        return

    artifacts = _Path(__file__).parent / "artifacts" / "triage_hints"
    artifacts.mkdir(parents=True, exist_ok=True)
    safe = item.nodeid.replace("/", "__").replace("::", "---")
    hint = artifacts / f"{safe}.md"
    lines = [f"# Triage hint for {item.nodeid}", "", f"Window: last 24h (since {yesterday})", ""]
    lines.append(f"## Product-code commits that may be related ({len(commits)})")
    for c in commits:
        lines.append(f"- `{c['sha'][:8]}` {c['subject']}")
    hint.write_text("\n".join(lines) + "\n")
```

- [ ] **Step 2: Exercise the hook with a synthetic failure**

Write a throwaway `tests_unit/test_makereport_hook.py` that deliberately fails, then verify `artifacts/triage_hints/<node>.md` exists. Delete the throwaway test before committing (we only want to verify the hook works manually).

- [ ] **Step 3: Commit**

```bash
git add packages/desktop/tests-gui/conftest.py
git commit -m "test(triage): Gate-4 hook writes product-code commits to artifacts on test failure"
```

---

## Phase F: Optional Cleanup (if time permits)

### Task F1: Visual regression baseline

- [ ] Capture welcome screen + main chat view via `screencapture` from AppleScript.
- [ ] Store as `tests/visual/baselines/{macos15,arm64}/welcome.png` etc.
- [ ] Add a `@pytest.mark.visual` test that uses PIL pixel-diff against baseline.

### Task F2: i18n locale switch smoke

- [ ] Find the locale-switch UI (Settings → Language).
- [ ] Write a smoke test that flips locale → asserts the welcome text matches the corresponding `fr`/`es`/`de` value from `en.json`'s companion files.

### Task F3: Clean up orphaned worktrees

- [ ] `git worktree list` → find `worktree-agent-*` entries.
- [ ] For each, confirm its branch has been merged or is safe to discard, then `git worktree remove` + `git branch -D`.

---

## Execution Rhythm

- **Between every phase:** rebase onto `origin/gpd`; re-run `uv run pytest tests_unit -q` to confirm no regression.
- **Between every task:** commit; brief status line to user; move to next.
- **Subagent dispatch:** prefer 1 worktree agent per task. For Phase B (repetitive contract tests) consider launching multiple agents in parallel, one per command file.
- **Review:** after Phase A completes, spec-compliance + code-quality review before Phase B starts. Same between Phase C and Phase D (most risk-dense transitions).
- **Stop conditions:** if CI run in A4 reveals infra problems that require Tauri/opencode-cli source changes (outside the test harness), stop and flag to user — don't silently patch product code.

---

## Phase A Results (fill in after A4 completes)

_TBD_

## Phase B Results

_TBD_

## Phase C/D/E Results

_TBD_
