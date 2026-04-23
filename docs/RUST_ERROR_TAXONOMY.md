# Rust → TS Error Taxonomy for the GPD Tauri Desktop Shell

Design document. No implementation in this commit.

## 1. Problem statement

Every Tauri command in the GPD desktop shell that can fail today returns
`Result<T, String>`, where the error string is an English literal baked in at
the Rust call site. specta emits those commands as `Promise<T>`-throwing JS
functions whose rejection value is a single opaque string. The TypeScript
consumer has no programmatic way to tell one failure mode from another, which
means:

1. Error messages cannot be translated. The app ships with an `i18n` layer
   (`packages/desktop/src/i18n/en.ts`, 61 entries today) and every
   user-visible string in the TypeScript codebase goes through
   `language.t(key, params)`, but errors coming from Rust bypass i18n entirely
   and land in toasts / dialogs as English.
2. Error messages cannot be re-worded for clarity without breaking any
   consumer that tried to classify them. `cli.ts:6-30` already does exactly
   that — and it is the concrete failure mode that motivated this doc.
3. Error messages cannot carry structured context (a path, a command, an
   errno) in a way the TS side can re-assemble into a translated sentence;
   the Rust side has to commit to a particular English word order forever.

The `cli.ts` case is worth staring at. When `install_cli` fails, Rust returns
one of seven English sentinels and the TS side hunts for them with
`text.includes(...)`:

```ts
// packages/desktop/src/cli.ts:6-30
function installError(error: unknown) {
  const text = String(error)
  if (text.includes("CLI installation is only supported on macOS & Linux"))
    return t("desktop.cli.error.unsupportedPlatform")
  if (text.includes("Sidecar binary not found"))
    return t("desktop.cli.error.sidecarMissing")
  if (text.includes("Failed to write install script"))
    return t("desktop.cli.error.scriptWriteFailed")
  // … 4 more substring checks …
  return text || t("desktop.cli.error.unknown")
}
```

The corresponding Rust side is in `packages/desktop/src-tauri/src/cli.rs`:

- `cli.rs:134` — `Err("CLI installation is only supported on macOS & Linux".to_string())`
- `cli.rs:138` — `Err("Sidecar binary not found".to_string())`
- `cli.rs:143` — `format!("Failed to write install script: {}", e)`
- `cli.rs:149` — `format!("Failed to set script permissions: {}", e)`
- `cli.rs:156` — `format!("Failed to run install script: {}", e)`
- `cli.rs:162` — `format!("Install script failed: {}", stderr)`
- `cli.rs:166` — `"Could not determine install path"`

Any Rust refactor that re-words those strings silently breaks the TS
classifier, because `text.includes("Failed to write install script")` turns
false without any compile-time signal. That is the structural hazard this
doc replaces.

Four more concrete examples, taken from the highest-impact files, to
illustrate the broader pattern:

- **First-run failures** (`gpd_setup.rs:156`):
  `format!("Couldn't remove the GPD Python environment. Make sure no other app is using it. ({e})")`
  — three facts crammed into one sentence that cannot be rephrased per locale.
- **LaTeX compile** (`tex_compiler.rs:267`):
  `format!("LaTeX source file not found: {root}. Make sure the file exists and hasn't been moved.")`
  — path interpolation + advice sentence mashed together.
- **Tectonic install** (`tectonic.rs:85-88`):
  `"Tectonic is not available as a prebuilt binary for this platform. See {MANUAL_INSTALL_URL} for manual install instructions."`
  — URL + advice locked into English word order.
- **WSL path translation** (`lib.rs:426`):
  `format!("Couldn't translate the file path for WSL. Try a simpler path. ({e})")`
  — two-sentence user message impossible for i18n to touch.

Across the 9 files in scope (`lib.rs`, `cli.rs`, `dependencies.rs`,
`gpd_setup.rs`, `tectonic.rs`, `tex_compiler.rs`, `project_fs.rs`,
`server.rs`, `os/windows.rs`) this document counts **85 distinct
error-string call sites** reachable from `Result<T, String>` Tauri commands
or helpers they call into. The full inventory is in §4.

## 2. Option comparison

### Option A — Stable sentinel strings + substring match (status quo)

