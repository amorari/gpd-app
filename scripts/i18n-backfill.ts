#!/usr/bin/env bun
/**
 * i18n-backfill.ts — maintenance script.
 *
 * Bulk-machine-translates every key in packages/app/src/i18n/en.ts that is
 * missing from each non-English locale file in the same directory, using the
 * OpenAI Chat Completions API (model: gpt-4.1-mini) with a structured-JSON
 * response format.
 *
 * Usage:
 *   # Requires OPENAI_API_KEY in the environment (or in ../.env relative to
 *   # the monorepo root).
 *   bun run scripts/i18n-backfill.ts
 *
 * Behavior:
 *   - en.ts is the source of truth and is never modified.
 *   - Existing translations in each locale file are preserved verbatim.
 *   - New entries are appended to each locale file in a block preceded by a
 *     "// Backfilled YYYY-MM-DD via scripts/i18n-backfill.ts" marker, placed
 *     immediately before the closing `}` (and any trailing `satisfies`
 *     clause). The file's module header (imports, type alias) and the
 *     `satisfies Partial<Record<Keys, string>>` cast, when present, are
 *     preserved byte-for-byte.
 *   - {{placeholder}} interpolation markers are instructed to be preserved
 *     verbatim and validated post-translation. If any batch fails validation
 *     or returns invalid JSON, the script retries that batch up to 3 times
 *     with a sharper instruction, then aborts if still failing.
 *   - Progress is logged per locale + batch so the caller can follow along.
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

import { dict as en } from "../packages/app/src/i18n/en"
import { dict as ar } from "../packages/app/src/i18n/ar"
import { dict as br } from "../packages/app/src/i18n/br"
import { dict as bs } from "../packages/app/src/i18n/bs"
import { dict as da } from "../packages/app/src/i18n/da"
import { dict as de } from "../packages/app/src/i18n/de"
import { dict as es } from "../packages/app/src/i18n/es"
import { dict as fr } from "../packages/app/src/i18n/fr"
import { dict as ja } from "../packages/app/src/i18n/ja"
import { dict as ko } from "../packages/app/src/i18n/ko"
import { dict as no } from "../packages/app/src/i18n/no"
import { dict as pl } from "../packages/app/src/i18n/pl"
import { dict as ru } from "../packages/app/src/i18n/ru"
import { dict as th } from "../packages/app/src/i18n/th"
import { dict as tr } from "../packages/app/src/i18n/tr"
import { dict as zh } from "../packages/app/src/i18n/zh"
import { dict as zht } from "../packages/app/src/i18n/zht"

// ---------------------------------------------------------------------------
// Env
// ---------------------------------------------------------------------------

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = join(__dirname, "..")
const I18N_DIR = join(REPO_ROOT, "packages", "app", "src", "i18n")

function loadDotenv() {
  // Prefer shell env var if set.
  if (process.env.OPENAI_API_KEY) return
  // Fall back to ../.env (one dir above the monorepo root).
  const candidates = [
    join(REPO_ROOT, "..", ".env"),
    join(REPO_ROOT, ".env"),
  ]
  for (const p of candidates) {
    if (!existsSync(p)) continue
    const content = readFileSync(p, "utf8")
    for (const line of content.split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/)
      if (!m) continue
      const [, k, rawV] = m
      const v = rawV.replace(/^['"]|['"]$/g, "")
      if (!process.env[k]) process.env[k] = v
    }
    break
  }
}
loadDotenv()

const OPENAI_API_KEY = process.env.OPENAI_API_KEY
if (!OPENAI_API_KEY) {
  console.error("ERROR: OPENAI_API_KEY is not set in the environment or .env")
  process.exit(1)
}

const MODEL = process.env.I18N_MODEL || "gpt-4.1-mini"

// ---------------------------------------------------------------------------
// Locale setup
// ---------------------------------------------------------------------------

type Dict = Record<string, string>

const LOCALES: Record<string, { name: string; dict: Dict }> = {
  ar: { name: "Arabic", dict: ar as Dict },
  br: { name: "Brazilian Portuguese", dict: br as Dict },
  bs: { name: "Bosnian", dict: bs as Dict },
  da: { name: "Danish", dict: da as Dict },
  de: { name: "German", dict: de as Dict },
  es: { name: "Spanish", dict: es as Dict },
  fr: { name: "French", dict: fr as Dict },
  ja: { name: "Japanese", dict: ja as Dict },
  ko: { name: "Korean", dict: ko as Dict },
  no: { name: "Norwegian (Bokmål)", dict: no as Dict },
  pl: { name: "Polish", dict: pl as Dict },
  ru: { name: "Russian", dict: ru as Dict },
  th: { name: "Thai", dict: th as Dict },
  tr: { name: "Turkish", dict: tr as Dict },
  zh: { name: "Simplified Chinese", dict: zh as Dict },
  zht: { name: "Traditional Chinese", dict: zht as Dict },
}

const enKeys = Object.keys(en)
const enDict = en as Dict

// ---------------------------------------------------------------------------
// OpenAI call
// ---------------------------------------------------------------------------

interface TranslateBatchOpts {
  localeCode: string
  localeName: string
  keys: string[] // subset of enKeys
  attempt: number // 1-based
}

function buildPrompt(opts: TranslateBatchOpts): {
  system: string
  user: string
} {
  const { localeCode, localeName, attempt } = opts
  const entries: Record<string, string> = {}
  for (const k of opts.keys) entries[k] = enDict[k]

  const system =
    "You are a professional UI localization engineer translating strings " +
    "for a desktop physics-research application named GPD (built by PSI). " +
    "The audience is technical researchers. Translations should be natural, " +
    "concise, and idiomatic for the target language, matching the register " +
    "of a modern productivity desktop app.\n\n" +
    "HARD RULES (non-negotiable):\n" +
    "1. Preserve every {{placeholder}} token VERBATIM. Do not translate the " +
    "   word inside the braces. Do not change the brace style (no full-width " +
    "   braces, no single braces, no spaces inside the braces).\n" +
    "2. Preserve leading and trailing whitespace exactly as given. Some " +
    "   strings end with a space because they are concatenated with user " +
    "   input downstream (e.g. 'Search arXiv for recent papers on ').\n" +
    "3. Preserve ASCII ellipsis '...' where it appears; do not convert to '…'.\n" +
    "4. Preserve proper nouns: GPD, PSI, arXiv, GitHub, OpenAI, Anthropic, " +
    "   Google, MCP, HTTP, API, URL, JSON, YAML, ULID, TOS, UI, OS, CPU, GPU.\n" +
    "5. Do not add quotation marks around the translation. Do not wrap in " +
    "   markdown. Return only a JSON object mapping each input key to its " +
    "   translation.\n" +
    "6. If the source string is literally '...' (three ASCII dots), return " +
    "   '...' unchanged.\n"

  const sharpening =
    attempt > 1
      ? "\nIMPORTANT: A previous attempt produced output that either was " +
        "not valid JSON or altered a {{placeholder}}. Be extra careful: " +
        "echo placeholders verbatim and return only a single JSON object.\n"
      : ""

  const user =
    `Target locale: ${localeCode} (${localeName}).\n` +
    sharpening +
    "Translate every value in the JSON object below from English to " +
    `${localeName}. Return a JSON object with the SAME keys and the ` +
    "translated values. Do not include any keys that are not in the input.\n\n" +
    "SOURCE (English):\n" +
    JSON.stringify(entries, null, 2)

  return { system, user }
}

async function callOpenAI(opts: TranslateBatchOpts): Promise<Dict> {
  const { system, user } = buildPrompt(opts)
  const body = {
    model: MODEL,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user },
    ],
    temperature: 0.2,
    response_format: { type: "json_object" },
  }

  const MAX_NETWORK_RETRIES = 5
  let lastErr: unknown = null
  for (let attempt = 1; attempt <= MAX_NETWORK_RETRIES; attempt++) {
    try {
      const res = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${OPENAI_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      })
      if (!res.ok) {
        const text = await res.text()
        // Rate limit or server error: back off.
        if (res.status === 429 || res.status >= 500) {
          const wait = 2 ** attempt * 500
          console.warn(
            `  [warn] OpenAI HTTP ${res.status}; retrying in ${wait}ms ` +
              `(attempt ${attempt}/${MAX_NETWORK_RETRIES})`,
          )
          await new Promise((r) => setTimeout(r, wait))
          continue
        }
        throw new Error(`OpenAI HTTP ${res.status}: ${text}`)
      }
      const j: any = await res.json()
      const content = j?.choices?.[0]?.message?.content
      if (typeof content !== "string") {
        throw new Error(
          "OpenAI response missing string content: " + JSON.stringify(j),
        )
      }
      const parsed = JSON.parse(content)
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("OpenAI returned non-object JSON: " + content)
      }
      return parsed as Dict
    } catch (e) {
      lastErr = e
      if (attempt === MAX_NETWORK_RETRIES) break
      const wait = 2 ** attempt * 500
      console.warn(
        `  [warn] network/parse error: ${(e as Error).message}; ` +
          `retrying in ${wait}ms`,
      )
      await new Promise((r) => setTimeout(r, wait))
    }
  }
  throw lastErr
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function extractPlaceholders(s: string): string[] {
  const out: string[] = []
  const re = /\{\{[^}]+\}\}/g
  let m: RegExpExecArray | null
  while ((m = re.exec(s)) !== null) out.push(m[0])
  return out.sort()
}

function validateTranslation(
  key: string,
  enValue: string,
  translated: string,
): string | null {
  if (typeof translated !== "string") {
    return `value for ${key} is not a string (${typeof translated})`
  }
  // Placeholder parity.
  const enPH = extractPlaceholders(enValue)
  const trPH = extractPlaceholders(translated)
  if (enPH.length !== trPH.length || enPH.some((p, i) => p !== trPH[i])) {
    return `placeholder mismatch for ${key}: en=${JSON.stringify(enPH)} tr=${JSON.stringify(trPH)}`
  }
  // Leading/trailing whitespace parity.
  const enLead = enValue.match(/^\s*/)![0]
  const trLead = translated.match(/^\s*/)![0]
  const enTrail = enValue.match(/\s*$/)![0]
  const trTrail = translated.match(/\s*$/)![0]
  if (enLead !== trLead) {
    return `leading whitespace mismatch for ${key}: en=${JSON.stringify(enLead)} tr=${JSON.stringify(trLead)}`
  }
  if (enTrail !== trTrail) {
    return `trailing whitespace mismatch for ${key}: en=${JSON.stringify(enTrail)} tr=${JSON.stringify(trTrail)}`
  }
  // Literal ASCII ellipsis parity (if en was literally "..." or contained a
  // trailing "..." sequence, we want the translation to retain it).
  if (enValue === "...") {
    if (translated !== "...") {
      return `ellipsis literal mismatch for ${key}: translation=${JSON.stringify(translated)}`
    }
  }
  return null
}

