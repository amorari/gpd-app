#!/usr/bin/env bun
/**
 * GDPR per-user deletion.
 *
 * Purges a user's data from every persistence layer:
 *   1. GCS: rm -r gs://gpd-desktop-logs/user=<hash>/
 *   2. BigQuery: DELETE FROM gpd_logs.sessions WHERE user_hash = <hash>
 *   3. LiteLLM: POST /user/delete (removes virtual keys, spend records)
 *
 * Runs as the shell user's gcloud + bq credentials. Requires --confirm to
 * prevent accidents; defaults to dry-run so you can see what would be
 * deleted first.
 *
 * Usage:
 *   bun scripts/delete-user.ts --user-id=<plain user id>
 *   bun scripts/delete-user.ts --user-hash=<16 hex chars>
 *
 *   Add --confirm to actually delete.
 *   Add --litellm-master-key=<sk-...> to also purge the LiteLLM records.
 */
import crypto from "crypto"
import { spawnSync } from "child_process"

function die(msg: string): never {
  console.error(`delete-user: ${msg}`)
  process.exit(2)
}

function arg(name: string): string | undefined {
  const flag = `--${name}=`
  const raw = process.argv.find((a) => a.startsWith(flag))
  return raw ? raw.slice(flag.length) : undefined
}

function flag(name: string): boolean {
  return process.argv.includes(`--${name}`)
}

function hashUserId(userId: string): string {
  return crypto.createHash("sha256").update(userId, "utf8").digest("hex").slice(0, 16)
}

function run(cmd: string, args: string[], opts: { capture?: boolean } = {}): string {
  const res = spawnSync(cmd, args, {
    stdio: opts.capture ? ["inherit", "pipe", "inherit"] : "inherit",
    encoding: "utf8",
  })
  if (res.status !== 0) die(`${cmd} ${args.join(" ")} → exit ${res.status}`)
  return (res.stdout ?? "").trim()
}

const userId = arg("user-id")
const userHashArg = arg("user-hash")
const confirm = flag("confirm")
const litellmMasterKey = arg("litellm-master-key") ?? process.env.LITELLM_MASTER_KEY
const litellmBase = arg("litellm-base") ?? "https://litellm-production-46bb.up.railway.app"
const bucket = arg("bucket") ?? "gpd-desktop-logs"
const bqProject = arg("bq-project") ?? "gpd-desktop"
const bqDataset = arg("bq-dataset") ?? "gpd_logs"

if (!userId && !userHashArg) die("pass --user-id=<id> OR --user-hash=<hash>")
if (userHashArg && !/^[0-9a-f]{16}$/.test(userHashArg)) {
  die("--user-hash must be 16 hex chars (first 16 of sha256)")
}

const userHash = userHashArg ?? hashUserId(userId!)
const dryRun = !confirm

console.log(`--- GDPR delete ---`)
console.log(`  user_id:   ${userId ?? "(unknown)"}`)
console.log(`  user_hash: ${userHash}`)
console.log(`  mode:      ${dryRun ? "DRY RUN (pass --confirm to execute)" : "EXECUTING"}`)
console.log()

// 1. GCS
console.log(`[1/3] GCS: gs://${bucket}/user=${userHash}/`)
const gcsPrefix = `gs://${bucket}/user=${userHash}/`
const listing = spawnSync("gcloud", ["storage", "ls", "-r", gcsPrefix], {
  stdio: ["inherit", "pipe", "pipe"],
  encoding: "utf8",
})
if (listing.status === 0) {
  const objectLines = (listing.stdout ?? "")
    .split("\n")
    .filter((l) => l.startsWith("gs://") && !l.endsWith("/"))
  console.log(`      ${objectLines.length} object(s) under prefix`)
  if (!dryRun && objectLines.length > 0) {
    run("gcloud", ["storage", "rm", "-r", gcsPrefix])
    console.log(`      ✓ deleted`)
  }
} else {
  // gcloud storage ls returns exit 1 when the prefix matched nothing.
  // That's success-by-vacuous-truth for us (nothing to delete).
  console.log(`      0 objects (prefix empty)`)
}

// 2. BigQuery
console.log()
console.log(`[2/3] BigQuery: DELETE FROM ${bqProject}.${bqDataset}.sessions`)
const bqSelect = `SELECT COUNT(*) as n FROM \`${bqProject}.${bqDataset}.sessions\` WHERE user_hash = '${userHash}'`
try {
  const bqOut = run(
    "bq",
    [
      "query",
      "--format=csv",
      "--use_legacy_sql=false",
      `--project_id=${bqProject}`,
      bqSelect,
    ],
    { capture: true },
  )
  const rowCount = bqOut.split("\n").slice(1)[0]
  console.log(`      ${rowCount} row(s) matching`)
} catch {
  console.log(`      (query failed — table may not exist)`)
}
if (!dryRun) {
  run(
    "bq",
    [
      "query",
      "--use_legacy_sql=false",
      `--project_id=${bqProject}`,
      `DELETE FROM \`${bqProject}.${bqDataset}.sessions\` WHERE user_hash = '${userHash}'`,
    ],
  )
  console.log(`      ✓ deleted`)
}

// 3. LiteLLM
console.log()
console.log(`[3/3] LiteLLM keys + spend for user_id=${userId ?? "(skipped — need plain user_id)"}`)
if (!userId) {
  console.log(`      skipped: LiteLLM indexes by plain user_id, not hash.`)
  console.log(`      Run this script with --user-id=<id> to also purge LiteLLM state.`)
} else if (!litellmMasterKey) {
  console.log(`      skipped: pass --litellm-master-key=<sk-...> or set LITELLM_MASTER_KEY`)
} else {
  if (dryRun) {
    console.log(`      would POST ${litellmBase}/user/delete with {user_ids:[${userId}]}`)
  } else {
    const res = await fetch(`${litellmBase}/user/delete`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${litellmMasterKey}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ user_ids: [userId] }),
    })
    if (res.status === 404) {
      // LiteLLM returns 404 when user_id never had any records — vacuous success.
      console.log(`      ✓ no LiteLLM records for user_id=${userId} (404)`)
    } else if (!res.ok) {
      const txt = await res.text()
      die(`LiteLLM /user/delete returned ${res.status}: ${txt}`)
    } else {
      console.log(`      ✓ ${await res.text()}`)
    }
  }
}

console.log()
if (dryRun) {
  console.log(`Dry-run only. Re-run with --confirm to actually delete.`)
} else {
  console.log(`All done.`)
}
