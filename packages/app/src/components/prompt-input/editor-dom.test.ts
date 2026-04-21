import { describe, expect, test } from "bun:test"
import {
  containsControlChar,
  createTextFragment,
  getCursorPosition,
  getNodeLength,
  getTextLength,
  sanitizeControlChars,
  setCursorPosition,
  stripControlChars,
} from "./editor-dom"

describe("prompt-input editor dom", () => {
  test("createTextFragment preserves newlines with consecutive br nodes", () => {
    const fragment = createTextFragment("foo\n\nbar")
    const container = document.createElement("div")
    container.appendChild(fragment)

    expect(container.childNodes.length).toBe(4)
    expect(container.childNodes[0]?.textContent).toBe("foo")
    expect((container.childNodes[1] as HTMLElement).tagName).toBe("BR")
    expect((container.childNodes[2] as HTMLElement).tagName).toBe("BR")
    expect(container.childNodes[3]?.textContent).toBe("bar")
  })

  test("createTextFragment keeps trailing newline as terminal break", () => {
    const fragment = createTextFragment("foo\n")
    const container = document.createElement("div")
    container.appendChild(fragment)

    expect(container.childNodes.length).toBe(2)
    expect(container.childNodes[0]?.textContent).toBe("foo")
    expect((container.childNodes[1] as HTMLElement).tagName).toBe("BR")
  })

  test("createTextFragment avoids break-node explosion for large multiline content", () => {
    const content = Array.from({ length: 220 }, () => "line").join("\n")
    const fragment = createTextFragment(content)
    const container = document.createElement("div")
    container.appendChild(fragment)

    expect(container.childNodes.length).toBe(1)
    expect(container.childNodes[0]?.nodeType).toBe(Node.TEXT_NODE)
    expect(container.textContent).toBe(content)
  })

  test("createTextFragment keeps terminal break in large multiline fallback", () => {
    const content = `${Array.from({ length: 220 }, () => "line").join("\n")}\n`
    const fragment = createTextFragment(content)
    const container = document.createElement("div")
    container.appendChild(fragment)

    expect(container.childNodes.length).toBe(2)
    expect(container.childNodes[0]?.textContent).toBe(content.slice(0, -1))
    expect((container.childNodes[1] as HTMLElement).tagName).toBe("BR")
  })

  test("length helpers treat breaks as one char and ignore zero-width chars", () => {
    const container = document.createElement("div")
    container.appendChild(document.createTextNode("ab\u200B"))
    container.appendChild(document.createElement("br"))
    container.appendChild(document.createTextNode("cd"))

    expect(getNodeLength(container.childNodes[0]!)).toBe(2)
    expect(getNodeLength(container.childNodes[1]!)).toBe(1)
    expect(getTextLength(container)).toBe(5)
  })

  test("setCursorPosition and getCursorPosition round-trip with pills and breaks", () => {
    const container = document.createElement("div")
    const pill = document.createElement("span")
    pill.dataset.type = "file"
    pill.textContent = "@file"
    container.appendChild(document.createTextNode("ab"))
    container.appendChild(pill)
    container.appendChild(document.createElement("br"))
    container.appendChild(document.createTextNode("cd"))
    document.body.appendChild(container)

    setCursorPosition(container, 2)
    expect(getCursorPosition(container)).toBe(2)

    setCursorPosition(container, 7)
    expect(getCursorPosition(container)).toBe(7)

    setCursorPosition(container, 8)
    expect(getCursorPosition(container)).toBe(8)

    container.remove()
  })

  test("setCursorPosition and getCursorPosition round-trip across blank lines", () => {
    const container = document.createElement("div")
    container.appendChild(document.createTextNode("a"))
    container.appendChild(document.createElement("br"))
    container.appendChild(document.createElement("br"))
    container.appendChild(document.createTextNode("b"))
    document.body.appendChild(container)

    setCursorPosition(container, 2)
    expect(getCursorPosition(container)).toBe(2)

    setCursorPosition(container, 3)
    expect(getCursorPosition(container)).toBe(3)

    container.remove()
  })

  test("setCursorPosition places cursor correctly when text node contains merged \\u200B", () => {
    // Simulates WebKit merging "hello" + "\u200B" into "hello\u200B".
    const container = document.createElement("div")
    container.appendChild(document.createTextNode("hello\u200B"))
    document.body.appendChild(container)

    // Logical position 5 (after "hello") should map to physical offset 5
    // (before the \u200B), so the sentinel stays invisible.
    setCursorPosition(container, 5)
    const selection = window.getSelection()!
    expect(selection.getRangeAt(0).startOffset).toBe(5)
    // getCursorPosition strips \u200B, so round-trip reads back 5.
    expect(getCursorPosition(container)).toBe(5)

    container.remove()
  })

  test("setCursorPosition and getCursorPosition round-trip with \\u200B at end of text node", () => {
    // "ab\u200B" followed by a pill — logical length of text node is 2.
    const container = document.createElement("div")
    const pill = document.createElement("span")
    pill.dataset.type = "file"
    pill.textContent = "@file"
    container.appendChild(document.createTextNode("ab\u200B"))
    container.appendChild(pill)
    container.appendChild(document.createTextNode("cd"))
    document.body.appendChild(container)

    setCursorPosition(container, 0)
    expect(getCursorPosition(container)).toBe(0)

    setCursorPosition(container, 2)
    expect(getCursorPosition(container)).toBe(2)

    // After the pill
    setCursorPosition(container, 7)
    expect(getCursorPosition(container)).toBe(7)

    container.remove()
  })

  test("containsControlChar flags C0 control characters", () => {
    expect(containsControlChar("hello")).toBe(false)
    expect(containsControlChar("")).toBe(false)
    expect(containsControlChar(null)).toBe(false)
    expect(containsControlChar(undefined)).toBe(false)
    // Tab, newline, carriage return are NOT stripped — they're legitimate.
    expect(containsControlChar("\t")).toBe(false)
    expect(containsControlChar("\n")).toBe(false)
    expect(containsControlChar("\r")).toBe(false)
    // The WebKit empty-editor arrow-key bug inserts U+001C / U+001D.
    expect(containsControlChar("\u001c")).toBe(true)
    expect(containsControlChar("\u001d")).toBe(true)
    // ZWSP is visual and harmless via this filter — sentinel handling owns it.
    expect(containsControlChar("\u200b")).toBe(false)
    // Any other C0 control char is flagged.
    expect(containsControlChar("\u0001")).toBe(true)
    expect(containsControlChar("\u001f")).toBe(true)
  })

  test("stripControlChars removes C0 control chars but preserves tab/newline/cr", () => {
    expect(stripControlChars("hello")).toBe("hello")
    expect(stripControlChars("hello\u001cworld")).toBe("helloworld")
    expect(stripControlChars("\u001c\u001d\u001c\u001d")).toBe("")
    expect(stripControlChars("line1\nline2\tcol")).toBe("line1\nline2\tcol")
    expect(stripControlChars("carriage\rreturn")).toBe("carriage\rreturn")
  })

  test("sanitizeControlChars walks all text nodes and mutates in place", () => {
    const container = document.createElement("div")
    container.appendChild(document.createTextNode("hello\u001c"))
    container.appendChild(document.createElement("br"))
    container.appendChild(document.createTextNode("\u001dworld"))
    document.body.appendChild(container)

    const mutated = sanitizeControlChars(container)
    expect(mutated).toBe(true)
    expect(container.textContent).toBe("helloworld")

    // Running again on clean content should be a no-op.
    expect(sanitizeControlChars(container)).toBe(false)

    container.remove()
  })
})
