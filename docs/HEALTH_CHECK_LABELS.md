# Health Check Labels — i18n Inventory

Inventory of every English label, description, and install hint the opencode
sidecar emits through `/health/doctor` and `/health/presets` so the app UI can
add a `checkId → i18nKey` mapping in
`packages/app/src/components/settings-dependencies.tsx`.

**Design decision.** The chosen approach is frontend-side mapping (option b):
the sidecar keeps emitting stable English strings and stable `id` fields; the
frontend translates by `id`. The sidecar stays locale-agnostic and remains
safe to consume from CLI tooling or the HTTP API from any client.

**No code changes in this doc.** Inventory + proposed keys only.

---

## 1. Backend emitters

All `/health/*` label data originates in TypeScript. The Python side
(`scripts/gpd/sidecar_main.py`, `gpd.cli doctor`) is not a source of UI
labels.

| Endpoint | File | Helper |
| --- | --- | --- |
| `GET /health/doctor` | `packages/opencode/src/server/instance/health.ts` | `buildDoctorResponse()` (lines 185–407), mounted by `HealthRoutes` (lines 473–522) |
| `GET /health/presets` | `packages/opencode/src/server/instance/health.ts` | `buildPresetsResponse()` (lines 438–471) + `presetRequirements()` (lines 409–436) |
| Route mount | `packages/opencode/src/server/instance/index.ts` line 36 (`.route("/", HealthRoutes())`) | — |

The `GET /health` route in `packages/opencode/src/server/instance/global.ts`
is a separate "is the server alive" probe — it returns
`{ healthy: true, version }` and never reaches the Dependencies panel.

### Python-side contribution (question 4 + 7)

There is **no Python code path that emits labels**. The sidecar invokes the
GPD Python CLI (`python -m gpd.cli doctor --runtime opencode --local
--live-executable-probes`) from `runGpdDoctor()` at
`packages/opencode/src/server/instance/health.ts:158`, but:

- The return value is captured as a **single opaque text blob** and attached
  to the doctor response as `rawOutput`.
- `rawOutput` is only rendered inside the "Details" `<pre>` disclosure in
  `settings-dependencies.tsx` (lines 514–532) — it is not parsed, and none
  of its contents feed the individual check rows.
- Every `Check.label`, `Check.details`, and `Check.installHint.*` value is
  constructed inline in `buildDoctorResponse()` (TypeScript).

**Verdict:** The Python sidecar does not contribute localizable labels to the
Dependencies panel. The `rawOutput` pane is a diagnostic text dump that the
user can show/hide — out of scope for i18n translation at row level, though a
future enhancement could surface `gpd doctor`'s structured JSON output if it
ever exists.

---

## 2. Check inventory

Every check ID the sidecar can emit, with its English defaults. "Dynamic"
means the string is computed from probe output and should be handled with
templates (see Section 5), not static translation.

