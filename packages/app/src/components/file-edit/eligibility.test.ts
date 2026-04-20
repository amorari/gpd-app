import { describe, expect, test } from "bun:test"
import { detectLanguage, fileEligibility, splitLines } from "./eligibility"

describe("fileEligibility", () => {
  test("rejects empty/undefined content", () => {
    expect(fileEligibility(undefined).editable).toBe(false)
    expect(fileEligibility({}).editable).toBe(false)
    expect(fileEligibility({ type: "text", content: "" }).editable).toBe(false)
  })

  test("rejects binary content", () => {
    expect(fileEligibility({ type: "binary", content: "ABCD" })).toEqual({
      editable: false,
      reason: "binary",
    })
  })

  test("rejects base64-encoded content", () => {
    expect(fileEligibility({ type: "text", content: "ABCD", encoding: "base64" })).toEqual({
      editable: false,
      reason: "binary",
    })
  })

  test("rejects image/pdf mime types", () => {
    expect(fileEligibility({ type: "text", content: "abc", mimeType: "image/png" })).toEqual({
      editable: false,
      reason: "binary",
    })
    expect(fileEligibility({ type: "text", content: "abc", mimeType: "application/pdf" })).toEqual({
      editable: false,
      reason: "binary",
    })
  })

  test("rejects diff view", () => {
    expect(fileEligibility({ type: "text", content: "abc", diff: "@@ -1,1 +1,1 @@" })).toEqual({
      editable: false,
      reason: "diffView",
    })
  })

  test("accepts small file", () => {
    const result = fileEligibility({ type: "text", content: "hello\nworld" })
    expect(result.editable).toBe(true)
    if (result.editable) expect(result.tier).toBe("small")
  })

  test("accepts medium file", () => {
    const content = "x".repeat(200_000) // 200KB
    const result = fileEligibility({ type: "text", content })
    expect(result.editable).toBe(true)
    if (result.editable) expect(result.tier).toBe("medium")
  })

  test("rejects >1MB file", () => {
    const content = "x".repeat(1_100_000)
    expect(fileEligibility({ type: "text", content })).toEqual({
      editable: false,
      reason: "tooLarge",
    })
  })
})

describe("splitLines", () => {
  test("splits LF-terminated file without trailing empty line", () => {
    expect(splitLines("a\nb\nc\n")).toEqual(["a", "b", "c"])
  })

  test("splits CRLF-terminated file", () => {
    expect(splitLines("a\r\nb\r\nc\r\n")).toEqual(["a", "b", "c"])
  })

  test("keeps final line if no trailing newline", () => {
    expect(splitLines("a\nb\nc")).toEqual(["a", "b", "c"])
  })

  test("empty file is empty", () => {
    expect(splitLines("")).toEqual([""])
  })
})

describe("detectLanguage", () => {
  test("detects markdown", () => {
    expect(detectLanguage("README.md")).toBe("markdown")
    expect(detectLanguage("docs/intro.mdx")).toBe("markdown")
  })

  test("detects python", () => {
    expect(detectLanguage("script.py")).toBe("python")
    expect(detectLanguage("types.pyi")).toBe("python")
  })

  test("detects js/ts", () => {
    expect(detectLanguage("file.ts")).toBe("javascript")
    expect(detectLanguage("file.tsx")).toBe("javascript")
    expect(detectLanguage("file.js")).toBe("javascript")
  })

  test("undefined for unknown", () => {
    expect(detectLanguage("file.tex")).toBeUndefined()
    expect(detectLanguage(undefined)).toBeUndefined()
    expect(detectLanguage("README")).toBeUndefined()
  })
})
