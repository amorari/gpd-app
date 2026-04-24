# Tauri Commands — Deep Inventory (G1.3)

Read-only audit of all 28 `#[tauri::command]` handlers declared in `packages/desktop/src-tauri/src/*.rs`. Each entry captures arg struct fields, return shape, side effects, idempotency, and recommended Phase G4 tests.

Source of truth for the catalog: `packages/desktop/tests-gui/gpd_tests/fixtures/tauri_commands.json`.
Existing IPC tests cross-referenced from `packages/desktop/tests-gui/tests/ipc/`.

---

### `install_cli` (cli.rs:129, `async: false`)

**Purpose:** Invokes the repo's `install` shell script (embedded at compile time) to symlink the bundled sidecar binary into `~/.opencode/bin/opencode`.

**Args:** `app: tauri::AppHandle` (no user-supplied args).

**Returns:** `Ok(String)` absolute install path; `Err(String)` on missing sidecar, script write failure, chmod failure, or non-zero script exit.

**Side effects:** writes `<tempdir>/opencode-install.sh`, sets mode 0o755, spawns it as a subprocess, then deletes it. The script writes into `~/.opencode/bin/`, may append to shell rc files (`~/.zshrc`, `~/.bashrc`) to update PATH. Returns `Err("CLI installation is only supported on macOS & Linux")` on non-Unix.

**Idempotency:** mutating. Re-running overwrites the binary and may re-append a rc-file line depending on the install script's internal idempotency.

**Safety classification:** UNSAFE — mutates `~/.opencode/bin` and shell init files.

**Test coverage today:**
- Happy path: SKIPPED (`test_tectonic_markdown_cli.py::test_install_cli_platform_gated` — calls only on non-Unix to assert platform gate; Unix branch is skipped).
- Failure path: partial (non-Unix "only supported" guard asserted indirectly).
- Location: `tests/ipc/test_tectonic_markdown_cli.py:68-78`.

**Recommended tests to add:**
- Gate the real happy path behind `PYTEST_OPTIN_MUTATE_SYSTEM=1`; capture state of `~/.opencode/bin/opencode` pre-call, invoke, assert file exists and is executable, then restore backup.
- Mock-less sandbox: copy `$HOME` to a temp dir, set `HOME=...` in the subprocess env the sidecar was spawned with (infeasible without restart). Mark as out-of-scope for unattended suites.
- Windows runner: assert exact error string equals `"CLI installation is only supported on macOS & Linux"`.
- Missing-sidecar branch: rename bundled sidecar, expect `"Sidecar binary not found"`.

---

### `install_git_macos` (dependencies.rs:35, `async: true`)

**Purpose:** Launches `xcode-select --install` to trigger the Command Line Tools installer dialog on macOS.

**Args:** none.

**Returns:** `Ok(InstallResult { launched: bool, message: String })` — `launched: true` both when the installer kicks off and when tools are already installed. `Err(String)` when `xcode-select` exits non-zero with an unrecognised message, or when spawn itself fails.

**Side effects:** spawns `xcode-select --install`; on a fresh Mac this opens a modal system dialog. Network is touched only after the user confirms the dialog. On Linux/Windows returns an early `Err`.

**Idempotency:** effectively idempotent — second call typically returns the "already installed" branch, still shaped as `Ok`.

**Safety classification:** INTERACTIVE (on macOS — OS-level modal) / SAFE (on non-macOS — early error return).

**Test coverage today:**
- Happy path: SKIPPED on macOS (`test_dependencies.py::test_install_git_macos_platform_gated`).
- Failure path: YES — on non-macOS the command returns the platform-gate error.
- Location: `tests/ipc/test_dependencies.py:22-36`.

**Recommended tests to add:**
- On macOS runner with Command Line Tools pre-installed, assert `launched == true` and `message` contains `"already installed"`.
- On macOS with `PYTEST_OPTIN_MUTATE_SYSTEM=1` missing, force-skip to avoid the modal dialog in CI.
- Assert error string prefix on Linux/Windows.

---

### `install_git_windows` (dependencies.rs:74, `async: true`)

**Purpose:** Installs Git via `winget install --id Git.Git` on Windows.

**Args:** none.

**Returns:** `Ok(InstallResult)` when winget exits 0; `Err(String)` otherwise (includes stdout + stderr).

**Side effects:** spawns `winget` subprocess; may trigger UAC; mutates system PATH via Git installer; network download.

