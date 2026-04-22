#!/usr/bin/env bun
/**
 * CI check: every `data-testid="..."` value in packages/app/src must be
 * registered in packages/app/src/testing/selectors.ts AND must appear
 * on exactly one element.
 *
 * Enforces Decision 0.B: no string-literal `data-testid` drift, no
 * cross-component collisions. Run as part of `bun turbo test`.
 *
 * Exit codes:
 *   0 — all registered, no duplicates
 *   1 — unregistered value, duplicate value, or structural error
 */

import { readdir, readFile } from "fs/promises"
import { join } from "path"
import { SELECTORS } from "../packages/app/src/testing/selectors"

const APP_SRC = join(import.meta.dir, "..", "packages", "app", "src")

// Match data-testid="foo", data-testid={"foo"}, and data-testid={SELECTORS.FOO}.
// The negative lookbehind (?<!\[) excludes matches inside CSS attribute
// selectors like `[data-testid="..."]` inside <style> tags.
const LITERAL_TESTID = /(?<!\[)data-testid\s*=\s*["'`]([^"'`]+)["'`]/g
const JSX_LITERAL_TESTID = /(?<!\[)data-testid\s*=\s*\{\s*["'`]([^"'`]+)["'`]\s*\}/g
const SELECTORS_REF = /data-testid\s*=\s*\{\s*SELECTORS\.([A-Z0-9_]+)\s*\}/g
const SELECTORS_SPREAD = /\.\.\.testId\(\s*SELECTORS\.([A-Z0-9_]+)\s*\)/g
// Runtime DOM attachment used for elements created imperatively by
// third-party libraries (e.g. CodeMirror's contentDOM).
const SET_ATTRIBUTE_REF = /setAttribute\(\s*["'`]data-testid["'`]\s*,\s*SELECTORS\.([A-Z0-9_]+)\s*\)/g
const SET_ATTRIBUTE_LITERAL = /setAttribute\(\s*["'`]data-testid["'`]\s*,\s*["'`]([^"'`]+)["'`]\s*\)/g

// Files that own selector definitions or otherwise legitimately discuss
// them in prose — skip during walk.
const SKIP_FILES = new Set(["selectors.ts", "selectors.test.ts"])

type Hit = { file: string; value: string; kind: "literal" | "selector-ref" }

async function walk(dir: string, files: string[] = []): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true })
  for (const e of entries) {
    if (e.name === "node_modules" || e.name === "dist" || e.name.startsWith(".")) continue
    const full = join(dir, e.name)
    if (e.isDirectory()) {
      await walk(full, files)
    } else if (/\.(tsx?|jsx?)$/.test(e.name) && !e.name.endsWith(".test.ts") && !e.name.endsWith(".test.tsx")) {
      if (SKIP_FILES.has(e.name)) continue
      files.push(full)
    }
  }
  return files
}

function registeredValues(): Set<string> {
  return new Set(Object.values(SELECTORS))
}

function registeredKeys(): Set<string> {
  return new Set(Object.keys(SELECTORS))
}

async function scan(): Promise<{ hits: Hit[]; errors: string[] }> {
  const errors: string[] = []
  const files = await walk(APP_SRC)
  const regValues = registeredValues()
  const regKeys = registeredKeys()
  const hits: Hit[] = []

  for (const file of files) {
    const src = await readFile(file, "utf8")

    for (const re of [LITERAL_TESTID, JSX_LITERAL_TESTID, SET_ATTRIBUTE_LITERAL]) {
      re.lastIndex = 0
      let m: RegExpExecArray | null
      while ((m = re.exec(src))) {
        const value = m[1]
        if (!regValues.has(value)) {
          errors.push(`${file}: data-testid="${value}" is not registered in SELECTORS`)
        }
        hits.push({ file, value, kind: "literal" })
      }
    }

    for (const re of [SELECTORS_REF, SELECTORS_SPREAD, SET_ATTRIBUTE_REF]) {
      re.lastIndex = 0
      let m: RegExpExecArray | null
      while ((m = re.exec(src))) {
        const key = m[1]
        if (!regKeys.has(key)) {
          errors.push(`${file}: SELECTORS.${key} referenced but not defined`)
          continue
        }
        hits.push({ file, value: (SELECTORS as Record<string, string>)[key], kind: "selector-ref" })
      }
    }
  }

  return { hits, errors }
}

function duplicates(hits: Hit[]): Array<{ value: string; files: string[] }> {
  const byValue = new Map<string, string[]>()
  for (const h of hits) {
    const arr = byValue.get(h.value) ?? []
    arr.push(h.file)
    byValue.set(h.value, arr)
  }
  const dups: Array<{ value: string; files: string[] }> = []
  for (const [value, files] of byValue) {
    if (files.length > 1) dups.push({ value, files })
  }
  return dups
}

async function main() {
  const { hits, errors } = await scan()
  const dups = duplicates(hits)

  if (errors.length === 0 && dups.length === 0) {
    console.log(`ok: ${hits.length} data-testid reference(s) across ${new Set(hits.map((h) => h.file)).size} file(s)`)
    process.exit(0)
  }

  for (const e of errors) console.error(`ERROR ${e}`)
  for (const d of dups) {
    console.error(`ERROR data-testid="${d.value}" appears in >1 file:`)
    for (const f of d.files) console.error(`  - ${f}`)
  }
  process.exit(1)
}

main().catch((e) => {
  console.error("check-selector-uniqueness failed:", e)
  process.exit(1)
})
