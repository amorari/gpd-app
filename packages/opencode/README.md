# opencode (GPD fork)

Sidecar CLI for the GPD desktop app. Fork of
[anomalyco/opencode](https://github.com/anomalyco/opencode) (itself a fork
of [sst/opencode](https://github.com/sst/opencode)).

GPD-specific additions live under `src/` and `scripts/` — the rest tracks
upstream. The MIT license at the repo root preserves both the upstream
and PSI copyrights.

## Build

```bash
bun install
bun run index.ts
```

## Layout

Sidecar entry: `src/cli/cmd/serve.ts`. LLM + session runtime:
`src/session/`. Storage: `src/storage/` (bun:sqlite + Drizzle). HTTP
adapter: `src/server/adapter.bun.ts`. See `src/` for everything else.