**Idempotency:** mutating (re-running usually reports "already installed" via winget's own idempotency, but still counts as a state mutation attempt).

**Safety classification:** INTERACTIVE (UAC + installer dialog) on Windows / SAFE on non-Windows.

**Test coverage today:**
- Happy path: SKIPPED on Windows.
- Failure path: YES — non-Windows returns the platform-gate error.
- Location: `tests/ipc/test_dependencies.py:44-62`.

**Recommended tests to add:**
- On Windows with Git pre-installed, assert winget's "no-op" success return shape.
- Assert error prefix on macOS/Linux equals `"install_git_windows is only available on Windows"`.

---

### `linux_install_hint` (dependencies.rs:114, `async: false`)

**Purpose:** Returns a copy-pastable shell snippet for the given tool; no execution. Purely informational.

**Args:** `tool: String`.

**Returns:** `String` — one of the hardcoded snippets (`"sudo apt install git"` etc.) or `""` for unknown tool.

**Side effects:** none.

**Idempotency:** idempotent (pure function).

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (parametrised across git/python/python-venv/latex/tectonic/pdf-tools).
- Failure path: YES (unknown tool → empty string).
- Location: `tests/ipc/test_dependencies.py:75-95`.

**Recommended tests to add:**
- Stability pin: snapshot-assert the exact snippet strings so any accidental edit to the hardcoded table triggers a test failure.
- Case-sensitivity: assert `"Git"` (uppercase) returns `""`, documenting the case-sensitive match.

---

### `repair_gpd_venv` (gpd_setup.rs:123, `async: true`)

**Purpose:** Deletes `~/.config/gpd/.venv` and the `.gpd-initialized` marker, then re-runs the full first-run setup (Python provisioning → venv creation → `pip install get-physics-done[arxiv]` → `gpd install opencode` → config injection).

**Args:** `app: tauri::AppHandle`.

**Returns:** `Ok(())` on successful re-setup; `Err(String)` on filesystem errors, uv missing, Python install timeout, pip failure, or GPD install failure.

**Side effects:** removes `~/.config/gpd/.venv`, `.gpd-initialized`; creates them afresh. Spawns bundled `uv`, network calls to Railway LiteLLM endpoint, git cloning `psi-oss/get-physics-done`. Typical runtime: 2-5 minutes.

**Idempotency:** destructive-then-reconstructive. Equivalent to "reinstall", not a no-op.

**Safety classification:** UNSAFE — wipes and rewrites `~/.config/gpd`. Also takes multi-minute network time.

**Test coverage today:**
- Happy path: SKIPPED (`test_lib_commands.py::test_repair_gpd_venv_skipped_destructive` — static skip marker).
- Failure path: NO.
- Location: `tests/ipc/test_lib_commands.py:168-177`.

**Recommended tests to add:**
- Gated real-behavior test behind `PYTEST_OPTIN_MUTATE_SYSTEM=1` that snapshots `~/.config/gpd`, invokes, asserts marker + venv re-created, measures wall-clock <600s, then restores snapshot.
- Fault-injection via env override of `XDG_CONFIG_HOME` to a tmp path: invoke, assert `.venv` exists in tmp + marker written.
- Error path: make the bundled uv resource path unreadable (chmod 000) and assert the error string starts with "GPD installation is missing a required helper (uv)" (requires running outside the app binary).

---

### `kill_sidecar` (lib.rs:77, `async: false`, return: `()`)

**Purpose:** Sends a kill signal to the spawned opencode sidecar process via its `CommandChild` handle.

**Args:** `app: AppHandle` (picked from `try_state<ServerState>`).

**Returns:** `()` — no error type. Idle logs when state is absent.

**Side effects:** sends SIGTERM-equivalent to the sidecar subprocess. Subsequent HTTP calls to the sidecar fail. The app will not auto-respawn the sidecar until the next launch.

**Idempotency:** destructive (calling it once kills the sidecar; second call is a no-op because `child.lock().take()` returns `None`).

**Safety classification:** UNSAFE — breaks every subsequent test in the sweep. Exists in the registry purely so the `RunEvent::Exit` branch can invoke it on app shutdown.

**Test coverage today:**
- Happy path: SKIPPED (`test_lib_commands.py::test_kill_sidecar_skipped_destructive`).
- Failure path: NO.
- Location: `tests/ipc/test_lib_commands.py:30-43`.

**Recommended tests to add:**
- Dedicated fresh-app fixture test: launch app, invoke kill_sidecar, poll sidecar HTTP health → expect connection refused within 5s, then quit app.
- Idempotency: invoke twice, assert no error emitted both times.
- This test must be in its own file with a `session` scope teardown that re-launches the app.

---

### `await_initialization` (lib.rs:100, `async: true`)

**Purpose:** Blocks until the sidecar credentials are ready and streams `InitStep` progress events through a Channel. Called exactly once by the frontend on boot.

**Args:** `state: State<SidecarReady>`, `init_state: State<InitState>`, `events: Channel<InitStep>` (Tauri-injected).

**Returns:** `Ok(ServerReadyData { url, username, password })`; `Err("Failed to get sidecar data")` if the oneshot dropped.

**Side effects:** reads watch channel; sends messages on the caller-provided Channel. No filesystem or network.

**Idempotency:** the underlying `Shared<oneshot::Receiver>` can be awaited multiple times, but the init-state stream only fires `Done` once; second callers get only the final value.

**Safety classification:** SAFE_WITH_FIXTURE — needs a running app with the `SidecarReady` + `InitState` managed states.

**Test coverage today:**
- Happy path: NO (requires a real Channel handle from the frontend; MCP plugin can't synthesize `tauri::ipc::Channel`).
- Failure path: YES — calling with empty args errors because the Channel parameter isn't forged (`test_lib_commands.py::test_await_initialization_requires_channel_arg`).
- Location: `tests/ipc/test_lib_commands.py:48-57`.

**Recommended tests to add:**
- Document the Channel arg shape — if MCP supports creating a Channel, invoke and assert the three-field `ServerReadyData` on first call.
- Property: assert `.url` matches `^http://127\.0\.0\.1:\d+$` and `.password` is a UUID.
- Time-bounded: assert the call returns within 30s of app launch.

---

### `check_app_exists` (lib.rs:137, `async: false`)

**Purpose:** Platform-specific probe for whether a named application is installed (checks `/Applications`, `~/Applications`, `/System/Applications`, and PATH on macOS; equivalent on Windows; always `true` on Linux).

**Args:** `app_name: &str`.

**Returns:** `bool`.

**Side effects:** stats several filesystem paths; on macOS runs `which <app_name>`.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_check_app_exists_returns_bool` — asserts Finder returns `true` on macOS).
- Failure path: YES (`test_check_app_exists_false_for_nonsense_name`).
- Location: `tests/ipc/test_lib_commands.py:61-80`.

**Recommended tests to add:**
- Per-platform: on Linux assert always `true` regardless of input (documents the always-true branch).
- Pathological inputs: empty string, very long string (>4KiB), Unicode name — must not panic.
- Shell injection probe: pass `"; rm -rf /tmp/xyz"` — assert subprocess isn't influenced (the `which` call takes a single arg).

---

### `resolve_app_path` (lib.rs:156, `async: false`)

**Purpose:** Returns an absolute path for an app name; on Windows uses registry lookup, on macOS/Linux echoes the input.

**Args:** `app_name: &str`.

**Returns:** `Option<String>`.

**Side effects:** on Windows reads HKEY registry keys; on non-Windows pure.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_resolve_app_path_returns_string_or_null`).
- Failure path: NO.
- Location: `tests/ipc/test_lib_commands.py:84-90`.

**Recommended tests to add:**
- Non-Windows identity check: assert `resolve_app_path("Finder") == "Finder"`.
- Assert `resolve_app_path("") == ""` on non-Windows (documents identity behavior).
- Windows registry probe: on Windows runner, assert `"Notepad"` resolves to a path ending in `notepad.exe`.

---

### `open_path` (lib.rs:172, `async: false`)

**Purpose:** Opens a file, directory, or URL via the platform opener plugin (`open` on macOS, `xdg-open` on Linux, `start` on Windows; PowerShell special-case on Windows).

**Args:** `path: String`, `app_name: Option<String>`.

**Returns:** `Ok(())`; `Err(String)` when opener plugin rejects.

**Side effects:** spawns the OS's native file opener — actually opens a file or URL in the user's default handler. Visible UI effect.

**Idempotency:** mutating (each call opens another window/tab).

**Safety classification:** INTERACTIVE — spawns user-visible windows; would disrupt the test machine.

**Test coverage today:**
- Happy path: NO (explicitly avoided — would pollute the desktop).
- Failure path: YES (`test_open_path_missing_required_arg_errors`).
- Location: `tests/ipc/test_lib_commands.py:94-103`.

**Recommended tests to add:**
- Path-traversal input: `"../../etc/passwd"` — document whether it errors or silently calls the opener.
- Non-existent path: assert error returned for `/nonexistent/xyz`.
- Real-behavior test gated behind `PYTEST_OPTIN_OPEN_WINDOWS=1`: open a tmp file, sleep 1s, kill opener child, cleanup.

---

### `get_display_backend` (lib.rs:234, `async: false`)

**Purpose:** Reports the preferred Linux display backend (`Wayland` or `Auto`); `None` on non-Linux.

**Args:** none.

**Returns:** `Option<LinuxDisplayBackend>` where `LinuxDisplayBackend` is `Wayland` or `Auto` (`#[serde(rename_all = "camelCase")]`).

**Side effects:** reads `~/.config/opencode/linux-display-backend` (via `linux_display::read_wayland`); nothing on non-Linux.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_get_display_backend_shape`).
- Failure path: N/A (no error path exposed).
- Location: `tests/ipc/test_lib_commands.py:107-113`.

**Recommended tests to add:**
- On macOS, assert `None` exactly.
- On Linux runner: write a known value via `set_display_backend`, then `get_display_backend` → assert round-trip matches.

---

### `set_display_backend` (lib.rs:251, `async: false`)

**Purpose:** Writes the Linux display-backend preference; no-op on other platforms.

**Args:** `app: AppHandle`, `backend: LinuxDisplayBackend` (`Wayland` | `Auto`).

**Returns:** `Ok(())` always on non-Linux; on Linux bubbles `linux_display::write_wayland` errors.

**Side effects:** writes `~/.config/opencode/linux-display-backend` on Linux; nothing elsewhere.

**Idempotency:** mutating, but deterministic (writing the same value twice is a no-op).

**Safety classification:** SAFE_WITH_FIXTURE on Linux (touches `~/.config/opencode`); SAFE on macOS/Windows.

**Test coverage today:**
- Happy path: YES (`test_set_display_backend_roundtrip`).
- Failure path: partial — no test for invalid backend value.
- Location: `tests/ipc/test_lib_commands.py:117-141`.

**Recommended tests to add:**
- Negative: invoke with `{"backend": "invalid"}` — expect deserialization error.
- Linux: write `"wayland"`, read back, write `"auto"`, read back; cleanup restores original.
- Assert that passing no args errors (currently not tested).

---

### `wsl_path` (lib.rs:269, `async: false`)

**Purpose:** Translates a path between Windows and WSL representations via `wsl -e wslpath`; on non-Windows returns input unchanged.

**Args:** `path: String`, `mode: Option<WslPathMode>` (`Windows` | `Linux`, default `Linux`).

**Returns:** `Ok(String)` translated path; `Err(String)` if `wsl` spawn fails, exits non-zero, or returns empty with no stderr.

**Side effects:** spawns `wsl` subprocess on Windows; pure on non-Windows.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES on non-Windows (identity).
- Failure path: YES (`test_wsl_path_missing_required_arg_errors`).
- Location: `tests/ipc/test_lib_commands.py:145-158`.

**Recommended tests to add:**
- On non-Windows with `mode="windows"`: assert input is echoed unchanged (documents the short-circuit).
- Unicode + whitespace paths: `"C:\\Users\\Ällesandro\\Documents"` — assert no panic.
- Tilde expansion: `path="~/foo"` on non-Windows — assert the literal `"~/foo"` is returned (the `~` path is WSL-specific logic).

---

### `parse_markdown_command` (markdown.rs:59, `async: true`)

**Purpose:** Parses a Markdown string to HTML using `comrak` with strikethrough/table/tasklist/autolink extensions and external-link rewriting (`class="external-link" target="_blank" rel="noopener noreferrer"`).

**Args:** `markdown: String`.

**Returns:** `Ok(String)` HTML. Never errors in practice.

**Side effects:** none.

**Idempotency:** idempotent (pure).

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_parse_markdown_command_renders_basic_fixture`).
- Failure path: YES (empty input → empty HTML).
- Location: `tests/ipc/test_tectonic_markdown_cli.py:25-44`.