// Attempt to repair common placeholder drift before full rejection.
function repairPlaceholders(enValue: string, translated: string): string {
  // Replace full-width braces with ASCII.
  let repaired = translated.replace(/｛｛/g, "{{").replace(/｝｝/g, "}}")
  // Replace "{ key }" with "{{key}}" where the key matches one from en.
  const enPHNames = extractPlaceholders(enValue).map((p) =>
    p.slice(2, -2).trim(),
  )
  for (const name of enPHNames) {
    const reSingle = new RegExp(`\\{\\s*${name}\\s*\\}(?!\\})`, "g")
    repaired = repaired.replace(reSingle, `{{${name}}}`)
  }
  return repaired
}

// ---------------------------------------------------------------------------
// File rewriting
// ---------------------------------------------------------------------------

interface FileShape {
  /** Entire prefix of the file, up to and including the last existing entry
   * line. All existing content is preserved byte-for-byte. */
  head: string
  /** The closing suffix: "}\n" or "} satisfies Partial<Record<Keys, string>>\n". */
  tail: string
}

function splitFile(raw: string): FileShape {
  // Strategy: locate the final closing-brace line. Everything before it is
  // `head`, everything from the closing brace onward is `tail`.
  //
  // Files look like: ...,\n\n\n}\n  OR  ...,\n\n\n} satisfies ...\n
  // We match the last line that starts with "}" (optionally followed by
  // " satisfies ...").
  const lines = raw.split("\n")
  // Find the last non-empty line that begins with "}"
  let closeIdx = -1
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i]
    if (line.startsWith("}")) {
      closeIdx = i
      break
    }
  }
  if (closeIdx === -1) {
    throw new Error("Could not find closing } in locale file")
  }
  // Strip any trailing blank lines immediately before the closing brace from
  // head — we'll re-emit exactly one blank line before the backfill block for
  // readability.
  let headEnd = closeIdx - 1
  while (headEnd >= 0 && lines[headEnd].trim() === "") headEnd--
  const head = lines.slice(0, headEnd + 1).join("\n")
  const tail = lines.slice(closeIdx).join("\n")
  return { head, tail }
}

