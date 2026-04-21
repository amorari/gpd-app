# GPD — Get Physics Done

A physics research workspace by [PSI](https://psi.inc). Fork of [OpenCode](https://github.com/anomalyco/opencode).

---

## Install

Download the latest desktop build from [download.gpd.psi.inc](https://download.gpd.psi.inc).

## For professors / post-docs

Open the app, paste the access key you received, start a research project. That's it.

## For developers

- Release playbook: [`docs/RELEASING.md`](docs/RELEASING.md)
- Rebase onto a new upstream OpenCode tag: [`docs/UPDATING.md`](docs/UPDATING.md)
- Architecture + LiteLLM + macOS TCC notes: [`docs/GPD_DISTRIBUTION.md`](docs/GPD_DISTRIBUTION.md)
- Local dev cheatsheet: [`docs/GPD_DESKTOP_CHEATSHEET.md`](docs/GPD_DESKTOP_CHEATSHEET.md)

```bash
bun install
cd packages/desktop && bun tauri dev
```

## License

Upstream OpenCode license applies. See [`LICENSE`](LICENSE).