This is what `cli.rs`/`cli.ts` does today. The Rust side agrees to keep an
English substring stable forever, and the TS side matches it with
`text.includes(…)`. Translation happens in the TS layer.

**Pros.** Zero Rust churn: signatures stay `Result<T, String>`, no new
types, minimal rebase risk against upstream OpenCode. Works today for the
one file (`cli.rs`) that has adopted it.

**Cons.** Maintenance trap. There is no compile-time link between the Rust
string and the TS matcher, so any re-wording of the English text silently
breaks classification and falls through to the `|| t(…unknown)` branch.
Worse, the classifier must be written for each command separately; no
shared machinery. Parameters (path, errno) can't cross the bridge — the TS
layer has to re-parse them out of the interpolated English with a regex.
Scaling this pattern to 85 strings would require ~85 substring guards
and 85 English-text invariants. That is strictly worse than what we have
now.

### Option B — Typed enum via `#[derive(serde::Serialize, specta::Type)]`, returned as `Result<T, DesktopError>`

Define a single `DesktopError` enum. Every `Result<T, String>` command in
the scope files becomes `Result<T, DesktopError>`. Variants are
adjacently-tagged (`#[serde(tag = "code", content = "data")]`) so the TS
type is a discriminated union on a `code` field. Each variant carries its
parameters (path, errno detail, etc.) as a struct of strongly-typed
fields.

**Pros.** Exhaustive on both sides: Rust gets pattern-match exhaustiveness
for any helper that consumes `DesktopError`; TS gets exhaustive `switch
(err.code)` via the generated discriminated union. Interpolation
parameters cross the wire as structured fields (no regex re-parsing).
Re-wording a message is a pure TS change that cannot break anything.
Adding a new variant is a single commit that touches one Rust enum, one
TS switch, and `en.ts`. The existing codebase already proves specta
serializes adjacently-tagged enums cleanly — see `InitStep` at
`lib.rs:50-57` (rendered as `{ phase: "server_waiting" } | …` in
`bindings.ts:60`) and `SqliteMigrationProgress` at `cli.rs:620-627`
(rendered as `{ type: "InProgress"; value: number } | { type: "Done" }`
at `bindings.ts:90`). There is no new specta feature required.

**Cons.** One-time migration cost for ~85 call sites. New enum must be
kept in sync with the TS translator. The `.map_err(|e| format!(…))`
pattern gets replaced with `.map_err(|e| DesktopError::Foo { detail:
e.to_string(), … })` which is slightly more verbose but mechanical.

### Option C — Error code constants + `HashMap<String, String>` params

Define Rust-side constants (`const CLI_UNSUPPORTED: &str = "cli.unsupportedPlatform"`)
and return them in a struct like `{ code: String, params: HashMap<String, String> }`.
TS switches on `code` and interpolates `params` into the translated string.

**Pros.** No enum to maintain — constants are cheap to add. `params` is
free-form so unusual one-off fields don't require an enum-variant change.

**Cons.** No type safety for the params map: a variant expecting
`params.path` doesn't fail the build when `path` is forgotten on the Rust
side or misspelled on the TS side. The TS union becomes `{ code: string;
params: Record<string, string> }` — the consumer can't tell what keys to
expect, so it has no compile-time guardrail. Essentially Option B with all
the type-safety removed.

### Option D — Translated error via `.to_user_string()` RPC

Rust returns an opaque code and the TS side makes a second Tauri call to
fetch the translated message for the current locale. Rejected: two wire
protocols and a Rust-side i18n store, when the app already has a working
TS i18n layer.

## 3. Recommendation

**Adopt Option B — typed enum returned as `Result<T, DesktopError>`.**

The fork already relies on adjacently-tagged enums flowing through
tauri-specta (`InitStep`, `SqliteMigrationProgress`, `TexCompileStatus`,
`LinuxDisplayBackend`) so there is no open question about specta support
or runtime behaviour. Option B is the only design where re-wording an
error message is guaranteed to be a non-breaking change, and the only one
that lets the TS side receive structured interpolation parameters (paths,
errno numbers) as fields on an object rather than regex-extracting them
out of a human sentence. The incremental cost is bounded (~85 call sites,
mechanical refactor) and the migration is phaseable file-by-file because
each command's signature change is local to that command.

