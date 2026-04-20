// Shared eligibility rules for inline line editing. Must stay in sync with the
// read-only reason copy exposed via i18n (file.edit.readonly.reason.*).

export const SMALL_FILE_BYTES = 100 * 1024 // 100 KB
export const MEDIUM_FILE_BYTES = 1024 * 1024 // 1 MB

export type Eligibility =
  | { editable: true; tier: "small" | "medium"; size: number }
  | { editable: false; reason: "tooLarge" | "binary" | "diffView" | "empty" }

type Content = {
  type?: "text" | "binary"
  content?: string
  encoding?: "base64" | (string & {})
  mimeType?: string
  diff?: string
} | undefined

function isBinaryContent(content: Content): boolean {
  if (!content) return false
  if (content.type === "binary") return true
  if (content.encoding === "base64") return true
  if (content.mimeType && content.mimeType.startsWith("image/")) return true
  if (content.mimeType === "application/pdf") return true
  return false
}

function byteLengthOf(text: string): number {
  if (typeof TextEncoder !== "undefined") {
    try {
      return new TextEncoder().encode(text).byteLength
    } catch {
      // fall through
    }
  }
  // Fall back to a conservative upper bound (chars * 4 for worst-case UTF-8).
  return text.length * 4
}

/**
 * Compute whether a file content should permit inline line edits.
 *
 * Rules:
 *   - Diff view (diff present) => read-only
 *   - Binary / image / pdf / base64 encoded => read-only
 *   - Missing content (empty or not loaded) => read-only
 *   - Size >1MB => read-only (tooLarge)
 *   - 100KB..1MB => editable (medium)
 *   - <100KB => editable (small)
 */
export function fileEligibility(content: Content): Eligibility {
  if (!content) return { editable: false, reason: "empty" }
  if (content.diff && content.diff.trim()) return { editable: false, reason: "diffView" }
  if (isBinaryContent(content)) return { editable: false, reason: "binary" }

  const text = typeof content.content === "string" ? content.content : ""
  if (!text) return { editable: false, reason: "empty" }

  const size = byteLengthOf(text)
  if (size > MEDIUM_FILE_BYTES) return { editable: false, reason: "tooLarge" }
  if (size > SMALL_FILE_BYTES) return { editable: true, tier: "medium", size }
  return { editable: true, tier: "small", size }
}

/**
 * Split a text file's content into its logical lines for hotspot display.
 * Always uses LF semantics for indexing; callers should never use the result
 * for writing back to disk.
 */
export function splitLines(content: string): string[] {
  const normalized = content.replace(/\r\n/g, "\n")
  const lines = normalized.split("\n")
  // If the file ends with a newline, the split produces a trailing empty string
  // that does not correspond to an editable line.
  if (lines.length > 0 && lines[lines.length - 1] === "" && normalized.endsWith("\n")) lines.pop()
  return lines
}

/**
 * Detect a CodeMirror language preset from a file path. Returns `undefined`
 * for unknown extensions so the editor falls back to plain text.
 */
export type EditorLanguage = "markdown" | "python" | "javascript" | undefined

export function detectLanguage(path: string | undefined): EditorLanguage {
  if (!path) return undefined
  const lower = path.toLowerCase()
  if (lower.endsWith(".md") || lower.endsWith(".mdx") || lower.endsWith(".markdown")) return "markdown"
  if (lower.endsWith(".py") || lower.endsWith(".pyi")) return "python"
  if (
    lower.endsWith(".js") ||
    lower.endsWith(".jsx") ||
    lower.endsWith(".ts") ||
    lower.endsWith(".tsx") ||
    lower.endsWith(".mjs") ||
    lower.endsWith(".cjs") ||
    lower.endsWith(".mts") ||
    lower.endsWith(".cts")
  ) {
    return "javascript"
  }
  return undefined
}
