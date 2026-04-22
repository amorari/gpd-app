import { describe, expect, test } from "bun:test"
import {
  canonicalizeAndReject,
  rejectUnsafeProjectPath,
  type CanonicalizePlatform,
} from "./project-path"

const HOME = "/Users/alice"

describe("rejectUnsafeProjectPath — legacy cases (pre-Task-1.3)", () => {
  test("null / undefined / whitespace", () => {
    expect(rejectUnsafeProjectPath(null, HOME)?.key).toBe("project.rejection.none")
    expect(rejectUnsafeProjectPath(undefined, HOME)?.key).toBe("project.rejection.none")
    expect(rejectUnsafeProjectPath("", HOME)?.key).toBe("project.rejection.none")
    expect(rejectUnsafeProjectPath("   ", HOME)?.key).toBe("project.rejection.none")
  })

  test("filesystem roots", () => {
    expect(rejectUnsafeProjectPath("/", HOME)?.key).toBe("project.rejection.filesystemRoot")
    expect(rejectUnsafeProjectPath("C:\\", HOME)?.key).toBe("project.rejection.driveRoot")
    expect(rejectUnsafeProjectPath("D:/", HOME)?.key).toBe("project.rejection.driveRoot")
  })

  test("unexpanded tilde and bare dot segments", () => {
    expect(rejectUnsafeProjectPath("~", HOME)?.key).toBe("project.rejection.unexpandedTilde")
    expect(rejectUnsafeProjectPath(".", HOME)?.key).toBe("project.rejection.invalid")
    expect(rejectUnsafeProjectPath("..", HOME)?.key).toBe("project.rejection.invalid")
  })

  test("home + forbidden subdirectories", () => {
    expect(rejectUnsafeProjectPath(HOME, HOME)?.key).toBe("project.rejection.homeDir")
    expect(rejectUnsafeProjectPath(`${HOME}/`, HOME)?.key).toBe("project.rejection.homeDir")
    expect(rejectUnsafeProjectPath(`${HOME}/Documents`, HOME)?.key).toBe("project.rejection.homeSubdir")
    expect(rejectUnsafeProjectPath(`${HOME}/Downloads`, HOME)?.key).toBe("project.rejection.homeSubdir")
  })

  test("system directories", () => {
    for (const sys of ["/Users", "/home", "/System", "/private", "/var", "/etc", "/usr"]) {
      expect(rejectUnsafeProjectPath(sys, HOME)?.key).toBe("project.rejection.systemDir")
    }
  })

  test("legitimate project paths pass", () => {
    expect(rejectUnsafeProjectPath(`${HOME}/projects/my-repo`, HOME)).toBeNull()
    expect(rejectUnsafeProjectPath(`${HOME}/Documents/subdir`, HOME)).toBeNull()
    expect(rejectUnsafeProjectPath("/opt/proj", HOME)).toBeNull() // /opt itself is forbidden, subdir is fine
  })
})

describe("rejectUnsafeProjectPath — Task 1.3 hardening", () => {
  test("`..` segments resolve before comparison", () => {
    // Was: `<home>/Documents/..` passed the string-compare guard because
    // the raw string didn't equal `<home>`. Now it normalizes to `<home>`
    // and is rejected.
    expect(rejectUnsafeProjectPath(`${HOME}/Documents/..`, HOME)?.key).toBe("project.rejection.homeDir")
    expect(rejectUnsafeProjectPath(`${HOME}/projects/../Documents`, HOME)?.key).toBe(
      "project.rejection.homeSubdir",
    )
    expect(rejectUnsafeProjectPath("/Users/alice/../..", HOME)?.key).toBe("project.rejection.filesystemRoot")
  })

  test("URL-encoded traversal (%2e%2e) decoded before normalization", () => {
    expect(rejectUnsafeProjectPath(`${HOME}/Documents/%2e%2e`, HOME)?.key).toBe("project.rejection.homeDir")
    expect(rejectUnsafeProjectPath(`/Users/alice/%2e%2e/%2e%2e`, HOME)?.key).toBe(
      "project.rejection.filesystemRoot",
    )
  })

  test("repeated separators collapsed", () => {
    expect(rejectUnsafeProjectPath(`${HOME}//Documents`, HOME)?.key).toBe("project.rejection.homeSubdir")
    expect(rejectUnsafeProjectPath(`${HOME}///Downloads///`, HOME)?.key).toBe("project.rejection.homeSubdir")
  })

  test("mixed separators (Windows-style) normalized", () => {
    const winHome = "C:\\Users\\alice"
    expect(rejectUnsafeProjectPath(`${winHome}\\Documents\\..`, winHome)?.key).toBe(
      "project.rejection.homeDir",
    )
    expect(rejectUnsafeProjectPath(`${winHome}/Documents`, winHome)?.key).toBe(
      "project.rejection.homeSubdir",
    )
  })

  test("relative `.` and `./ ` no-ops don't leak", () => {
    // Previously `./` was passed through unchanged; now it normalizes
    // to empty and is flagged invalid.
    expect(rejectUnsafeProjectPath("./", HOME)?.key).toBe("project.rejection.invalid")
    expect(rejectUnsafeProjectPath("../", HOME)?.key).toBe("project.rejection.invalid")
  })

  test("traversal deep enough to reach /Users still rejected", () => {
    expect(rejectUnsafeProjectPath(`${HOME}/a/b/c/../../../..`, HOME)?.key).toBe(
      "project.rejection.systemDir",
    )
  })
})

describe("canonicalizeAndReject — async trust-boundary helper", () => {
  const makePlatform = (impl: (path: string) => string | null): CanonicalizePlatform => ({
    canonicalizeProjectPath: async (p: string) => impl(p),
  })

  test("canonical path passes through when safe", async () => {
    const platform = makePlatform((p) => p.replace(/\/+$/, ""))
    const res = await canonicalizeAndReject(`${HOME}/projects/repo`, HOME, platform)
    expect(res).toEqual({ ok: true, path: `${HOME}/projects/repo` })
  })

  test("canonicalization reveals a symlink into forbidden root", async () => {
    // Simulate: user supplies a symlink path that resolves to /System.
    const platform = makePlatform((p) => (p.includes("link") ? "/System" : p))
    const res = await canonicalizeAndReject(`${HOME}/link-to-system`, HOME, platform)
    expect(res.ok).toBe(false)
    if (!res.ok && res.reason === "rejected") {
      expect(res.rejection.key).toBe("project.rejection.systemDir")
    } else {
      throw new Error(`expected rejected, got ${JSON.stringify(res)}`)
    }
  })

  test("canonicalization returning null → unreachable (not rejected)", async () => {
    const platform = makePlatform(() => null)
    const res = await canonicalizeAndReject(`${HOME}/missing`, HOME, platform)
    expect(res).toEqual({ ok: false, reason: "unreachable" })
  })

  test("platform without canonicalizeProjectPath capability → unreachable", async () => {
    const platform: CanonicalizePlatform = {}
    const res = await canonicalizeAndReject(`${HOME}/anywhere`, HOME, platform)
    expect(res).toEqual({ ok: false, reason: "unreachable" })
  })

  test("empty / null input rejected before hitting platform", async () => {
    let called = false
    const platform = makePlatform(() => {
      called = true
      return ""
    })
    const res = await canonicalizeAndReject("", HOME, platform)
    expect(called).toBe(false)
    expect(res.ok).toBe(false)
    if (!res.ok && res.reason === "rejected") {
      expect(res.rejection.key).toBe("project.rejection.none")
    }
  })
})