## 4. Enum design

All 85 strings have been extracted from the nine files listed in the
brief. Near-duplicate siblings (e.g. the four "Failed to read tar entry",
"Failed to read zip entry i", "Failed to read tar archive" strings in
`tectonic.rs`) have been collapsed into one variant with a `phase: String`
discriminator, bringing the final enum to **48 variants**.

```rust
// packages/desktop/src-tauri/src/error.rs   (proposed new module)

/// All user-facing failure modes that a Tauri command in the GPD desktop
/// shell can return to the web frontend. Variants are grouped by
/// subsystem via naming convention; the `code` tag (set by
/// `#[serde(tag = "code")]`) uniquely identifies each variant on the
/// wire.
///
/// Adding a new variant requires:
///   1. An entry in this enum.
///   2. An entry in `translateDesktopError` (src/errors/desktop.ts).
///   3. An entry in the `en.ts` i18n catalog.
///
/// The translator is exhaustive — a missing switch case is a TS compile
/// error — so (2) and (3) cannot be forgotten silently.
#[derive(serde::Serialize, specta::Type, Debug, Clone)]
#[serde(tag = "code", content = "data", rename_all = "camelCase")]
pub enum DesktopError {
    // -------------------------------------------------------------------
    // Auth / JSON-backed key store   (lib.rs:319-376)
    // -------------------------------------------------------------------
    AuthJsonRead            { detail: String, path: String },
    AuthJsonWrite           { detail: String, path: String },
    AuthJsonSerialize       { detail: String },
    AuthJsonDirCreate       { detail: String, path: String },

    // -------------------------------------------------------------------
    // Bundled resources / platform env   (lib.rs:386-404)
    // -------------------------------------------------------------------
    EnvVarMissing           { name: String },
    ResourceResolve         { name: String, detail: String },
    ResourceRead            { name: String, path: String, detail: String },

    // -------------------------------------------------------------------
    // Open path / PowerShell   (lib.rs:193-198, os/windows.rs:452-463)
    // -------------------------------------------------------------------
    OpenPath                { detail: String, path: String },
    PowerShellStart         { detail: String },
    PowerShellCwdResolve    { detail: String },

    // -------------------------------------------------------------------
    // WSL bridge   (lib.rs:409-443)
    // -------------------------------------------------------------------
    WslPathTranslate        { detail: String },
    WslPathTranslateEmpty,

    // -------------------------------------------------------------------
    // CLI install   (cli.rs:131-218)
    // -------------------------------------------------------------------
    CliUnsupportedPlatform,
    CliSidecarMissing,
    CliInstallScriptWrite   { detail: String },
    CliInstallScriptChmod   { detail: String },
    CliInstallScriptSpawn   { detail: String },
    CliInstallScriptFailed  { stderr: String },
    CliInstallPathUnknown,
    CliVersionSpawn         { detail: String },
    CliVersionReadFailed,
    CliVersionParse         { raw: String, detail: String },

    // -------------------------------------------------------------------
    // Sidecar / server   (server.rs)
    // -------------------------------------------------------------------
    SettingsStoreOpen       { detail: String },
    SettingsStoreSave       { detail: String },
    SidecarTerminatedEarly  { code: Option<i32>, signal: Option<i32> },

    // -------------------------------------------------------------------
    // Dependency install (git, etc.)   (dependencies.rs)
    // -------------------------------------------------------------------
    DependencyWrongOs       { tool: String, os: String },
    DependencySpawn         { tool: String, detail: String },
    DependencyInstallFailed { tool: String, stdout: String, stderr: String },

    // -------------------------------------------------------------------
    // GPD first-run setup   (gpd_setup.rs)
    // -------------------------------------------------------------------
    GpdSetupHelperMissing   { helper: String, path: String },
    GpdSetupConfigDirCreate { detail: String, path: String },
    GpdSetupVenvRemove      { detail: String, path: String },
    GpdSetupMarkerRemove    { detail: String },
    GpdSetupMarkerWrite     { detail: String },
    GpdSetupPythonInstall   { phase: String, detail: String },  // collapses: install timeout, install spawn, install exit, find spawn, find empty
    GpdSetupVenvCreate      { phase: String, detail: String },  // collapses: venv timeout, venv spawn, venv exit
    GpdSetupPipInstall      { phase: String, detail: String },  // collapses: pip timeout, pip spawn, pip exit
    GpdSetupGpdInstall      { phase: String, detail: String },  // collapses: gpd install timeout, spawn, exit
    GpdSetupConfigRead      { detail: String, path: String },
    GpdSetupConfigParse     { detail: String, path: String },
    GpdSetupConfigSerialize { detail: String },
    GpdSetupConfigWrite     { detail: String, path: String },

