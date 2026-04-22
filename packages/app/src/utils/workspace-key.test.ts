import { describe, expect, test } from "bun:test"
import { workspaceKey } from "./workspace-key"

describe("workspaceKey", () => {
  test("empty / null / whitespace → empty string", () => {
    expect(workspaceKey(null)).toBe("")
    expect(workspaceKey(undefined)).toBe("")
    expect(workspaceKey("")).toBe("")
    expect(workspaceKey("   ")).toBe("")
  })

  test("trailing slash stripped", () => {
    expect(workspaceKey("/foo/bar")).toBe("/foo/bar")
    expect(workspaceKey("/foo/bar/")).toBe("/foo/bar")
    expect(workspaceKey("/foo/bar///")).toBe("/foo/bar")
  })

  test("root `/` preserved", () => {
    expect(workspaceKey("/")).toBe("/")
  })

  test("backslashes normalized to forward", () => {
    expect(workspaceKey("C:\\Users\\alice\\repo")).toBe("C:/Users/alice/repo")
  })

  test("mixed separators collapse to forward", () => {
    expect(workspaceKey("C:\\Users/alice\\repo/")).toBe("C:/Users/alice/repo")
  })

  test("multiple internal slashes collapsed", () => {
    expect(workspaceKey("/foo//bar///baz")).toBe("/foo/bar/baz")
  })

  test("UNC path preserves leading double-slash", () => {
    expect(workspaceKey("\\\\server\\share\\dir")).toBe("//server/share/dir")
    expect(workspaceKey("//server/share/dir")).toBe("//server/share/dir")
    expect(workspaceKey("//server/share/dir/")).toBe("//server/share/dir")
  })

  test("UNC server-only form stays unambiguous", () => {
    // `//server/` should not collapse to `//server` (reads as incomplete UNC)
    expect(workspaceKey("//server/")).toBe("//server/")
  })

  test("case preserved (no case-fold)", () => {
    // Server tags Bus events with user-supplied case; matching must too.
    expect(workspaceKey("/Users/Alice/Repo")).toBe("/Users/Alice/Repo")
    expect(workspaceKey("C:\\Users\\Alice")).toBe("C:/Users/Alice")
  })

  test("aliases that produced shadow state before Task 1.2 now collapse", () => {
    const a = workspaceKey("/repo")
    const b = workspaceKey("/repo/")
    const c = workspaceKey("/repo//")
    const d = workspaceKey("\\repo")
    expect(a).toBe(b)
    expect(b).toBe(c)
    expect(c).toBe(d)
  })
})
