import { Hono } from "hono"
import { describeRoute, resolver } from "hono-openapi"
import z from "zod"
import { Log } from "../../util/log"
import { lazy } from "../../util/lazy"

/**
 * /health/doctor and /health/presets surface the local runtime readiness
 * for GPD (Python, git, LaTeX, PDF tooling, workflow presets).
 *
 * Implementation strategy:
 *   1. Detect the GPD Python interpreter under ~/.config/gpd/.venv/.
 *   2. Run a handful of lightweight executable probes (mirrors
 *      `gpd doctor --live-executable-probes`).
 *   3. If the GPD Python CLI is available, also try to invoke
 *      `gpd doctor` and capture the raw text output so the UI can show
 *      the "Details" disclosure. When gpd isn't available we still
 *      return a complete response so the panel stays useful.
 */

const log = Log.create({ service: "server.health" })

type Status = "ok" | "warn" | "fail"

const Check = z
  .object({
    id: z.string(),
    label: z.string(),
    status: z.enum(["ok", "warn", "fail"]),
    category: z.enum(["runtime", "core", "optional"]),
    details: z.string().optional(),
    version: z.string().optional(),
    path: z.string().optional(),
    installHint: z
      .object({
        macos: z.string().optional(),
        windows: z.string().optional(),
        linux: z.string().optional(),
        url: z.string().optional(),
      })
      .optional(),
  })
  .meta({ ref: "HealthCheck" })

const DoctorResponse = z
  .object({
    overall: z.enum(["ok", "warn", "fail"]),
    summary: z.object({
      ok: z.number(),
      warn: z.number(),
      fail: z.number(),
      total: z.number(),
    }),
    checks: z.array(Check),
    rawOutput: z.string().optional(),
    pythonExecutable: z.string().optional(),
  })
  .meta({ ref: "DoctorResponse" })

const PresetStatus = z
  .object({
    id: z.string(),
    label: z.string(),
    description: z.string(),
    status: z.enum(["ok", "warn", "fail"]),
    missing: z.array(z.string()),
  })
  .meta({ ref: "PresetStatus" })

const PresetsResponse = z
  .object({
    presets: z.array(PresetStatus),
    rawOutput: z.string().optional(),
  })
  .meta({ ref: "PresetsResponse" })

function homeDir(): string {
  return process.env.HOME ?? process.env.USERPROFILE ?? ""
}

function gpdConfigDir(): string {
  const xdg = process.env.XDG_CONFIG_HOME
  const base = xdg && xdg.length > 0 ? xdg : `${homeDir()}/.config`
  return `${base}/gpd`
}

function gpdPythonPath(): string {
  const venv = `${gpdConfigDir()}/.venv`
  if (process.platform === "win32") return `${venv}\\Scripts\\python.exe`
  return `${venv}/bin/python`
}

/**
 * Location where the desktop app installs the on-demand Tectonic binary. The
 * `install_tectonic` Tauri command downloads into this directory; we include
 * it in the Tectonic lookup so the "Install Tectonic" button flips the panel
 * to green on the next `Check now`.
 */
function tectonicCapabilityPath(): string {
  const bin = `${gpdConfigDir()}/.capabilities/tectonic/bin`
  if (process.platform === "win32") return `${bin}\\tectonic.exe`
  return `${bin}/tectonic`
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await Bun.file(path).stat()
    return true
  } catch {
    return false
  }
}

type ProbeResult = {
  found: boolean
  path?: string
  version?: string
  error?: string
}

async function probeCommand(command: string, args: string[], versionArgs?: string[]): Promise<ProbeResult> {
  try {
    const proc = Bun.spawn([command, ...(versionArgs ?? args)], {
      stdout: "pipe",
      stderr: "pipe",
      stdin: "ignore",
    })
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ])
    if (exitCode !== 0) {
      return { found: false, error: stderr.trim() || stdout.trim() || `exit ${exitCode}` }
    }
    const output = (stdout || stderr).trim()
    const versionLine = output.split(/\r?\n/, 1)[0] ?? ""
    return { found: true, version: versionLine.trim() || undefined }
  } catch (err) {
    return { found: false, error: err instanceof Error ? err.message : String(err) }
  }
}