| `id` | `category` | `label` (static) | `description` / `details` (static vs dynamic) | `installHint.macos` | `installHint.windows` | `installHint.linux` | `installHint.url` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `python` (OK branch) | `runtime` | `Python` | static: `"GPD-managed interpreter under ~/.config/gpd/.venv/"` OR `"System interpreter"` | — | — | — | — |
| `python` (fail: probe failed) | `runtime` | `Python` | dynamic: `probe.error` **or** static fallback `"Python interpreter did not respond to --version"` | `brew install python@3.12` | `winget install --id Python.Python.3.12 -e --source winget` | `sudo apt install python3 python3-venv` | `https://www.python.org/downloads/` |
| `python` (fail: not found) | `runtime` | `Python` | static: `"Python 3.11+ is required. The GPD sidecar was unable to find a Python interpreter."` | `brew install python@3.12` | `winget install --id Python.Python.3.12 -e --source winget` | `sudo apt install python3 python3-venv` | `https://www.python.org/downloads/` |
| `git` (OK) | `core` | `Git` | — (no `details` on OK branch) | — | — | — | — |
| `git` (fail) | `core` | `Git` | static: `"git is required for version control and GPD project history."` | `xcode-select --install` | `winget install --id Git.Git -e --source winget` | `sudo apt install git` | `https://git-scm.com/downloads` |
| `python-venv` (OK) | `core` | `Python venv module` | static: `"venv module importable"` | — | — | — | — |
| `python-venv` (fail: probe failed) | `core` | `Python venv module` | dynamic: `probe.error` **or** static fallback `"venv module missing"` | — | — | `sudo apt install python3-venv` | `https://docs.python.org/3/library/venv.html` |
| `python-venv` (fail: no python) | `core` | `Python venv module` | static: `"Cannot verify venv without a Python interpreter."` | — | — | — | — |
| `latex` (OK) | `optional` | `LaTeX (pdflatex)` | — (no `details` on OK branch) | — | — | — | — |
| `latex` (warn) | `optional` | `LaTeX (pdflatex)` | static: `"Needed for paper-build and publication workflows. Tectonic is a lightweight alternative."` | `brew install --cask mactex-no-gui` | `winget install --id MiKTeX.MiKTeX -e --source winget` | `sudo apt install texlive-latex-recommended texlive-latex-extra` | `https://tectonic-typesetting.github.io/en-US/install.html` |
| `tectonic` (OK) | `optional` | `Tectonic (alternative LaTeX)` | static: `"Self-contained LaTeX build tool."` | — | — | — | — |
| `tectonic` (warn) | `optional` | `Tectonic (alternative LaTeX)` | static: `"Optional Rust-based LaTeX build. Faster to install than a full TeX distribution."` | `brew install tectonic` | `winget install --id TheTectonicTypesettingSystem.Tectonic -e --source winget` | `See tectonic docs for your distro.` | `https://tectonic-typesetting.github.io/en-US/install.html` |
| `pdf-tools` (OK) | `optional` | `PDF tooling` | dynamic: `"Detected pdfinfo"` / `"Detected qpdf"` / `"Detected pdfinfo, qpdf"` | — | — | — | — |
| `pdf-tools` (warn) | `optional` | `PDF tooling` | static: `"Used to inspect PDF artifacts produced by the paper-review workflow."` | `brew install poppler qpdf` | `winget install --id jbarlow83.OCRmyPDF -e --source winget` | `sudo apt install poppler-utils qpdf` | `https://poppler.freedesktop.org/` |

### Check field notes

- `version` and `path` are always raw tool output — **never translate**.
  `version` is the first line of `--version` output (e.g. `"git version 2.42.0"`),
  `path` is the absolute filesystem path from `which`/`where`.
- The three Linux install hints (`sudo apt install ...`) assume Debian/Ubuntu.
  For i18n we still treat them as opaque shell commands. If per-distro strings
  are added later, the key shape supports it (`installHint.linux`).
- `"See tectonic docs for your distro."` is the only Linux install hint that
  is English prose instead of a command. It needs translation.
- The `path` field may briefly diverge from the `version` field: `tectonic`
  at `~/.config/gpd/.capabilities/tectonic/bin/tectonic` is preferred over a
  system-`PATH` copy only if no on-PATH one exists
  (`health.ts:329-333`). This affects which `path` the UI shows but not the
  `label`/`description` strings.

### Frontend-only pseudo-check

When `/health/doctor` itself fails, `settings-dependencies.tsx` (see current
diff at `lines 99–120`) synthesises a fake `Check` with `id: "python"` and
label sourced from `language.t("settings.dependencies.check.python")`. That
key already exists at `en.ts:1091`. No new inventory entry needed — but it
confirms the `checkId → labelKey` lookup pattern is already in use.

---

## 3. Preset inventory

Every preset the sidecar can emit. All are defined in `presetRequirements()`
at `health.ts:409–436`. `missing` is computed from check statuses and is
populated with the **label of the missing check** (or the pseudo-labels
`"LaTeX or Tectonic"` / `"PDF tooling"` for the two synthetic requirements).

