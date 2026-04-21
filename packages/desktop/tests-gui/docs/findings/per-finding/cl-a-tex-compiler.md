# CL-A: tex_compiler failures

File under test: `packages/desktop/src-tauri/src/tex_compiler.rs`
Test file: `packages/desktop/tests-gui/tests/ipc/test_tex_compiler.py`
Failure evidence: `packages/desktop/tests-gui/runs/ipc-{1,2,3}.xml` (deterministic 3/3 across sweep iterations)

---

## Test 1: test_detect_tex_root_honors_magic_comment

- **Failure message:** `KeyError: 'stub'` raised during fixture setup, at `test_tex_compiler.py:88` where the test calls `TEX_WITH_MAGIC_ROOT_TEMPLATE.format(root=root.name)`.
  ```
  child.write_text(
  >           TEX_WITH_MAGIC_ROOT_TEMPLATE.format(root=root.name)
          )
  E       KeyError: 'stub'
  ```
- **Test expects:** Given a child `.tex` file whose first line is a `% !TEX root = main.tex` magic comment, `detect_tex_root` returns the resolved absolute path to `main.tex`.
- **Command actually does:** `tex_compiler.rs:180-222` — reads the first 5 lines of the start file, regex-matches `! TEX root` via `magic_root_comment` (`tex_compiler.rs:889-909`), resolves the ref relative to the start file's parent (`resolve_root_relative`, `tex_compiler.rs:911-918`), and returns the resolved path if it exists. The command itself is fine; the test never reaches it.
- **Root cause:** Pure harness bug in the test template. The template is defined at `test_tex_compiler.py:38-41`:
  ```python
  TEX_WITH_MAGIC_ROOT_TEMPLATE = (
      "% !TEX root = {root}\n"
      r"\input{stub}"
  )
  ```
  The second line is a raw string, so `\i` is preserved, but `{stub}` is still a Python `str.format()` placeholder. When the test calls `.format(root=root.name)` at line 88, Python's format parser sees two placeholders (`{root}` and `{stub}`) and raises `KeyError: 'stub'` because `stub` was not supplied. The author likely intended `{stub}` to be literal LaTeX — either `{{stub}}` (escaped braces for `.format`) or `.replace("{root}", root.name)` would work.
- **Label:** HARNESS_BUG
- **Confidence:** high
- **Fix hint:** Escape the literal brace in the template, e.g. `r"\input{{stub}}"`, or switch to a different substitution mechanism (f-string captured at template-use time, or `str.replace`). The Rust side needs no changes — the Rust unit test `magic_comment_variants` already verifies the parser.

---

## Test 2: test_compile_tex_rejects_missing_source

- **Failure message:**
  ```
  E       AssertionError: Regex pattern did not match.
  E         Expected regex: re.compile("(?i)not found|doesn't exist|hasn't been moved", re.IGNORECASE)
  E         Actual message: 'TeX root file does not exist: /…/does-not-exist.tex'
  ```
  (from `ipc-1.xml:386-388`; identical across ipc-2 and ipc-3)
- **Test expects:** `compile_tex` raises `IPCError` whose message matches one of `not found`, `doesn't exist`, `hasn't been moved` (regex alternation, case-insensitive).
- **Command actually does:** The **current source** at `tex_compiler.rs:267` returns the friendly string:
  ```rust
  return Err(format!("LaTeX source file not found: {root}. Make sure the file exists and hasn't been moved."));
  ```
  which WOULD match both `not found` and `hasn't been moved`. But the **running debug build** returns the older pre-copy-wave-3 string `"TeX root file does not exist: {root}"`, which matches `doesn't exist` only via a loose read ("does not" vs "doesn't" — different spellings, regex requires the apostrophe form).