async function resolveOnPath(name: string): Promise<string | undefined> {
  const isWin = process.platform === "win32"
  const lookup = isWin ? "where" : "which"
  try {
    const proc = Bun.spawn([lookup, name], { stdout: "pipe", stderr: "pipe", stdin: "ignore" })
    const [stdout, exitCode] = await Promise.all([new Response(proc.stdout).text(), proc.exited])
    if (exitCode !== 0) return undefined
    const first = stdout.split(/\r?\n/).find((line) => line.trim().length > 0)
    return first?.trim() || undefined
  } catch {
    return undefined
  }
}

async function runGpdDoctor(python: string): Promise<string | undefined> {
  try {
    const proc = Bun.spawn(
      [python, "-m", "gpd.cli", "doctor", "--runtime", "opencode", "--local", "--live-executable-probes"],
      { stdout: "pipe", stderr: "pipe", stdin: "ignore" },
    )
    // 10s timeout — doctor probes can touch filesystem and shell out.
    const timeoutHandle = setTimeout(() => {
      try {
        proc.kill()
      } catch {}
    }, 10_000)
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
      proc.exited,
    ])
    clearTimeout(timeoutHandle)
    const combined = stdout + (stderr ? `\n${stderr}` : "")
    if (exitCode !== 0 && combined.trim().length === 0) return undefined
    return combined
  } catch (err) {
    log.warn("gpd doctor probe failed", { error: err instanceof Error ? err.message : String(err) })
    return undefined
  }
}

