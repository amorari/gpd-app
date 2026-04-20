import { defineConfig } from "vite"
import appPlugin from "@opencode-ai/app/vite"

const host = process.env.TAURI_DEV_HOST

// True when built via `tauri dev` or `tauri build --debug`. Gates the
// vendored tauri-plugin-mcp listener wire-up in src/index.tsx so it ships
// only when the Rust-side plugin is gated in via cfg(debug_assertions).
// import.meta.env.DEV is false during `tauri build --debug` because Vite
// still runs a production build, so we can't rely on it for this gate.
const tauriDebug = process.env.TAURI_ENV_DEBUG === "true" || process.env.TAURI_DEV_HOST !== undefined

// https://vite.dev/config/
export default defineConfig({
  plugins: [appPlugin],
  publicDir: "../app/public",
  define: {
    __GPD_TAURI_DEBUG__: JSON.stringify(tauriDebug),
  },
  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  esbuild: {
    // Improves production stack traces
    keepNames: true,
  },
  // build: {
  // sourcemap: true,
  // },
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
})