function escapeStringForTs(s: string): string {
  // We always emit with double quotes. Escape backslashes, then double
  // quotes. Convert literal newlines to \n escape sequences (en.ts never
  // embeds raw newlines, but be safe).
  return s
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")
    .replace(/\r/g, "\\r")
    .replace(/\t/g, "\\t")
}

function renderBackfillBlock(
  translations: Array<{ key: string; value: string }>,
  date: string,
): string {
  const header =
    `\n\n  // Backfilled ${date} via scripts/i18n-backfill.ts\n`
  const body = translations
    .map(({ key, value }) => {
      const keyLit = `"${escapeStringForTs(key)}"`
      const valLit = `"${escapeStringForTs(value)}"`
      return `  ${keyLit}: ${valLit},`
    })
    .join("\n")
  return header + body + "\n"
}

// ---------------------------------------------------------------------------
// Main per-locale pipeline
// ---------------------------------------------------------------------------

function chunk<T>(arr: T[], size: number): T[][] {
  const out: T[][] = []
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size))
  return out
}

const BATCH_SIZE = 35
const MAX_SEMANTIC_RETRIES = 3

async function translateBatch(
  localeCode: string,
  localeName: string,
  keys: string[],
): Promise<Dict> {
  let lastErr: string[] = []
  for (let attempt = 1; attempt <= MAX_SEMANTIC_RETRIES; attempt++) {
    const raw = await callOpenAI({
      localeCode,
      localeName,
      keys,
      attempt,
    })
    // Verify we got every key back.
    const missing = keys.filter((k) => !(k in raw))
    if (missing.length) {
      lastErr = [`missing keys in response: ${missing.slice(0, 5).join(", ")}`]
      console.warn(
        `  [warn] attempt ${attempt} missing ${missing.length} keys; retrying`,
      )
      continue
    }
    // Validate each value, attempting placeholder repair on a first miss.
    const errors: string[] = []
    const fixed: Dict = {}
    for (const k of keys) {
      let v = raw[k]
      const enV = enDict[k]
      let err = validateTranslation(k, enV, v)
      if (err && typeof v === "string") {
        const repaired = repairPlaceholders(enV, v)
        if (repaired !== v) {
          const err2 = validateTranslation(k, enV, repaired)
          if (!err2) {
            v = repaired
            err = null
          }
        }
      }
      if (err) errors.push(err)
      else fixed[k] = v
    }
    if (errors.length === 0) return fixed
    lastErr = errors
    console.warn(
      `  [warn] attempt ${attempt} had ${errors.length} validation errors; ` +
        `first: ${errors[0]}. Retrying with sharper prompt.`,
    )
  }
  throw new Error(
    `batch failed after ${MAX_SEMANTIC_RETRIES} attempts. Errors: ` +
      lastErr.slice(0, 3).join(" | "),
  )
}