    // -------------------------------------------------------------------
    // Tectonic on-demand install   (tectonic.rs)
    // -------------------------------------------------------------------
    TectonicBinDirCreate    { detail: String, path: String },
    TectonicUnsupportedPlatform { install_url: String },
    TectonicHttpClient      { detail: String },
    TectonicReleaseFetch    { detail: String },
    TectonicReleaseStatus   { status: u16 },
    TectonicReleaseParse    { detail: String },
    TectonicAssetMissing    { version: String, install_url: String },
    TectonicDownloadStart   { detail: String },
    TectonicDownloadStatus  { status: u16 },
    TectonicDownloadInterrupted { detail: String },
    TectonicArchiveOpen     { kind: String, detail: String },     // kind = "zip" | "tar.gz"
    TectonicArchiveEntry    { kind: String, index: Option<u32>, detail: String },
    TectonicBinaryWrite     { detail: String, path: String },
    TectonicBinaryMissing   { archive_name: String, bin_name: String },
    TectonicArchiveUnknown  { archive_name: String },
    TectonicChmod           { detail: String, path: String },
    TectonicPostInstallNotRunnable { path: String, gatekeeper_hint: bool },

    // -------------------------------------------------------------------
    // TeX compile surface   (tex_compiler.rs)
    // -------------------------------------------------------------------
    TexRootMissing          { path: String },
    TexOutDirCreate         { detail: String, path: String },
    TexSynctexCliMissing,
    TexSynctexRun           { direction: String, detail: String }, // direction = "forward" | "reverse"
    TexArtifactPathResolve  { detail: String, path: String },
    TexArtifactOutsideCache { path: String },
    TexArtifactRead         { detail: String, path: String },
    TexLogRead              { detail: String, path: String },

    // -------------------------------------------------------------------
    // Project filesystem   (project_fs.rs)
    // -------------------------------------------------------------------
    ProjectNameEmpty,
    ProjectNameHasSeparator,
    ProjectNameReserved,
    ProjectParentMissing    { path: String },
    ProjectAlreadyExists    { name: String, parent: String },
    ProjectDirCreate        { detail: String, path: String },
    ProjectPathEmpty,
    ProjectCanonicalize     { detail: String, path: String },
    ProjectProbe            { detail: String, path: String },

    // -------------------------------------------------------------------
    // Internal — sidecar plumbing errors the frontend just logs
    // -------------------------------------------------------------------
    Internal                { detail: String },
}
```

**Fields — why these.**

- `detail: String` — every variant that wraps an `std::io::Error` or
  `serde_json::Error` carries the underlying `e.to_string()` so the TS
  side can show it to an advanced user in the "Details" disclosure of an
  error toast without re-asking the Rust side. Translating the wrapper
  sentence around `detail` is the whole point; `detail` itself stays
  English (it's a kernel errno / reqwest / serde message — translating it
  is out of scope).
- `path: String` — paths are stringified on the Rust side via
  `PathBuf::display()` because they need to match what the user saw in
  the file picker.
- `phase: String` discriminators on `GpdSetup*Install` collapse timeout
  / spawn-failure / non-zero-exit into one variant per subsystem step.
  The TS switch can either render a generic message or branch further on
  `phase`; keeping it one variant keeps the enum readable.

**48 variants, not 85,** because: `gpd_setup.rs` timeout/spawn/exit
trios across 4 phases collapse via `phase` (37→4); the 11 `tectonic.rs`
archive-read strings across zip/tar collapse via `kind` (→2); `tex_compiler.rs`
synctex forward/reverse collapses via `direction` (→2); settings-store
open/save strings across `server.rs` and `lib.rs` collapse (→2).

## 5. TS translator mapping

On the TS side, a single exhaustive switch converts a `DesktopError` into
the translated string the user sees. The `never` default case guarantees
every new Rust variant triggers a TS compile error until it is handled.

```ts
// packages/desktop/src/errors/desktop.ts   (proposed new module)

