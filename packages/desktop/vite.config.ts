import { defineConfig } from "vite"
import appPlugin from "@opencode-ai/app/vite"

const host = process.env.TAURI_DEV_HOST

// True when built via `tauri build --debug`. Gates the tauri-plugin-mcp
// guest-js listener wire-up in src/index.tsx for debug bundles that Vite
// ships prod-mode (import.meta.env.DEV=false). Excluded from release
// builds because the Rust side is already absent there (cfg attribute).
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