- **Root cause:** Stale binary. Commit `64e39c1` ("copy(wave-3): friendly error messages from Rust + frontend wrappers") rewrote the Err string from `"TeX root file does not exist: {root}"` → `"LaTeX source file not found: {root}. Make sure the file exists and hasn't been moved."`. This commit is an ancestor of HEAD (`git merge-base HEAD 64e39c1` = `64e39c1`), so the source tree already has the new message. The test regex was clearly written to match the **new** message (`not found|hasn't been moved`, plus `doesn't exist` as defensive belt-and-suspenders). But the Tauri sidecar binary the tests hit was compiled from a pre-`64e39c1` state and still emits the old string. The "does not exist" the running app returned doesn't match `doesn't exist` because the regex insists on the contraction with apostrophe.
- **Label:** REGRESSION_ON_BRANCH (stale sidecar build — product code and test are mutually consistent at HEAD, but the deployed binary lags)
- **Confidence:** high
- **Fix hint:** Rebuild the Tauri debug sidecar on this branch before re-running the IPC sweep — `cargo build` (or whatever the test harness uses to produce the binary in `src-tauri/target/debug`) should pick up the friendly message from line 267 and the regex will match via `not found` / `hasn't been moved`. No test or product change needed. As a belt-and-suspenders improvement the regex could also tolerate `does not exist` (space-separated) in addition to `doesn't exist`.

---

## Test 3: test_parse_tex_log_rejects_missing_file

- **Failure message:**
  ```
  E       AssertionError: Regex pattern did not match.
  E         Expected regex: re.compile('(?i)open|re-render|error log', re.IGNORECASE)
  E         Actual message: 'Failed to read log /…/does-not-exist.log: No such file or directory (os error 2)'
  ```
  (from `ipc-1.xml:505-507`; identical across ipc-2 and ipc-3)
- **Test expects:** `parse_tex_log` raises `IPCError` matching `open|re-render|error log` (case-insensitive).
- **Command actually does:** The **current source** at `tex_compiler.rs:580-581` returns:
  ```rust
  let raw_log = std::fs::read_to_string(&log_path)
      .map_err(|e| format!("Couldn't open the LaTeX error log. Try re-rendering. ({e})"))?;
  ```
  which matches all three alternates (`open`, `re-render`, `error log`). But the running binary emits `"Failed to read log {path}: {os-error}"` — the pre-copy-wave-3 form — which matches none of the three alternates (`Failed to read log` has neither "open" as a whole word intent nor "re-render" nor "error log"; note `log` alone is not in the regex).
- **Root cause:** Same stale-binary cause as Test 2. Commit `64e39c1` rewrote the map_err closure from `"Failed to read log {log_path}: {e}"` → `"Couldn't open the LaTeX error log. Try re-rendering. ({e})"`. The test regex was written against the new copy, but the running binary still emits the old one.
- **Label:** REGRESSION_ON_BRANCH (same stale-sidecar cause as Test 2)
- **Confidence:** high
- **Fix hint:** Rebuild the Tauri debug sidecar. No product or test change needed.

---

## Common thread

**Yes — Tests 2 and 3 share a single root cause: stale Tauri sidecar binary.**

Both regex failures are the test suite asserting against the post-`64e39c1` "friendly error message" copy (committed at `64e39c1`, which is an ancestor of HEAD `4b28044`), but the deployed GPD Dev binary those tests ran against was built from a pre-`64e39c1` tree. Rebuilding the sidecar is the single fix for both. The evidence is unambiguous:

| command          | source at HEAD (tex_compiler.rs)                                             | message the test saw                            | regex alternates                           |
| ---------------- | ---------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------ |
| `compile_tex`    | `LaTeX source file not found: {root}. Make sure the file exists and hasn't been moved.` (line 267) | `TeX root file does not exist: /…/…`            | `not found \| doesn't exist \| hasn't been moved` |
| `parse_tex_log`  | `Couldn't open the LaTeX error log. Try re-rendering. ({e})` (line 581)      | `Failed to read log /…/…: No such file… (os error 2)` | `open \| re-render \| error log`                 |

Test 1 is unrelated — a plain Python template bug (`KeyError: 'stub'`) in the test harness at line 88, not a contract mismatch at all. The IPC command is never invoked; the fixture builder dies before the `invoke_via_mcp` call.

## Recommendation priority

1. Fix Test 1 by escaping `{stub}` in the template (one-line harness fix).
2. Rebuild the Tauri debug sidecar so the IPC sweep runs against the same source tree that shipped the friendly-copy commit; Tests 2 and 3 should go green without touching test regexes or product code.
3. Optional: after (2), consider broadening the two regexes in Tests 2/3 to also tolerate pre-copy-wave-3 phrasings, so a future debug-build lag doesn't produce the same false positive. This is defensive; the suite should primarily be run against a fresh build.