**Recommended tests to add:**
- Table rendering: pass a pipe-table fixture, assert `<table>` + `<th>` + `<td>` in output.
- Task list: `- [x] done` → assert `<input type="checkbox" checked` in output.
- Math/image/code-fence: three parametrised fixtures verifying each extension.
- XSS vector: `<script>alert(1)</script>` — with `r#unsafe = true` the tag is preserved; document this explicitly as expected and dangerous.
- Autolink: bare URL in prose → `<a class="external-link" target="_blank" rel="noopener noreferrer">`.

---

### `create_project_directory` (project_fs.rs:8, `async: false`)

**Purpose:** Creates a new directory named `<name>` under `<parent>`, refusing overwrites or unsafe names.

**Args:** `parent: String`, `name: String`.

**Returns:** `Ok(String)` absolute path to the created dir; `Err(String)` for empty/slash-containing name, `.`/`..`, non-directory parent, existing target, or `create_dir` failure.

**Side effects:** creates one directory; no network.

**Idempotency:** mutating but guarded — refuses to proceed if the target already exists.

**Safety classification:** SAFE_WITH_FIXTURE — point `parent` at `tmp_path` to contain side effects.

**Test coverage today:**
- Happy path: YES (`test_create_project_directory_happy_path`).
- Failure path: YES (`test_create_project_directory_rejects_invalid`).
- Location: `tests/ipc/test_project_fs.py:13-46`.