| `id` | `label` | `description` | `requires` (internal, not emitted) |
| --- | --- | --- | --- |
| `core-research` | `Core research` | `Default preset. Uses the base runtime-readiness contract.` | `python`, `git`, `python-venv` |
| `theory` | `Theory` | `Bias toward rigorous derivations and exact reasoning.` | `python`, `git`, `python-venv` |
| `numerics` | `Numerics` | `Bias toward computational implementations and convergence work.` | `python`, `git`, `python-venv` |
| `publication` | `Publication / manuscript` | `Drafting, review, build, and submission workflow for research papers.` | `python`, `git`, `python-venv`, `latex-or-tectonic`, `pdf-tools` |

### `missing[]` string inventory

The `missing` array is a `string[]` shown in the UI via
`language.t("settings.dependencies.missing", { tools: preset.missing.join(", ") })`.
Current possible entries:

- `"Python"`, `"Git"`, `"Python venv module"`, `"LaTeX (pdflatex)"`,
  `"Tectonic (alternative LaTeX)"`, `"PDF tooling"` — these are the
  `check.label` values copied into `missing` when a required check fails.
- `"LaTeX or Tectonic"` — synthetic pseudo-label from `health.ts:447`.
- `"PDF tooling"` — synthetic pseudo-label from `health.ts:451`.

Because these strings are already being translated via the check-label key
mapping, the only genuinely new pseudo-labels that need keys are
`"LaTeX or Tectonic"` and `"PDF tooling"`. The latter already matches
`settings.dependencies.tool.pdf-tools` at `en.ts:1103` — the synthetic
pseudo-label collides with the check label by design.

---

## 4. Proposed i18n keys

Naming convention:

- `settings.dependencies.check.<id>.label`
- `settings.dependencies.check.<id>.description.<variant>` — `variant` is
  `okBundled`, `okSystem`, `okDetected`, `okSelfContained`, `probeFailed`,
  `notFound`, `noInterpreter`, `moduleImportable`, `moduleMissing`, `warn`,
  etc., to cover the branching static strings in Section 2.
- `settings.dependencies.check.<id>.installHint.<platform>` — `platform` ∈
  `macos`, `windows`, `linux`, `url`.
- `settings.dependencies.preset.<id>.label`
- `settings.dependencies.preset.<id>.description`
- `settings.dependencies.missing.pseudo.<id>` for synthetic `missing[]`
  pseudo-labels that are not also a check label.

### 4.1 Check keys

`python` (8 keys):

- `settings.dependencies.check.python.label` → `"Python"` — already present
  at `en.ts:1091` under the short path `settings.dependencies.check.python`.
  Either rename to `.label` for uniformity or keep the short path and treat
  `.label` as the same key. **Recommend keeping existing key and layering
  `.description.*` and `.installHint.*` beneath it.**
- `settings.dependencies.check.python.description.okBundled` →
  `"GPD-managed interpreter under ~/.config/gpd/.venv/"`
- `settings.dependencies.check.python.description.okSystem` →
  `"System interpreter"`
- `settings.dependencies.check.python.description.probeFailed` →
  `"Python interpreter did not respond to --version"`
- `settings.dependencies.check.python.description.notFound` →
  `"Python 3.11+ is required. The GPD sidecar was unable to find a Python interpreter."`
- `settings.dependencies.check.python.installHint.macos` →
  `"brew install python@3.12"`
- `settings.dependencies.check.python.installHint.windows` →
  `"winget install --id Python.Python.3.12 -e --source winget"`
- `settings.dependencies.check.python.installHint.linux` →
  `"sudo apt install python3 python3-venv"`
- `settings.dependencies.check.python.installHint.url` →
  `"https://www.python.org/downloads/"` (URLs are not strictly translatable,
  but keying them uniformly lets locales override to language-specific docs
  e.g. `.../ja/downloads/`).

