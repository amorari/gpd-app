# Releasing GPD Desktop

How to cut, inspect, and publish GPD Desktop releases on `psi-oss/opencode`.

## TL;DR

```bash
# 1. Cut a draft (reads get-physics-done version from GitHub by default)
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd

# 2. When you're satisfied with the draft, publish it
gh workflow run gpd-publish-draft.yml --repo psi-oss/opencode --ref gpd
```

Builds are uploaded to the draft release **as each platform finishes**, so mac-intel / mac-arm binaries appear first (~6 min), linux next (~8 min), Windows last (~15 min). You can download them from the draft page while the rest are still building.

---

## Repo refresher

- Default branch on `psi-oss/opencode` is `gpd`, not `main`. When you see `git push origin gpd`, that's the equivalent of pushing to `main` on a normal repo — it's where we work.
- `main` on the fork tracks upstream and is not touched during day-to-day work.
- `gh-pages` is the download page and is updated automatically by the `gpd-download-page.yml` workflow on `release:published`.

---

## Workflows involved

| Workflow file | Trigger | What |
|---|---|---|
| `.github/workflows/gpd-release.yml` | `workflow_dispatch` | Build CLI + four desktop platforms + upload to a **draft** release |
| `.github/workflows/gpd-publish-draft.yml` | `workflow_dispatch` | Flip a draft release to published |
| `.github/workflows/gpd-download-page.yml` | `release:published` | Regenerates the download page |

---

## Two versions, decoupled

A release carries two versions — **desktop** and **sidecar** (the bundled `get-physics-done` Python package) — and they are intentionally allowed to drift:

- **Desktop version** drives the tag, asset filenames, and the app's reported version. It's what the auto-updater compares.
- **Sidecar version** is reported in the release body for clarity. It's the version of `get-physics-done` available at build time (and what fresh installs will start with).

The release workflow's `resolve-version` job always resolves the sidecar version from `version_source` (default: `github` — reads `pyproject.toml` on `psi-oss/get-physics-done@main`; can also be `pypi` or `npm`). The desktop version then takes the explicit `version` input if provided, otherwise follows the sidecar.

### When to override

- **Desktop-only patch releases** (UI copy fix, bug fix, translation, etc. — no sidecar change): bump desktop independently with `-f version=<next-patch>`. The auto-updater will promote this to existing installs. The release body still accurately reports which sidecar version is bundled.
- **Sidecar release** (new `get-physics-done` on PyPI / GitHub): leave `version` empty, let desktop follow.

### Tag collision handling

If the chosen `gpd-desktop-v<version>` tag already exists:
- If it's a **draft**, the workflow appends its assets to that draft.
- If it's **published**, the workflow appends a redrop suffix: `1.1.0` → `1.1.0-1` → `1.1.0-2` → …, stopping at the first available slot. Hard cap `-100`.

Tag shape:

```
gpd-desktop-v<desktop-version>[-<redrop-counter>]
```

⚠️ **The redrop suffix (`-N`) does NOT reach existing installs via auto-update.** semver treats `1.1.0-1` as a *pre-release of* `1.1.0` and sorts it *below*; the updater concludes the new build is older. Auto-update is otherwise healthy — the plugin is registered whenever CI has `TAURI_SIGNING_PRIVATE_KEY` (see `constants.rs:UPDATER_ENABLED`), and `latest.json` is signed. Treat `-N` suffixes as "fresh-install only" deliveries (download page, new machines). For patch releases that need to promote, always use a real semver bump (`1.1.1`, `1.2.0`, etc.).

---

## Cutting a draft

### Standard case — release matches get-physics-done

```bash
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd
```

Watch it:

```bash
RUN_ID=$(gh run list --repo psi-oss/opencode --workflow gpd-release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch $RUN_ID --repo psi-oss/opencode
```

### Desktop-only patch — keeps same sidecar, needs to reach existing installs

Pick the next desktop patch version explicitly so the auto-updater promotes it:

```bash
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd -f version=1.1.1
```

The release body will still say "Bundled sidecar: get-physics-done v1.1.0" (whatever the sidecar is at build time).

### Redrop — same sidecar, fresh-install only

Just re-run the workflow with no input. The collision handler picks the next `-N` suffix automatically. Auto-update will NOT promote this to existing installs (see caveat above); only fresh downloads from the site get it.

### Explicit version override (general case)

```bash
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd -f version=1.2.0
```

Use this whenever the desktop version is intentionally diverging from the sidecar.

### Reading from PyPI instead of GitHub

```bash
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd -f version_source=pypi
```

Useful when `main` in `get-physics-done` is ahead of what's published to PyPI and you want the release to match the sidecar users actually install.