async function buildDoctorResponse() {
  const pythonPath = gpdPythonPath()
  const hasBundledPython = await fileExists(pythonPath)
  const systemPython = await resolveOnPath(process.platform === "win32" ? "python" : "python3")
  const python = hasBundledPython ? pythonPath : systemPython

  const checks: z.infer<typeof Check>[] = []

  // ------- Runtime: Python -------
  if (python) {
    const probe = await probeCommand(python, ["--version"])
    if (probe.found) {
      checks.push({
        id: "python",
        label: "Python",
        status: "ok",
        category: "runtime",
        version: probe.version,
        path: python,
        details: hasBundledPython ? "GPD-managed interpreter under ~/.config/gpd/.venv/" : "System interpreter",
      })
    } else {
      checks.push({
        id: "python",
        label: "Python",
        status: "fail",
        category: "runtime",
        details: probe.error ?? "Python interpreter did not respond to --version",
        installHint: {
          macos: "brew install python@3.12",
          windows: "winget install --id Python.Python.3.12 -e --source winget",
          linux: "sudo apt install python3 python3-venv",
          url: "https://www.python.org/downloads/",
        },
      })
    }
  } else {
    checks.push({
      id: "python",
      label: "Python",
      status: "fail",
      category: "runtime",
      details: "Python 3.11+ is required. The GPD sidecar was unable to find a Python interpreter.",
      installHint: {
        macos: "brew install python@3.12",
        windows: "winget install --id Python.Python.3.12 -e --source winget",
        linux: "sudo apt install python3 python3-venv",
        url: "https://www.python.org/downloads/",
      },
    })
  }

  // ------- Core: git -------
  {
    const gitPath = await resolveOnPath("git")
    if (gitPath) {
      const probe = await probeCommand(gitPath, ["--version"])
      checks.push({
        id: "git",
        label: "Git",
        status: probe.found ? "ok" : "warn",
        category: "core",
        version: probe.version,
        path: gitPath,
      })
    } else {
      checks.push({
        id: "git",
        label: "Git",
        status: "fail",
        category: "core",
        details: "git is required for version control and GPD project history.",
        installHint: {
          macos: "xcode-select --install",
          windows: "winget install --id Git.Git -e --source winget",
          linux: "sudo apt install git",
          url: "https://git-scm.com/downloads",
        },
      })
    }
  }

  // ------- Core: python venv module -------
  if (python) {
    const probe = await probeCommand(python, ["-m", "venv", "--help"])
    checks.push({
      id: "python-venv",
      label: "Python venv module",
      status: probe.found ? "ok" : "fail",
      category: "core",
      details: probe.found ? "venv module importable" : (probe.error ?? "venv module missing"),
      installHint: probe.found
        ? undefined
        : {
            linux: "sudo apt install python3-venv",
            url: "https://docs.python.org/3/library/venv.html",
          },
    })
  } else {
    checks.push({
      id: "python-venv",
      label: "Python venv module",
      status: "fail",
      category: "core",
      details: "Cannot verify venv without a Python interpreter.",
    })
  }

  // ------- Optional: LaTeX (pdflatex) -------
  {
    const pdflatex = await resolveOnPath("pdflatex")
    if (pdflatex) {
      const probe = await probeCommand(pdflatex, ["-version"])
      checks.push({
        id: "latex",
        label: "LaTeX (pdflatex)",
        status: probe.found ? "ok" : "warn",
        category: "optional",
        version: probe.version,
        path: pdflatex,
      })
    } else {
      checks.push({
        id: "latex",
        label: "LaTeX (pdflatex)",
        status: "warn",
        category: "optional",
        details: "Needed for paper-build and publication workflows. Tectonic is a lightweight alternative.",
        installHint: {
          macos: "brew install --cask mactex-no-gui",
          windows: "winget install --id MiKTeX.MiKTeX -e --source winget",
          linux: "sudo apt install texlive-latex-recommended texlive-latex-extra",
          url: "https://tectonic-typesetting.github.io/en-US/install.html",
        },
      })
    }
  }

  // ------- Optional: Tectonic (preferred LaTeX alternative) -------
  {
    // Tectonic can be on the system PATH (user installed via brew/winget) or
    // in the GPD capabilities dir populated by the in-app "Install Tectonic"
    // button. Prefer the on-PATH copy when both exist so a user who has
    // mixed installs sees their explicit install first.
    let tectonic = await resolveOnPath("tectonic")
    if (!tectonic) {
      const managed = tectonicCapabilityPath()
      if (await fileExists(managed)) tectonic = managed
    }
    const probe = tectonic ? await probeCommand(tectonic, ["--version"]) : undefined
    checks.push({
      id: "tectonic",
      label: "Tectonic (alternative LaTeX)",
      status: tectonic && probe?.found ? "ok" : "warn",
      category: "optional",
      version: probe?.version,
      path: tectonic,
      details: tectonic
        ? "Self-contained LaTeX build tool."
        : "Optional Rust-based LaTeX build. Faster to install than a full TeX distribution.",
      installHint: tectonic
        ? undefined
        : {
            macos: "brew install tectonic",
            windows: "winget install --id TheTectonicTypesettingSystem.Tectonic -e --source winget",
            linux: "See tectonic docs for your distro.",
            url: "https://tectonic-typesetting.github.io/en-US/install.html",
          },
    })
  }

  // ------- Optional: PDF tooling (pdfinfo / qpdf) -------
  {
    const pdfinfo = await resolveOnPath("pdfinfo")
    const qpdf = await resolveOnPath("qpdf")
    const any = pdfinfo ?? qpdf
    checks.push({
      id: "pdf-tools",
      label: "PDF tooling",
      status: any ? "ok" : "warn",
      category: "optional",
      version: any ? (await probeCommand(any, ["--version"]).then((p) => p.version)) : undefined,
      path: any,
      details: any
        ? `Detected ${pdfinfo ? "pdfinfo" : ""}${pdfinfo && qpdf ? ", " : ""}${qpdf ? "qpdf" : ""}`
        : "Used to inspect PDF artifacts produced by the paper-review workflow.",
      installHint: any
        ? undefined
        : {
            macos: "brew install poppler qpdf",
            windows: "winget install --id jbarlow83.OCRmyPDF -e --source winget",
            linux: "sudo apt install poppler-utils qpdf",
            url: "https://poppler.freedesktop.org/",
          },
    })
  }

  // ------- Aggregate -------
  const summary = checks.reduce(
    (acc, check) => {
      acc.total += 1
      acc[check.status] += 1
      return acc
    },
    { ok: 0, warn: 0, fail: 0, total: 0 },
  )

  const overall: Status = summary.fail > 0 ? "fail" : summary.warn > 0 ? "warn" : "ok"

  // Only try gpd doctor if python is available and GPD CLI appears installed.
  let rawOutput: string | undefined
  if (python && hasBundledPython) {
    rawOutput = await runGpdDoctor(python)
  }

  return {
    overall,
    summary,
    checks,
    rawOutput,
    pythonExecutable: python,
  }
}