`git` (6 keys):

- `settings.dependencies.check.git.label` → `"Git"`
- `settings.dependencies.check.git.description.fail` →
  `"git is required for version control and GPD project history."`
- `settings.dependencies.check.git.installHint.macos` →
  `"xcode-select --install"`
- `settings.dependencies.check.git.installHint.windows` →
  `"winget install --id Git.Git -e --source winget"`
- `settings.dependencies.check.git.installHint.linux` →
  `"sudo apt install git"`
- `settings.dependencies.check.git.installHint.url` →
  `"https://git-scm.com/downloads"`

`python-venv` (6 keys):

- `settings.dependencies.check.python-venv.label` → `"Python venv module"`
- `settings.dependencies.check.python-venv.description.moduleImportable` →
  `"venv module importable"`
- `settings.dependencies.check.python-venv.description.moduleMissing` →
  `"venv module missing"`
- `settings.dependencies.check.python-venv.description.noInterpreter` →
  `"Cannot verify venv without a Python interpreter."`
- `settings.dependencies.check.python-venv.installHint.linux` →
  `"sudo apt install python3-venv"`
- `settings.dependencies.check.python-venv.installHint.url` →
  `"https://docs.python.org/3/library/venv.html"`

`latex` (6 keys):

- `settings.dependencies.check.latex.label` → `"LaTeX (pdflatex)"`
- `settings.dependencies.check.latex.description.warn` →
  `"Needed for paper-build and publication workflows. Tectonic is a lightweight alternative."`
- `settings.dependencies.check.latex.installHint.macos` →
  `"brew install --cask mactex-no-gui"`
- `settings.dependencies.check.latex.installHint.windows` →
  `"winget install --id MiKTeX.MiKTeX -e --source winget"`
- `settings.dependencies.check.latex.installHint.linux` →
  `"sudo apt install texlive-latex-recommended texlive-latex-extra"`
- `settings.dependencies.check.latex.installHint.url` →
  `"https://tectonic-typesetting.github.io/en-US/install.html"`

`tectonic` (7 keys):

- `settings.dependencies.check.tectonic.label` →
  `"Tectonic (alternative LaTeX)"`
- `settings.dependencies.check.tectonic.description.okSelfContained` →
  `"Self-contained LaTeX build tool."`
- `settings.dependencies.check.tectonic.description.warn` →
  `"Optional Rust-based LaTeX build. Faster to install than a full TeX distribution."`
- `settings.dependencies.check.tectonic.installHint.macos` →
  `"brew install tectonic"`
- `settings.dependencies.check.tectonic.installHint.windows` →
  `"winget install --id TheTectonicTypesettingSystem.Tectonic -e --source winget"`
- `settings.dependencies.check.tectonic.installHint.linux` →
  `"See tectonic docs for your distro."`
- `settings.dependencies.check.tectonic.installHint.url` →
  `"https://tectonic-typesetting.github.io/en-US/install.html"`

`pdf-tools` (8 keys, including the 3 dynamic templates in Section 5):

- `settings.dependencies.check.pdf-tools.label` → `"PDF tooling"`
- `settings.dependencies.check.pdf-tools.description.warn` →
  `"Used to inspect PDF artifacts produced by the paper-review workflow."`
- `settings.dependencies.check.pdf-tools.description.detectedBoth` (template) →
  `"Detected pdfinfo, qpdf"`
- `settings.dependencies.check.pdf-tools.description.detectedPdfinfo` →
  `"Detected pdfinfo"`
- `settings.dependencies.check.pdf-tools.description.detectedQpdf` →
  `"Detected qpdf"`
- `settings.dependencies.check.pdf-tools.installHint.macos` →
  `"brew install poppler qpdf"`
- `settings.dependencies.check.pdf-tools.installHint.windows` →
  `"winget install --id jbarlow83.OCRmyPDF -e --source winget"`