**Recommended tests to add:**
- Parametrised rejection matrix: empty name, whitespace name, `"."`, `".."`, `"a/b"`, `"a\\b"`, name starting with null byte — each asserts the specific error prefix.
- Existing target: create a dir, call again with same name, assert the "already exists" error contains the name.
- Parent does not exist: assert error contains `"doesn't exist"`.
- Read-only parent: create a dir, chmod 0555, invoke, assert permission error surfaces.
- Symlink parent: parent is a symlink to a tmp dir → assert the new dir is created at the symlink target.

---

### `check_project_accessible` (project_fs.rs:53, `async: false`)

**Purpose:** Reports whether the Tauri main process can `read_dir` the given path. Distinguishes `"ok"`, `"locked"` (EACCES/EPERM), `"missing"`, and other errors.

**Args:** `path: String`.

**Returns:** `Ok("ok" | "locked" | "missing")` string sentinel, or `Err(String)` for unexpected errors.

**Side effects:** one `read_dir` syscall; no mutation.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_check_project_accessible_happy_path` — tmp_path → `"ok"`).
- Failure path: YES (missing-arg rejection).
- Location: `tests/ipc/test_project_fs.py:48-68`.

**Recommended tests to add:**
- `"missing"` branch: call with `/definitely/not/here` → assert `== "missing"`.
- `"locked"` branch on Unix: create dir, chmod 0000, invoke, assert `== "locked"`; cleanup with chmod 0755.
- File (not dir) input: pass a regular file path — document what this returns (likely `Err` since `read_dir` fails with NotADirectory).
- Windows-specific raw-errno code path (EPERM=1): gated runner-only test.

---

### `get_default_server_url` (server.rs:18, `async: false`)

**Purpose:** Reads `default_server_url` from the Tauri-store settings file.

**Args:** `app: AppHandle`.

**Returns:** `Ok(Option<String>)`; `Err(String)` if the store can't be opened.

**Side effects:** reads `~/.config/.../settings.json` (platform-specific Tauri path).

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_get_default_server_url_happy_path`).
- Failure path: NO (store-open error is hard to trigger without corrupting the store).
- Location: `tests/ipc/test_server.py:28-36`.