function presetRequirements(): Array<{ id: string; label: string; description: string; requires: string[] }> {
  return [
    {
      id: "core-research",
      label: "Core research",
      description: "Default preset. Uses the base runtime-readiness contract.",
      requires: ["python", "git", "python-venv"],
    },
    {
      id: "theory",
      label: "Theory",
      description: "Bias toward rigorous derivations and exact reasoning.",
      requires: ["python", "git", "python-venv"],
    },
    {
      id: "numerics",
      label: "Numerics",
      description: "Bias toward computational implementations and convergence work.",
      requires: ["python", "git", "python-venv"],
    },
    {
      id: "publication",
      label: "Publication / manuscript",
      description: "Drafting, review, build, and submission workflow for research papers.",
      requires: ["python", "git", "python-venv", "latex-or-tectonic", "pdf-tools"],
    },
  ]
}

async function buildPresetsResponse(doctor: Awaited<ReturnType<typeof buildDoctorResponse>>) {
  const byId = new Map(doctor.checks.map((c) => [c.id, c]))
  const latexOk = (byId.get("latex")?.status === "ok") || (byId.get("tectonic")?.status === "ok")
  const pdfOk = byId.get("pdf-tools")?.status === "ok"

  const presets = presetRequirements().map((preset) => {
    const missing: string[] = []
    for (const req of preset.requires) {
      if (req === "latex-or-tectonic") {
        if (!latexOk) missing.push("LaTeX or Tectonic")
        continue
      }
      if (req === "pdf-tools") {
        if (!pdfOk) missing.push("PDF tooling")
        continue
      }
      const entry = byId.get(req)
      if (!entry || entry.status === "fail") missing.push(entry?.label ?? req)
    }
    const status: Status = missing.length === 0 ? "ok" : missing.some(() => true) ? "warn" : "ok"
    return { ...preset, status, missing, requires: undefined as unknown as string[] }
  })

  // Strip the requires helper field before returning.
  const cleaned = presets.map(({ id, label, description, status, missing }) => ({
    id,
    label,
    description,
    status,
    missing,
  }))

  return { presets: cleaned }
}

export const HealthRoutes = lazy(() =>
  new Hono()
    .get(
      "/health/doctor",
      describeRoute({
        summary: "Get GPD runtime doctor report",
        description:
          "Runs lightweight tool probes (Python, git, venv, LaTeX, PDF tooling) and returns a structured readiness report. Mirrors `gpd doctor --live-executable-probes`.",
        operationId: "health.doctor",
        responses: {
          200: {
            description: "Doctor report",
            content: {
              "application/json": {
                schema: resolver(DoctorResponse),
              },
            },
          },
        },
      }),
      async (c) => {
        const result = await buildDoctorResponse()
        return c.json(result)
      },
    )
    .get(
      "/health/presets",
      describeRoute({
        summary: "Get GPD workflow preset readiness",
        description:
          "Returns a readiness status for each workflow preset (core-research, theory, numerics, publication) based on the doctor report.",
        operationId: "health.presets",
        responses: {
          200: {
            description: "Preset readiness",
            content: {
              "application/json": {
                schema: resolver(PresetsResponse),
              },
            },
          },
        },
      }),
      async (c) => {
        const doctor = await buildDoctorResponse()
        const result = await buildPresetsResponse(doctor)
        return c.json(result)
      },
    ),
)
