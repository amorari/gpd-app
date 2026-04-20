// Bun test preload: compiles .tsx imports with babel + babel-preset-solid
// + @babel/preset-typescript so Solid components render correctly in bun:test.
// Required because solid-js's "./jsx-runtime" export points at the runtime
// bundle and does NOT implement the automatic JSX transform — it relies on
// babel-preset-solid's classic compile step (normally done by vite-plugin-solid).
//
// Only applied to .tsx files in packages/app/src (the files we import for the
// dock test). .ts files are handled by Bun's default loader.
import { readFile } from "node:fs/promises"
import babel from "@babel/core"
// @ts-ignore - no types
import solidPreset from "babel-preset-solid"
// @ts-ignore - no types
import tsPreset from "@babel/preset-typescript"

// Runtime plugin: compiles .tsx imports with babel-preset-solid so Solid
// components work inside bun:test. Required because solid-js's jsx-runtime
// export does not provide jsx/jsxs/jsxDEV — it expects the classic
// compile-time transform provided by babel-preset-solid (normally wired up
// by vite-plugin-solid in dev/build).
Bun.plugin({
  name: "solid-tsx",
  setup(build) {
    build.onLoad({ filter: /\.tsx$/ }, async (args) => {
      const source = await readFile(args.path, "utf8")
      const result = await babel.transformAsync(source, {
        filename: args.path,
        babelrc: false,
        configFile: false,
        sourceMaps: "inline",
        presets: [
          [solidPreset, { generate: "dom", hydratable: false }],
          [tsPreset, { isTSX: true, allExtensions: true }],
        ],
      })
      return {
        contents: result?.code ?? source,
        loader: "js",
      }
    })
  },
})