**Recommended tests to add:**
- Round-trip: `set(url)` → `get()` returns `url` → `set(None)` → `get()` returns `None`.
- Corrupt-store injection (likely out of scope in unattended suites).

---

### `set_default_server_url` (server.rs:32, `async: true`)

**Purpose:** Writes or deletes `default_server_url` in the settings store.

**Args:** `app: AppHandle`, `url: Option<String>`.

**Returns:** `Ok(())`; `Err(String)` on store open/save failure.

**Side effects:** writes the Tauri settings.json; atomically committed via `store.save()`.

**Idempotency:** mutating but deterministic.

**Safety classification:** SAFE_WITH_FIXTURE — mutates shared user settings, but the tests restore the previous value.

**Test coverage today:**
- Happy path: YES (`test_set_default_server_url_happy_path` — uses try/finally to clean up).
- Failure path: YES (wrong type rejected — `test_set_default_server_url_rejects_wrong_type`).
- Location: `tests/ipc/test_server.py:45-65`.

**Recommended tests to add:**
- Round-trip cycle: set, get, assert; set null, get, assert `None`.
- Unicode URL: `"https://测试.example.com/path"` — assert round-trip stable.
- Very-long URL (64 KiB): assert store accepts.
- Persistence across app restart: set value, quit, relaunch, assert value preserved (requires app-restart fixture — G6.5 territory).

---

### `get_wsl_config` (server.rs:55, `async: false`)

**Purpose:** Reports the current WSL enable state. **Currently hardcoded**: returns `{ enabled: false }` regardless of store contents (the store-read branch is commented out).

**Args:** `_app: AppHandle` (unused).

**Returns:** `Ok(WslConfig { enabled: bool })`.

**Side effects:** none.