async function processLocale(localeCode: string) {
  const { name, dict } = LOCALES[localeCode]
  const missing = enKeys.filter((k) => !(k in dict))
  if (missing.length === 0) {
    console.log(`[${localeCode}] already complete, skipping`)
    return { added: 0, failed: [] as string[] }
  }
  console.log(
    `[${localeCode}] ${name}: ${missing.length} keys missing, ` +
      `${Math.ceil(missing.length / BATCH_SIZE)} batch(es)`,
  )
  const batches = chunk(missing, BATCH_SIZE)
  const translations: Array<{ key: string; value: string }> = []
  const failedKeys: string[] = []
  for (let bi = 0; bi < batches.length; bi++) {
    const batch = batches[bi]
    const t0 = Date.now()
    try {
      const out = await translateBatch(localeCode, name, batch)
      // Preserve en.ts ordering within the batch.
      for (const k of batch) {
        translations.push({ key: k, value: out[k] })
      }
      const dt = Date.now() - t0
      console.log(
        `[${localeCode}]   batch ${bi + 1}/${batches.length} ` +
          `(${batch.length} keys) OK in ${dt}ms`,
      )
    } catch (e) {
      console.error(
        `[${localeCode}]   batch ${bi + 1}/${batches.length} FAILED: ` +
          `${(e as Error).message}`,
      )
      failedKeys.push(...batch)
    }
  }
  if (translations.length === 0) {
    console.log(`[${localeCode}] nothing to write`)
    return { added: 0, failed: failedKeys }
  }
  // Load the current file and rewrite.
  const path = join(I18N_DIR, `${localeCode}.ts`)
  const raw = readFileSync(path, "utf8")
  const { head, tail } = splitFile(raw)
  const date = new Date().toISOString().slice(0, 10)
  const block = renderBackfillBlock(translations, date)
  const next = head + block + "\n" + tail
  writeFileSync(path, next, "utf8")
  console.log(
    `[${localeCode}] wrote ${translations.length} translations to ${path}`,
  )
  return { added: translations.length, failed: failedKeys }
}

async function main() {
  console.log(`i18n-backfill: model=${MODEL}, en keys=${enKeys.length}`)
  const summary: Record<string, { added: number; failed: string[] }> = {}
  for (const code of Object.keys(LOCALES)) {
    summary[code] = await processLocale(code)
  }
  console.log("\n===== SUMMARY =====")
  let totalAdded = 0
  let totalFailed = 0
  for (const [code, s] of Object.entries(summary)) {
    console.log(
      `  ${code.padEnd(4)} added=${s.added.toString().padStart(4)} ` +
        `failed=${s.failed.length}`,
    )
    totalAdded += s.added
    totalFailed += s.failed.length
  }
  console.log(`TOTAL added=${totalAdded} failed=${totalFailed}`)
  if (totalFailed > 0) {
    console.log("\nFailed keys (per locale):")
    for (const [code, s] of Object.entries(summary)) {
      if (s.failed.length)
        console.log(`  ${code}: ${s.failed.join(", ")}`)
    }
    process.exit(1)
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
