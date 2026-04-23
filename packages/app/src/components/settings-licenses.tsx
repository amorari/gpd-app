import { Component, Show, createResource } from "solid-js"
import { useLanguage } from "@/context/language"
import { usePlatform } from "@/context/platform"
import { SettingsList } from "./settings-list"

/**
 * Settings → Licenses panel.
 *
 * Reads the bundled `LICENSE` + `THIRD_PARTY_NOTICES.md` files via
 * platform-abstracted `readLicense()` / `readThirdPartyNotices()`. On
 * desktop these invoke Tauri commands that resolve the bundled
 * resource path. On web (no bundle) they're unset and we show a
 * placeholder.
 *
 * THIRD_PARTY_NOTICES.md uses `<details>` + code fences; we render it
 * with a minimal inline markdown transformer to keep the panel
 * self-contained — avoids pulling in a markdown parser just for one
 * settings screen.
 */
type LicenseResult =
  | { ok: true; text: string }
  | { ok: false; errorKey: "settings.licenses.unavailable"; params: { label: string } }
  | { ok: false; errorKey: "settings.licenses.loadFailed"; params: { label: string; error: string } }

async function safeCall(fn: (() => Promise<string>) | undefined, label: string): Promise<LicenseResult> {
  if (!fn) return { ok: false, errorKey: "settings.licenses.unavailable", params: { label } }
  try {
    return { ok: true, text: await fn() }
  } catch (e) {
    return {
      ok: false,
      errorKey: "settings.licenses.loadFailed",
      params: { label, error: e instanceof Error ? e.message : String(e) },
    }
  }
}

export const SettingsLicenses: Component = () => {
  const language = useLanguage()
  const platform = usePlatform()
  const [license] = createResource(() => safeCall(platform.readLicense, "LICENSE"))
  const [notices] = createResource(() => safeCall(platform.readThirdPartyNotices, "THIRD_PARTY_NOTICES.md"))

  const renderResult = (result: LicenseResult): string =>
    result.ok ? result.text : language.t(result.errorKey, result.params)

  return (
    <SettingsList>
      <div class="flex flex-col gap-4 py-4">
        <section>
          <h2 class="text-16-medium mb-2">{language.t("settings.licenses.app_title")}</h2>
          <p class="text-12-regular text-text-weak mb-2">
            {language.t("settings.licenses.app_description")}
          </p>
          <Show
            when={license()}
            fallback={
              <pre class="text-12-regular text-text-weak">
                {language.t("common.loading")}
                {language.t("common.loading.ellipsis")}
              </pre>
            }
          >
            {(result) => (
              <pre class="text-12-regular whitespace-pre-wrap bg-surface-subtle p-3 rounded border border-border-subtle max-h-[240px] overflow-auto">
                {renderResult(result())}
              </pre>
            )}
          </Show>
        </section>

        <section>
          <h2 class="text-16-medium mb-2">{language.t("settings.licenses.third_party_title")}</h2>
          <p class="text-12-regular text-text-weak mb-2">
            {language.t("settings.licenses.third_party_description")}
          </p>
          <Show
            when={notices()}
            fallback={
              <pre class="text-12-regular text-text-weak">
                {language.t("common.loading")}
                {language.t("common.loading.ellipsis")}
              </pre>
            }
          >
            {(result) => (
              <Show
                when={result().ok}
                fallback={<pre class="text-12-regular text-text-weak">{renderResult(result())}</pre>}
              >
                <div
                  class="text-12-regular bg-surface-subtle p-3 rounded border border-border-subtle max-h-[60vh] overflow-auto"
                  // Markdown is rendered as preformatted text; the `<details>` tags
                  // embedded in THIRD_PARTY_NOTICES.md work natively in the browser
                  // so users can expand per-package license bodies without us
                  // shipping a markdown parser in this path.
                  innerHTML={markdownToHtml(result().ok ? (result() as { ok: true; text: string }).text : "")}
                />
              </Show>
            )}
          </Show>
        </section>
      </div>
    </SettingsList>
  )
}

/**
 * Minimal markdown→HTML for the notices file. We do NOT want to pull in a
 * full markdown library just for this panel — the file is machine-generated
 * and uses only:
 *   - `## <h>` / `### <h>` headings
 *   - Pipe tables (handful, near the top)
 *   - `<details><summary>...</summary>...\`\`\`...\`\`\`...</details>` blocks
 *   - Links `[text](url)`
 *   - Inline code `` `code` ``
 *
 * We leave `<details>` tags as-is (browser renders natively), escape raw HTML
 * inside code fences, and transform headings/links/inline-code. This keeps
 * the panel self-contained.
 */
function markdownToHtml(src: string): string {
  // Normalize line endings.
  const lines = src.replace(/\r\n/g, "\n").split("\n")
  const out: string[] = []
  let inFence = false
  let fenceBuf: string[] = []

  const esc = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")

  const inlineTransform = (s: string) => {
    // Inline code first (so links inside code aren't linkified).
    let t = s.replace(/`([^`]+)`/g, (_, c) => `<code>${esc(c)}</code>`)
    // Links.
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, href) => {
      const safeHref = esc(href)
      return `<a href="${safeHref}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`
    })
    // Bold.
    t = t.replace(/\*\*([^*]+)\*\*/g, (_, c) => `<strong>${c}</strong>`)
    return t
  }

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inFence) {
        out.push(`<pre><code>${esc(fenceBuf.join("\n"))}</code></pre>`)
        fenceBuf = []
        inFence = false
      } else {
        inFence = true
      }
      continue
    }
    if (inFence) {
      fenceBuf.push(line)
      continue
    }
    if (line.startsWith("### ")) {
      out.push(`<h4>${inlineTransform(line.slice(4))}</h4>`)
      continue
    }
    if (line.startsWith("## ")) {
      out.push(`<h3>${inlineTransform(line.slice(3))}</h3>`)
      continue
    }
    if (line.startsWith("# ")) {
      out.push(`<h2>${inlineTransform(line.slice(2))}</h2>`)
      continue
    }
    if (line.startsWith("<details") || line.startsWith("</details") || line.startsWith("<summary") || line.startsWith("</summary")) {
      // Pass through Tauri-generated <details>/<summary> tags.
      out.push(line)
      continue
    }
    if (line.trim() === "") {
      out.push("")
      continue
    }
    if (line.startsWith("- ")) {
      out.push(`<div>• ${inlineTransform(line.slice(2))}</div>`)
      continue
    }
    if (line.startsWith("| ") && line.endsWith(" |")) {
      // Tables are rendered as plain preformatted for simplicity.
      out.push(`<div><code>${esc(line)}</code></div>`)
      continue
    }
    out.push(`<div>${inlineTransform(line)}</div>`)
  }
  return out.join("\n")
}