**Idempotency:** idempotent (constant).

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_get_wsl_config_happy_path`).
- Failure path: N/A.
- Location: `tests/ipc/test_server.py:72-84`.

**Recommended tests to add:**
- Pin the constant: assert `result == {"enabled": False}` unconditionally, with a comment linking to the commented-out code so if it's ever uncommented the test breaks as a reminder.
- After `set_wsl_config({enabled: true})`, assert `get_wsl_config` still returns `false` (regression guard for current behavior).

---

### `set_wsl_config` (server.rs:71, `async: false`)

**Purpose:** Writes `wsl.enabled` boolean to the settings store. (Note: `get_wsl_config` ignores this — see above.)

**Args:** `app: AppHandle`, `config: WslConfig { enabled: bool }`.

**Returns:** `Ok(())`; `Err(String)` on store error.

**Side effects:** writes settings store.

**Idempotency:** mutating but deterministic.

**Safety classification:** SAFE_WITH_FIXTURE.

**Test coverage today:**
- Happy path: YES (`test_set_wsl_config_happy_path`).
- Failure path: YES (`test_set_wsl_config_rejects_missing_field`).
- Location: `tests/ipc/test_server.py:91-110`.

**Recommended tests to add:**
- Malformed config: `{"config": "true"}` (string not object) → assert deserialize error.
- Nested unknown keys: `{"config": {"enabled": true, "extra": 1}}` — document whether `specta` tolerates this.

---

### `install_tectonic` (tectonic.rs:69, `async: true`)

**Purpose:** Downloads the latest Tectonic release asset from GitHub and extracts the binary into `~/.config/gpd/.capabilities/tectonic/bin/`.

**Args:** `app: AppHandle`.

**Returns:** `Ok(String)` absolute path to the installed binary; `Err(String)` when no asset matches, network failure, extraction failure, post-install smoke test fails, Gatekeeper-related execute failure.

**Side effects:** creates `~/.config/gpd/.capabilities/tectonic/bin/tectonic`; emits `TectonicDownloadProgress` events; 20-30 MB download. Re-invoking with the binary present is a cheap no-op (runs `--version` to confirm and returns the cached path).

**Idempotency:** idempotent after first successful install (cache hit short-circuits).

**Safety classification:** UNSAFE — mutates `~/.config/gpd/.capabilities`, multi-minute network.

**Test coverage today:**
- Happy path: SKIPPED (`test_install_tectonic_returns_path_or_errors_cleanly`).
- Failure path: NO.
- Location: `tests/ipc/test_tectonic_markdown_cli.py:47-59`.

**Recommended tests to add:**
- Cache-hit path (pre-staged binary): place a valid tectonic binary at the expected path, invoke, assert returns the path within 2s (no download).
- Gated full-install behind `PYTEST_OPTIN_MUTATE_SYSTEM=1`: invoke, assert binary is created, `--version` succeeds, download emitted progress events.
- Platform-unavailable: set `target_arch` to an unsupported triple (requires cfg tricks; likely out of reach from Python).
- Network failure: temporarily override DNS or use `PYTEST_OPTIN_OFFLINE=1` to assert the network-error branch returns a clear message.

---

### `detect_tex_root` (tex_compiler.rs:178, `async: false`)

**Purpose:** Detects the canonical TeX root for a starting file: magic `% !TEX root = ...` comment, `.latexmkrc` default_files, `\documentclass` heuristic, or fallback.

**Args:** `start_file: String`.

**Returns:** `String` (absolute path; never errors — returns the input when nothing else matches).

**Side effects:** reads up to the start file, `.latexmkrc`s walking up, and every `.tex` file in the start file's dir.

**Idempotency:** idempotent.

**Safety classification:** SAFE_WITH_FIXTURE (reads filesystem — tests pass tmp_path).

**Test coverage today:**
- Happy path: YES (`test_detect_tex_root_falls_back_to_start_file`, `test_detect_tex_root_honors_magic_comment`).
- Failure path: partial — only two branches tested.
- Location: `tests/ipc/test_tex_compiler.py:67-98`.

**Recommended tests to add:**
- `.latexmkrc` branch: create nested dir, place `.latexmkrc` with `@default_files = ('main.tex');` in parent, call with child file, assert returns parent's `main.tex`.
- `\documentclass` heuristic: tmp_path with two `.tex` files, one containing `\documentclass`; assert that one is returned.
- Relative-path magic comment: `% !TEX root = ../main.tex` with `main.tex` in parent — assert absolute path returned.
- Non-absolute input: pass `"foo.tex"` — assert echoed unchanged (defensive branch).
- Missing `!TEX root` value: assert falls through to other checks.
- Deep traversal: `.latexmkrc` 4 levels up — assert resolver walks up correctly.

---

### `detect_tex_compiler` (tex_compiler.rs:227, `async: false`)

**Purpose:** Reports which LaTeX toolchain is available: pdflatex > tectonic (PATH) > bundled tectonic, with latexmk/bibtex/synctex presence flags.

**Args:** none.

**Returns:** `TexCompilerInfo { kind: String, path: Option<String>, has_latexmk: bool, has_bibtex: bool, has_synctex: bool }`.

**Side effects:** scans PATH directories.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_detect_tex_compiler_returns_well_formed_info`).
- Failure path: N/A.
- Location: `tests/ipc/test_tex_compiler.py:105-124`.

**Recommended tests to add:**
- Invariant: `kind in {"pdflatex", "tectonic", "none"}` and `(kind == "none") == (path is None)`.
- If `has_latexmk` is true, assert `shutil.which("latexmk")` also reports the same on the host (cross-check).
- With `PATH=""` (empty): the command should return `kind = "none"`.
- Bundled-only branch: stage a fake tectonic under `~/.config/gpd/.capabilities/tectonic/bin/`, clear PATH, assert `kind == "tectonic"` and `path` points at the bundle.

---

### `compile_tex` (tex_compiler.rs:249, `async: true`)

**Purpose:** Runs pdflatex (via latexmk when available) or tectonic on a TeX root file, producing a PDF under `~/.config/gpd/.tex-builds/<project>/<hash>/`. Streams `TexCompileProgress` events. Cancels any in-flight compile for the same `TexCompileState`.

**Args:** `app: AppHandle`, `state: State<TexCompileState>`, `project_id: String`, `tex_file: String`, `root_file: Option<String>`.

**Returns:** `Ok(TexCompileResult { status, pdf_path, synctex_path, log_path, compiler_kind, compiler_path, duration_ms, errors, warnings, root_file, out_dir })` — `status` is one of `success | success_with_warnings | error | no_compiler | cancelled`. `Err(String)` only for file-not-found or cache-dir-creation failures.

**Side effects:** writes to `~/.config/gpd/.tex-builds/`; spawns pdflatex/latexmk/bibtex/tectonic subprocess(es); reads project source files.

**Idempotency:** re-running with the same args is effectively a cache hit (same hash directory) but the compiler still re-runs and overwrites artifacts. Concurrent calls cancel prior runs via the `TexCompileState` generation counter.

**Safety classification:** SAFE_WITH_FIXTURE (mutations live in the GPD cache; test-time cache isolation via `project_id = "test-<uuid>"`).