- `settings.dependencies.check.pdf-tools.installHint.linux` →
  `"sudo apt install poppler-utils qpdf"`
- `settings.dependencies.check.pdf-tools.installHint.url` →
  `"https://poppler.freedesktop.org/"`

### 4.2 Preset keys

`core-research`, `theory`, `numerics`, `publication` (2 keys × 4 presets = 8):

- `settings.dependencies.preset.core-research.label` → `"Core research"`
- `settings.dependencies.preset.core-research.description` →
  `"Default preset. Uses the base runtime-readiness contract."`
- `settings.dependencies.preset.theory.label` → `"Theory"`
- `settings.dependencies.preset.theory.description` →
  `"Bias toward rigorous derivations and exact reasoning."`
- `settings.dependencies.preset.numerics.label` → `"Numerics"`
- `settings.dependencies.preset.numerics.description` →
  `"Bias toward computational implementations and convergence work."`
- `settings.dependencies.preset.publication.label` →
  `"Publication / manuscript"`
- `settings.dependencies.preset.publication.description` →
  `"Drafting, review, build, and submission workflow for research papers."`

### 4.3 Missing pseudo-labels

- `settings.dependencies.missing.pseudo.latex-or-tectonic` →
  `"LaTeX or Tectonic"`

(`"PDF tooling"` already has a key as the check label; no new pseudo needed.)

### 4.4 Totals

- Checks: 6 distinct IDs × (1 label + 1-4 descriptions + up to 4 installHint
  variants) ≈ **41 keys**.
- Presets: 4 × 2 = **8 keys**.
- Missing pseudo-labels: **1 key**.
- **Total new keys: ~50** (one — `settings.dependencies.check.python` —
  already present; the rest are additions).

This sits in the expected 40–80 range.

---

## 5. Dynamic content special cases

These strings include probe-derived values that must not be hard-translated.
Use interpolation tokens the existing `language.t(key, vars)` infrastructure
already handles (see `settings.dependencies.summary` at `en.ts:1093` as prior
art for `{{ok}}`-style placeholders).

### 5.1 `python-venv` `description.probeFailed` fallback

Source: `health.ts:275` — `probe.error ?? "venv module missing"`. The probe
error is shell stderr and is already opaque English from the OS tools. The
UI has two options:

1. **Treat probe.error as untranslated ops detail** (recommended) — show it
   verbatim under a generic "`venv module could not be verified`" translated
   header. Add the header key:
   - `settings.dependencies.check.python-venv.description.probeFailed` →
     `"venv module could not be verified — {{error}}"` with `{{error}}` =
     the probe's `stderr`/`stdout` blob.
2. Map common error patterns and fall back to verbatim.

### 5.2 `python` fail-branch dynamic `details`

Source: `health.ts:212` — `probe.error ?? "Python interpreter did not respond to --version"`.
Same pattern. Either:

- `settings.dependencies.check.python.description.probeFailedWithError` →
  `"Python interpreter probe failed — {{error}}"` with `{{error}}` = probe
  stderr blob.

### 5.3 `pdf-tools` OK-branch dynamic `details`

Source: `health.ts:368–370` — enumerates which of `pdfinfo` / `qpdf` were
found. There are three concrete outputs:

- `"Detected pdfinfo"`
- `"Detected qpdf"`
- `"Detected pdfinfo, qpdf"`

Because these are discrete enumerations (not a version+path interpolation),
translate with three static keys as listed in Section 4.1. **Do not** attempt
a `{{tools}}` template with comma-joined `"pdfinfo, qpdf"` — the join order
and the word "and"/"," varies by locale.

### 5.4 Version and path fields

`check.version` (e.g. `"git version 2.42.0"`) and `check.path` (e.g.
`"/opt/homebrew/bin/git"`) are rendered as-is by the UI
(`settings-dependencies.tsx:360` and `:367`). **Never translate.** They are
tool-emitted identifiers.

### 5.5 HTTP error template (already handled)