---

## Monitoring a running release

Each build-desktop matrix job uploads directly to the draft as it completes, so you can inspect the draft mid-run:

```bash
# Which assets are live on the draft right now?
gh api repos/psi-oss/opencode/releases --jq \
  '.[] | select(.draft == true and (.tag_name | startswith("gpd-desktop-v"))) | {tag_name, assets: [.assets[].name]}'
```

Typical expected asset set on a fully successful build:

```
GPD_<ver>_aarch64.dmg              # mac-arm
GPD_<ver>_x64.dmg                  # mac-intel
GPD_aarch64.app.tar.gz(.sig)       # mac-arm updater bundle
GPD_x64.app.tar.gz(.sig)           # mac-intel updater bundle
GPD_<ver>_amd64.deb(.sig)          # linux deb
GPD-<ver>-1.x86_64.rpm(.sig)       # linux rpm
GPD_<ver>_x64-setup.exe(.sig)      # windows installer
latest.json                         # tauri updater manifest
```

---

## Publishing a draft

When the draft looks good, flip it to published:

```bash
# Newest gpd-desktop-v* draft (most common)
gh workflow run gpd-publish-draft.yml --repo psi-oss/opencode --ref gpd

# Specific tag
gh workflow run gpd-publish-draft.yml --repo psi-oss/opencode --ref gpd \
  -f tag=gpd-desktop-v1.1.0-1

# Don't mark as 'latest' (rare — for test/pre-release drops)
gh workflow run gpd-publish-draft.yml --repo psi-oss/opencode --ref gpd \
  -f mark_latest=false
```

The publish workflow refuses to act if:
- The chosen tag is already published (no-op with a warning).
- The tag has zero assets (fails — nothing to ship).

Publishing triggers `gpd-download-page.yml`, which regenerates `download.gpd.psi.inc`.

You can also publish via the GitHub UI (Releases → pencil icon on the draft → uncheck "Set as a pre-release" if relevant → "Publish release"). The workflow exists for scripted/headless use.

---

## Dealing with a contaminated release

If assets were accidentally uploaded to an already-published release (e.g., because the version wasn't bumped), the old assets are gone — GitHub does not keep prior asset content. Options:

1. Bump the sidecar version (merge a pyproject.toml bump to `psi-oss/get-physics-done@main`), then cut a fresh release. The version-collision guard will now resolve to the new clean tag.
2. If you want to keep the same base version, just re-run the release workflow — it will pick the next `-N` suffix and the contaminated assets on the original tag will stay as-is.
3. If the contamination is unacceptable, delete the bad release (GitHub UI → Releases → Delete) and its tag (`git push --delete psi-oss <tag>`), then re-run. This is destructive — use only if nobody has downloaded the bad assets.

---

## Running builds locally (no release)

To verify a Tauri build before pushing a release:

```bash
cd packages/desktop
# Populate sidecar stub so cargo check doesn't fail
mkdir -p src-tauri/gpd-sidecar-bundle && touch src-tauri/gpd-sidecar-bundle/.gitkeep
bun run tauri build --target aarch64-apple-darwin --config ./src-tauri/tauri.prod.conf.json
```

The built `.dmg` lands in `packages/desktop/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/`.

---

## Troubleshooting

**Workflow fails at `resolve-version` with "Exhausted -N suffixes"**
You have 100+ published releases against the same `get-physics-done` version. Bump the sidecar version; you should not be on a 101st desktop redrop of the same sidecar.

**Windows build times out / fails, but Mac+Linux are fine**
Let the release finish with only three platforms — the draft will have Mac + Linux assets. Decide whether to publish as-is (Windows users re-download when Windows builds later) or fix Windows first. To re-run only Windows, dispatch the workflow again; the draft already has the other platforms, and the collision handler will append.

**"Tag already published" keeps increasing the suffix**
Check `psi-oss/get-physics-done@main` — its `pyproject.toml` version is probably stale. Bump to the next real version and re-run.

**Download page didn't update after publishing**
Check `gpd-download-page.yml` in the Actions tab. It runs on `release:published` events only — if you unpublished and republished, or modified the release via the UI, the event may not have fired. Manually trigger it: `gh workflow run gpd-download-page.yml --repo psi-oss/opencode --ref gpd`.

---

## Related docs

- `docs/GPD_DISTRIBUTION.md` — end-to-end architecture (LiteLLM, sidecar, welcome screen)
- `docs/UPDATING.md` — how to rebase GPD onto a new upstream OpenCode tag before releasing
- `docs/GPD_DESKTOP_CHEATSHEET.md` — local paths, credentials, debug commands
