import { Server } from "../../server/server"
import { cmd } from "./cmd"
import { withNetworkOptions, resolveNetworkOptions } from "../network"
import { Flag } from "../../flag/flag"
import { Workspace } from "../../control-plane/workspace"
import { Project } from "../../project/project"
import { Installation } from "../../installation"

/**
 * Self-exit if our parent process dies. Tauri on macOS/Linux has no
 * kernel-level parent-death cleanup (Windows is covered at spawn time by
 * JobObject + KillOnDrop in src-tauri/src/cli.rs). When the Tauri parent
 * is killed ungracefully (SIGKILL from Activity Monitor, panic, OOM, or
 * `bun tauri dev` hot-rebuild), RunEvent::Exit never fires, so the async
 * kill channel in the Rust side never runs, and this sidecar survives,
 * pegging CPU indefinitely. Observed in the wild: 4 orphans at 100% CPU
 * for 24+ hours on a dev laptop.
 *
 * Detection: the process's PPID changes when its parent dies. On macOS
 * the orphan is always adopted by launchd (PID 1). On Linux the orphan
 * is adopted by the nearest subreaper (systemd-logind in user-session
 * scope sets PR_SET_CHILD_SUBREAPER, so PPID becomes that subreaper's
 * PID, not 1). Checking `process.ppid !== initialPpid` covers both —
 * under POSIX a process's PPID only ever changes when its parent dies,
 * so false positives are impossible in practice.
 *
 * Gated to GPD-spawned sidecars via OPENCODE_CLIENT=desktop (set in
 * src-tauri/src/cli.rs when spawning us). Standalone `opencode serve &`
 * users — who may intentionally detach the process past the parent shell
 * — are unaffected. Containers whose entrypoint is opencode start with
 * PPID=1; the `initialPpid === 1` short-circuit skips them too (the
 * container orchestrator owns lifecycle).
 */
function startOrphanWatchdog(): void {
  if (process.platform === "win32") return
  if (process.env["OPENCODE_CLIENT"] !== "desktop") return
  const initialPpid = process.ppid
  if (initialPpid === 1) return
  setInterval(() => {
    if (process.ppid !== initialPpid) {
      console.error(
        `[orphan-watchdog] parent ${initialPpid} died (now reparented to ${process.ppid}), self-exiting`,
      )
      process.exit(0)
    }
  }, 5_000).unref()
}

export const ServeCommand = cmd({
  command: "serve",
  builder: (yargs) => withNetworkOptions(yargs),
  describe: "starts a headless opencode server",
  handler: async (args) => {
    if (!Flag.OPENCODE_SERVER_PASSWORD) {
      console.log("Warning: OPENCODE_SERVER_PASSWORD is not set; server is unsecured.")
    }
    startOrphanWatchdog()
    const opts = await resolveNetworkOptions(args)
    const server = await Server.listen(opts)
    console.log(`opencode server listening on http://${server.hostname}:${server.port}`)

    await new Promise(() => {})
    await server.stop()
  },
})