**Test coverage today:**
- Happy path: YES partial (`test_compile_tex_happy_path` — covers both `success` and `no_compiler` branches).
- Failure path: YES (`test_compile_tex_rejects_missing_source`).
- Location: `tests/ipc/test_tex_compiler.py:132-189`.

**Recommended tests to add:**
- End-to-end PDF verification: compile `\documentclass{article}\begin{document}Hi\end{document}`, read bytes via `read_tex_artifact_base64`, assert header starts with `%PDF-`.
- Warnings branch: compile `\documentclass{article}\begin{document}\ref{missing}\end{document}` — assert `status == "success_with_warnings"` and `warnings` contains the `Reference ... undefined` message.
- Error branch: compile `\documentclass{article}\begin{document}\undefined_macro` — assert `status == "error"`, `errors` non-empty, `pdf_path is None`.
- Cancellation: start two compiles back-to-back on a slow `.tex` — assert the first returns `status == "cancelled"`.
- Bibtex pipeline: tex with `\cite{foo}` and a `.bib` file — assert two pdflatex passes + bibtex were run (observable via `duration_ms` heuristic or log inspection).
- Latexmk vs plain: when latexmk is available, `compiler_kind` should still be `"pdflatex"` (kind reports the compiler, not the driver).
- Root-file override: `root_file = Some("main.tex")` with a different `tex_file` — assert the override wins.

---

### `synctex_forward` (tex_compiler.rs:418, `async: true`)

**Purpose:** SyncTeX forward lookup: given PDF `(page, x, y)`, return `(source_file, line)`.

**Args:** `synctex_path: String`, `page: u32`, `x: f64`, `y: f64`.

**Returns:** `Ok(SyncTexResult { file, line, page: None, x: None, y: None })`; `Err("synctex CLI not found on PATH")` if `synctex` binary is absent.

**Side effects:** spawns `synctex view` subprocess.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: partial — contract test asserts the result shape or error.
- Failure path: YES.
- Location: `tests/ipc/test_tex_compiler.py:198-229`.

**Recommended tests to add:**
- Full compile → extract real synctex.gz → forward lookup at PDF (page=1, x=72, y=72) → assert `file` points to the root `.tex` and `line` is a positive int.
- Bogus synctex_path: file doesn't exist — assert error string is meaningful.
- Extreme coordinates (negative x, huge y) — document whether synctex errors or returns nulls.

---

### `synctex_reverse` (tex_compiler.rs:465, `async: true`)

**Purpose:** SyncTeX reverse lookup: given `(source_file, line)`, return `(page, x, y)`.

**Args:** `synctex_path: String`, `source_file: String`, `line: u32`.

**Returns:** `Ok(SyncTexResult { file: None, line: None, page, x, y })`; `Err(...)` if `synctex` missing.

**Side effects:** spawns `synctex edit` subprocess.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: partial.
- Failure path: YES.
- Location: `tests/ipc/test_tex_compiler.py:233-265`.

**Recommended tests to add:**
- Full compile → reverse lookup line 1 of root → assert `page >= 1` and `x, y` are positive floats.
- Source file that isn't referenced by the synctex map — assert graceful empty result.
- Symmetric round trip: forward(reverse(file, line)) should return (file, ~line) within tolerance.

---

### `read_tex_artifact_base64` (tex_compiler.rs:517, `async: false`)

**Purpose:** Returns base64-encoded bytes of a file at `path`, **provided the canonicalized path is inside `~/.config/gpd/.tex-builds/`**.

**Args:** `path: String`.

**Returns:** `Ok(String)` base64; `Err(String)` if path canonicalization fails, is outside cache, or read fails.

**Side effects:** reads file; no mutation.

**Idempotency:** idempotent.

**Safety classification:** SAFE (explicit path-traversal guard via `canonicalize` + `starts_with`).

**Test coverage today:**
- Happy path: YES (`test_read_tex_artifact_base64_happy_path` — chained with a real compile).
- Failure path: YES (`test_read_tex_artifact_base64_rejects_path_outside_cache`).
- Location: `tests/ipc/test_tex_compiler.py:278-328`.

**Recommended tests to add:**
- Symlink attack: inside `.tex-builds/foo/bar/`, create a symlink pointing to `/etc/passwd`, invoke with the symlink's path → assert refusal (canonicalize resolves the symlink outside the cache).
- Relative path with `..`: `"/tmp/../etc/passwd"` — assert refusal.
- Binary round-trip: write `0x00..0xFF` bytes to a file inside cache, decode the base64 return, assert byte-exact match.
- Empty-file: read a 0-byte artifact, assert returns `""`.

---

### `parse_tex_log` (tex_compiler.rs:577, `async: false`)

**Purpose:** Parses a pdflatex-style `.log` file and returns structured errors + warnings.

**Args:** `log_path: String`.

**Returns:** `Ok(TexLogParseResult { errors, warnings, raw_log })`; `Err(String)` if the file can't be read.

**Side effects:** reads the log file.

**Idempotency:** idempotent.