`en.ts:1092` already has
`settings.dependencies.httpError: "HTTP {{status}} {{statusText}}"` which is
used when `/health/doctor` itself fails. This is the prior-art template we
follow.

### 5.6 Sample envisioned template (hypothetical)

If the sidecar ever starts emitting structured dynamic fields like
`"Python 3.12.4 found at /opt/homebrew/bin/python3"`, the recommended key
shape is:

```
"settings.dependencies.check.python.description.foundAt":
  "Python {{version}} found at {{path}}"
```

…with the frontend mapping layer passing `{ version: check.version, path: check.path }`.
This is not required today (the sidecar exposes `version` and `path` as
separate fields, and the UI already renders them separately in
`CheckRow`), but the key shape is listed here so translators are prepared if
such a string appears later.

---

## 6. Implementation sketch

A `~20-line` mapping layer inside `settings-dependencies.tsx`. Not a code
change in this PR — shown only to verify the proposed key shapes slot in.

```ts
// Maps the stable backend `id` + the branch indicator (derived from what
// fields are populated) to an i18n key. Keeping the map local to the
// component means new checks added to the sidecar produce an English
// fallback (the raw `check.label`) until the map is updated — i.e. never
// a hard crash.
const labelKey = (check: Check) => `settings.dependencies.check.${check.id}.label`

const descriptionKey = (check: Check): string | null => {
  // Branch selection follows the buildDoctorResponse() logic in
  // packages/opencode/src/server/instance/health.ts. Only static strings
  // are mapped here; dynamic `details` (probe errors) use a template
  // key and pass the raw error as {{error}}.
  if (check.id === "python" && check.status === "ok") {
    return check.details?.includes(".venv")
      ? "settings.dependencies.check.python.description.okBundled"
      : "settings.dependencies.check.python.description.okSystem"
  }
  if (check.id === "pdf-tools" && check.status === "ok") {
    const both = check.details?.includes("pdfinfo") && check.details?.includes("qpdf")
    if (both) return "settings.dependencies.check.pdf-tools.description.detectedBoth"
    if (check.details?.includes("pdfinfo")) return "settings.dependencies.check.pdf-tools.description.detectedPdfinfo"
    if (check.details?.includes("qpdf")) return "settings.dependencies.check.pdf-tools.description.detectedQpdf"
  }
  // ...remaining static branches...
  return null
}

const localizedLabel = (check: Check) =>
  language.t(labelKey(check), { defaultValue: check.label })

const localizedDescription = (check: Check) => {
  const k = descriptionKey(check)
  return k ? language.t(k, { defaultValue: check.details ?? "" }) : check.details
}
```

**Contract:**

- Unknown `check.id` → fallback to raw English `check.label` / `check.details`
  (via `defaultValue`), so a sidecar that adds new checks stays functional.
- Dynamic probe errors → separate template key `...description.probeFailedWithError`
  with `{{error}}` = `check.details`.
- `version` / `path` → untouched, rendered raw.
- Install hints → looked up with `settings.dependencies.check.<id>.installHint.<platform>`,
  falling back to `check.installHint?.<platform>` raw.

The corresponding `presetRow` helper maps
`settings.dependencies.preset.<id>.label` /
`settings.dependencies.preset.<id>.description` with the same
`defaultValue`-based fallback.

---

## Appendix: non-localizable fields

These are emitted by the backend but must never be translated:

- `check.id`, `check.status`, `check.category`, `check.version`, `check.path`
- `preset.id`, `preset.status`, `preset.missing[]` (the `missing` **items**
  are themselves translated as check labels, but the **array structure** is
  data)
- `doctor.overall`, `doctor.summary.{ok,warn,fail,total}`,
  `doctor.pythonExecutable`, `doctor.rawOutput`
- URL values inside `installHint.url` (unless a localized docs URL is
  intentionally provided per-locale)

All of the above are either enums, numbers, filesystem paths, or structured
diagnostic output — any of which would break the UI if translated.