import type { DesktopError } from "../bindings"
import { t } from "../i18n"

export function translateDesktopError(err: DesktopError): string {
  switch (err.code) {
    // --- Auth / JSON key store ---
    case "authJsonRead":
      return t("desktop.error.auth.read", { detail: err.data.detail, path: err.data.path })
    case "authJsonWrite":
      return t("desktop.error.auth.write", { detail: err.data.detail, path: err.data.path })

    // --- GPD first-run ---
    case "gpdSetupHelperMissing":
      return t("desktop.error.gpdSetup.helperMissing", { helper: err.data.helper, path: err.data.path })
    case "gpdSetupPythonInstall":
      return t(`desktop.error.gpdSetup.pythonInstall.${err.data.phase}`, { detail: err.data.detail })

    // --- LaTeX ---
    case "texRootMissing":
      return t("desktop.error.tex.rootMissing", { path: err.data.path })
    case "texSynctexCliMissing":
      return t("desktop.error.tex.synctexCliMissing")
    case "texSynctexRun":
      return t("desktop.error.tex.synctexRun", { direction: err.data.direction, detail: err.data.detail })

    // --- Tectonic ---
    case "tectonicUnsupportedPlatform":
      return t("desktop.error.tectonic.unsupportedPlatform", { url: err.data.installUrl })
    case "tectonicReleaseStatus":
      return t("desktop.error.tectonic.releaseStatus", { status: String(err.data.status) })

    // --- CLI install ---
    case "cliUnsupportedPlatform":
      return t("desktop.error.cli.unsupportedPlatform")

    // … one row per variant …

    default: {
      const _exhaustive: never = err
      return t("desktop.error.unknown", { detail: JSON.stringify(_exhaustive) })
    }
  }
}
```

The `installError` helper in `cli.ts` collapses to two lines once all of
its substring branches are replaced by `translateDesktopError(err)`.

## 6. i18n key naming convention

Pattern: `desktop.error.<subsystem>.<specific>`.

- `desktop` — root namespace, matches the existing 53 `desktop.*` keys in
  `en.ts`.
- `error` — distinguishes error strings from action / status strings.
- `<subsystem>` — one of `auth`, `cli`, `dependency`, `env`, `gpdSetup`,
  `openPath`, `powerShell`, `project`, `resource`, `server`, `settings`,
  `tectonic`, `tex`, `wsl`.
- `<specific>` — camelCase specific name that matches the variant name
  with the subsystem prefix dropped. Example: `GpdSetupVenvRemove` →
  `desktop.error.gpdSetup.venvRemove`.

**Full catalog of 48 keys that would need adding to `en.ts`:**

```
desktop.error.auth.read
desktop.error.auth.write
desktop.error.auth.serialize
desktop.error.auth.dirCreate
desktop.error.env.varMissing
desktop.error.resource.resolve
desktop.error.resource.read
desktop.error.openPath.generic
desktop.error.powerShell.start
desktop.error.powerShell.cwdResolve
desktop.error.wsl.pathTranslate
desktop.error.wsl.pathTranslateEmpty
desktop.error.cli.unsupportedPlatform
desktop.error.cli.sidecarMissing
desktop.error.cli.scriptWrite
desktop.error.cli.scriptChmod
desktop.error.cli.scriptSpawn
desktop.error.cli.scriptFailed
desktop.error.cli.installPathUnknown
desktop.error.cli.versionSpawn
desktop.error.cli.versionReadFailed
desktop.error.cli.versionParse
desktop.error.settings.storeOpen
desktop.error.settings.storeSave
desktop.error.server.terminatedEarly
desktop.error.dependency.wrongOs
desktop.error.dependency.spawn
desktop.error.dependency.installFailed
desktop.error.gpdSetup.helperMissing
desktop.error.gpdSetup.configDirCreate
desktop.error.gpdSetup.venvRemove
desktop.error.gpdSetup.markerRemove
desktop.error.gpdSetup.markerWrite
desktop.error.gpdSetup.pythonInstall.<phase>   // phase subkeys: timeout, spawn, exit, find
desktop.error.gpdSetup.venvCreate.<phase>
desktop.error.gpdSetup.pipInstall.<phase>
desktop.error.gpdSetup.gpdInstall.<phase>
desktop.error.gpdSetup.configRead
desktop.error.gpdSetup.configParse
desktop.error.gpdSetup.configSerialize
desktop.error.gpdSetup.configWrite
desktop.error.tectonic.binDirCreate
desktop.error.tectonic.unsupportedPlatform
desktop.error.tectonic.httpClient
desktop.error.tectonic.releaseFetch
desktop.error.tectonic.releaseStatus
desktop.error.tectonic.releaseParse
desktop.error.tectonic.assetMissing
desktop.error.tectonic.downloadStart
desktop.error.tectonic.downloadStatus
desktop.error.tectonic.downloadInterrupted
desktop.error.tectonic.archiveOpen
desktop.error.tectonic.archiveEntry
desktop.error.tectonic.binaryWrite
desktop.error.tectonic.binaryMissing
desktop.error.tectonic.archiveUnknown
desktop.error.tectonic.chmod
desktop.error.tectonic.postInstallNotRunnable
desktop.error.tex.rootMissing
desktop.error.tex.outDirCreate
desktop.error.tex.synctexCliMissing
desktop.error.tex.synctexRun
desktop.error.tex.artifactPathResolve
desktop.error.tex.artifactOutsideCache
desktop.error.tex.artifactRead
desktop.error.tex.logRead
desktop.error.project.nameEmpty
desktop.error.project.nameHasSeparator
desktop.error.project.nameReserved
desktop.error.project.parentMissing
desktop.error.project.alreadyExists
desktop.error.project.dirCreate
desktop.error.project.pathEmpty
desktop.error.project.canonicalize
desktop.error.project.probe
desktop.error.unknown
desktop.error.internal
```

That is 60+ final keys (several variants expand into `.<phase>`
subkeys), which is a ~2× increase over the 53 existing `desktop.*` keys.

## 7. Migration plan

Five phases, ordered by user impact. Each phase is a standalone PR so
rebases against upstream OpenCode stay small.

### Phase 0 — Scaffolding  (est. ~200 LOC Rust + TS)

- Add `packages/desktop/src-tauri/src/error.rs` with the full
  `DesktopError` enum (only the variant definitions; no call sites yet).
- Implement `From<std::io::Error>` and `From<serde_json::Error>` as an
  `Internal { detail }` fallback so migrations can proceed one file at a
  time without breaking the `?` operator.
- Add `packages/desktop/src/errors/desktop.ts` with the exhaustive
  switch skeleton (all variants wired to `desktop.error.unknown`
  initially — so TS type-checks from day one).
- Add the `en.ts` keys with English text copied verbatim from the
  current Rust strings so there is no user-visible regression.
- `bindings.ts` regenerates automatically via `test_export_types`.

**Verification:** `cargo test -p opencode-desktop`, `pnpm typecheck` in
`packages/desktop/`.

### Phase 1 — `gpd_setup.rs` (first-run failures — highest impact, non-dismissible)  (~150 LOC Rust, ~50 TS)

- Convert every `Result<_, String>` in `gpd_setup.rs` to
  `Result<_, DesktopError>`. 13 call sites.
- Wire `GpdSetup*` variants in `translateDesktopError`.
- Fill in proper translated strings in `en.ts` for those variants (this
  is also where we audit the current English wording with the
  product team — first-run failures are what every new user sees).

**Why first:** the first-run flow is gated at `lib.rs:747-758` — a
failure here stops the user from doing anything, and the toast is
currently English-only and unfixable without a Rust redeploy.

### Phase 2 — `tex_compiler.rs` + `tectonic.rs` (LaTeX surface)  (~200 LOC Rust, ~70 TS)

- Convert LaTeX compile + artifact commands, plus the Tectonic
  downloader.
- 27 variants land here — the biggest single phase.
- Opportunity to split "compile failed because LaTeX reported an error"
  (which is *always* English from the log and isn't translated) from
  "compile failed because we can't find the compiler" (which should be
  translated). The current code conflates them at `tex_compiler.rs:267`.

### Phase 3 — `cli.rs` (retire the substring bridge)  (~80 LOC Rust, ~40 TS)

- Replace all seven sentinel strings in `cli.rs:131-218` with
  `DesktopError::Cli*` variants.
- Delete the `installError` substring classifier at `cli.ts:6-30`
  entirely; replace its call site with `translateDesktopError`.
- Drop the seven now-orphaned `en.ts` keys (`desktop.cli.error.*`) —
  they are superseded by `desktop.error.cli.*`.

### Phase 4 — Remaining files  (~120 LOC Rust, ~50 TS)

- `lib.rs`, `dependencies.rs`, `project_fs.rs`, `server.rs`,
  `os/windows.rs`.
- ~20 variants.
- At this point `DesktopError` is the only error type any command
  returns; the enum's exhaustive switch on the TS side is the enforced
  contract.

**Total estimate:** ~800 LOC Rust delta (mostly mechanical), ~250 LOC TS
delta, ~60 new i18n keys. Rust net LOC change is near zero because each
`format!("Failed to … ({e})")` becomes `DesktopError::Foo { detail:
e.to_string() }` which is the same length.

## 8. Backward-compat + upstream-divergence note

This repo is a fork of upstream OpenCode (the dispatcher at
`packages/desktop/src-tauri/src/lib.rs` and the spawn machinery in
`cli.rs` are inherited from upstream). Every time we rebase, any Rust
signature change under the common files conflicts textually.

**Recommendation:** isolate `DesktopError` so the rebase surface is one
file, not nine.

1. `DesktopError` lives in a single new module
   `packages/desktop/src-tauri/src/error.rs`. Upstream has no such file,
   so it rebases clean.
2. Each command site gets one change: its return type. `Result<T, String>`
   becomes `Result<T, DesktopError>`. A `From<std::io::Error> for
   DesktopError` impl makes the `?` operator keep working, so the body
   of most commands is unchanged — only the error-producing expressions
   are touched.
3. If a command is pure upstream (no GPD logic in the body) and upstream
   re-words one of its error strings on a future version, our rebase has
   to translate that to a variant. This is still strictly better than
   substring-matching English literals, because the rebase conflict
   surfaces as a type error at `cargo check` time rather than a silent
   TS classifier miss.
4. Commands we add ourselves in GPD-specific files (`gpd_setup.rs`,
   `tectonic.rs`, `tex_compiler.rs`) don't exist upstream so they never
   conflict.

A secondary guideline: the `translateDesktopError` switch is fully
additive, and adding a variant is a one-line diff. If upstream ever
factored their own error taxonomy, we'd be able to implement
`From<UpstreamError> for DesktopError` to bridge.

## 9. Open questions

Items to resolve with the maintainer before implementation starts:

1. **Detail field locale.** Proposal keeps `detail` English because it
   wraps a kernel/reqwest/serde message. Confirm the product team is OK
   showing English in the toast's "Details" disclosure even when the rest
   of the UI is translated.

2. **Specta named-field enum rendering.** `SqliteMigrationProgress` at
   `cli.rs:620-627` proves adjacently-tagged enums with tuple variants
   work. `DesktopError` uses named-field structs per variant. Serde
   supports this; specta should too, but we need to regenerate
   `bindings.ts` on a throwaway branch with one real variant before
   locking the design. This is the one concrete risk left.

3. **`Err(Vec<DesktopError>)`?** Is there any command that wants to
   return multiple errors at once? Current answer: no, compile errors
   already flow inside `Ok(TexCompileResult { errors })`. Confirm before
   implementation.

4. **`Ok(...)` stringly-typed enums.** `check_project_accessible`
   (`project_fs.rs:55-76`) returns `Ok("ok"|"locked"|"missing")` —
   same anti-pattern in the success case. Out of scope here; flag for
   follow-up.

5. **Rebase cadence.** If we rebase against upstream OpenCode
   frequently, phasing minimises rebase conflict surface. If rarely,
   one big PR is simpler. Need maintainer input.

6. **Option fields vs split variants.** `SidecarTerminatedEarly { code:
   Option<i32>, signal: Option<i32> }` has nullable fields. Cleaner as
   two variants (`SidecarTerminatedExit { code }` /
   `SidecarTerminatedSignal { signal }`)? Marginal.