**Safety classification:** SAFE.

**Test coverage today:**
- Happy path: YES (`test_parse_tex_log_happy_path` — synthetic log with error, warning, overfull hbox).
- Failure path: YES (missing file).
- Location: `tests/ipc/test_tex_compiler.py:336-371`.

**Recommended tests to add:**
- Warning dedup: inject two identical `LaTeX Warning: ...` lines, assert only one entry in `warnings`.
- Overfull/Underfull hbox + vbox: four-way parametrised test asserting `line` extraction from `at lines N--M`.
- Cap at 50 each: inject 100 errors, assert `len(errors) == 50`.
- Empty log: `""` → `errors == [] and warnings == []`.
- Non-UTF8 log file: write log with latin-1 bytes, assert graceful read (Rust's `read_to_string` errors on invalid UTF-8 — document whether to add lossy-utf8 handling).
- File-stack attribution: error nested inside `(./chapter1.tex`, assert `errors[0].file == "./chapter1.tex"`.

---

## Classification summary
- **SAFE: 14** — `linux_install_hint`, `check_app_exists`, `resolve_app_path`, `get_display_backend`, `wsl_path`, `parse_markdown_command`, `check_project_accessible`, `get_default_server_url`, `get_wsl_config`, `detect_tex_compiler`, `synctex_forward`, `synctex_reverse`, `read_tex_artifact_base64`, `parse_tex_log`
- **SAFE_WITH_FIXTURE: 7** — `await_initialization`, `set_display_backend`, `create_project_directory`, `set_default_server_url`, `set_wsl_config`, `detect_tex_root`, `compile_tex`
- **UNSAFE: 4** — `install_cli`, `repair_gpd_venv`, `kill_sidecar`, `install_tectonic`
- **INTERACTIVE: 3** — `install_git_macos`, `install_git_windows`, `open_path`

Total: 28 commands. Overlapping classifications (e.g., `install_git_macos` is INTERACTIVE on macOS and SAFE elsewhere) are resolved by assigning the worst-case bucket.

## Priority ranking for Phase G4 (deep-behavior tests)

Top 10 commands to exhaustively test, ranked by **impact × safety**. Impact scored by: (a) user-visible surface, (b) security sensitivity, (c) breadth of logic branches. Safety scored by: can we test without destructive side effects.

1. **`compile_tex`** — highest impact (entire TeX publication workflow). SAFE_WITH_FIXTURE via `project_id` namespacing. Branches: pdflatex, tectonic, bundled-tectonic, latexmk, bibtex, no-compiler, cancellation, error, warnings. Drives nearly all of G4.2.
2. **`create_project_directory`** — gates the new-project journey. SAFE_WITH_FIXTURE. Rich rejection matrix (empty, `.`, `..`, slashes, backslashes, existing, read-only, symlink parent). Low cost to cover comprehensively. Drives G4.1.
3. **`read_tex_artifact_base64`** — security-critical path-traversal guard. SAFE. Symlink/`..`/canonicalization edge cases are exactly the kind of thing that silently regresses.
4. **`parse_tex_log`** — pure parser with rich grammar; high payoff per test line. SAFE. File-stack attribution + dedup + 50-cap invariants are all observable.
5. **`detect_tex_root`** — four-branch resolver (magic comment, `.latexmkrc`, `\documentclass` scan, fallback). SAFE_WITH_FIXTURE. Currently only two branches covered.
6. **`parse_markdown_command`** — SAFE pure function; covers every `comrak` extension we enable (tables, tasklists, autolink, strikethrough, external-link rewriting, `r#unsafe=true` semantics).
7. **`set_default_server_url`** + **`get_default_server_url`** — paired round-trip, SAFE_WITH_FIXTURE, drives persistence-across-restart tests (G6.5). Null-vs-string branch + wrong-type deserialization.
8. **`check_project_accessible`** — SAFE, three-sentinel return (`ok`/`locked`/`missing`) plus the Windows EPERM raw-errno branch; matters for the macOS TCC flow.
9. **`synctex_forward` + `synctex_reverse`** — SAFE (pure-except-synctex-subprocess); pair naturally into a symmetric round-trip test after a real compile.
10. **`detect_tex_compiler`** — SAFE, short but load-bearing: its output drives `compile_tex` branch selection. PATH-manipulation tests are cheap and high-signal.

Commands explicitly **excluded** from G4 deep tests (requires OPT-IN / OPT-OUT gating):
- `install_cli`, `repair_gpd_venv`, `kill_sidecar`, `install_tectonic` — all UNSAFE, already skip-marked.
- `install_git_macos/windows` — platform-conditional INTERACTIVE.
- `open_path` — INTERACTIVE, pollutes the host desktop.
- `await_initialization` — requires a Tauri `Channel` arg that MCP can't synthesise without product-side help.

These UNSAFE/INTERACTIVE commands should receive one gated end-to-end test each behind `PYTEST_OPTIN_MUTATE_SYSTEM=1` rather than Phase G4 unit-style coverage.
