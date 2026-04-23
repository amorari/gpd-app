import { defineConfig } from "vite"
import appPlugin from "@opencode-ai/app/vite"

const host = process.env.TAURI_DEV_HOST

// True when built via `tauri dev` or `tauri build --debug`. Gates the
// vendored tauri-plugin-mcp listener wire-up in src/index.tsx so it ships
// only when the Rust-side plugin is gated in via cfg(debug_assertions).
// TAURI_DEV_HOST is intentionally excluded: it is set for mobile (iOS/Android)
// dev which has no cfg(debug_assertions) plugin path — the Rust side never
// emits so registering JS listeners there is both wrong and wasteful.
const tauriDebug = process.env.TAURI_ENV_DEBUG === "true"

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
