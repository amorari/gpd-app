# GPD Distribution System — Complete Reference

**Last updated:** April 16, 2026
**Status:** Production — versioned to match `get-physics-done`. Latest shipped desktop build: `gpd-desktop-v1.1.0-1` (first desktop redrop against sidecar `1.1.0`).

---

## Architecture

```
Professor's machine (macOS / Windows / Linux)
    │
    │  GPD Desktop App (rebranded OpenCode Tauri app)
    │  ├── OpenCode CLI sidecar (bundled, GPD-branded)
    │  ├── GPD PyInstaller sidecar (bundled, 8 MCP servers)
    │  ├── Provider config via OPENCODE_CONFIG_CONTENT env var
    │  └── Welcome screen → professor pastes LiteLLM virtual key
    │
    │  Authorization: Bearer <virtual-key>
    ▼
LiteLLM Proxy (Railway)
    │  URL: https://litellm-production-46bb.up.railway.app
    │  Validates virtual key, enforces $2K/month budget
    │  Filters /v1/models per key, translates tool calls
    ▼
Upstream Providers (PSI's API keys — never exposed)
    ├── Anthropic (Claude Opus/Sonnet 4.6, Haiku 4.5)
    ├── OpenAI (GPT-5.4/mini/nano/pro, GPT-5.3-codex, GPT-4.1/mini, o4-mini)
    └── Google (Gemini 3.1 Pro, 3 Flash, 3.1 Flash-Lite)
```

---

## Repositories

| Repo | Branch | What |
|------|--------|------|
| `psi-oss/opencode` | `gpd` (default) | OpenCode fork with GPD branding, welcome screen, provider config |
| `psi-oss/opencode` | `gh-pages` | Download page at `download.gpd.psi.inc` |
| `psi-oss/get-physics-done` | `main` | GPD Python package — MCP servers, commands, agents. **Version source for desktop app.** |

---

## Versioning

The GPD desktop app version follows the `get-physics-done` package version. They are the same product — the desktop app is just the delivery mechanism.

| Source | Version | What it means |
|--------|---------|---------------|
| `psi-oss/get-physics-done` pyproject.toml | `1.1.0` | Latest in repo (may be unreleased) |
| PyPI `get-physics-done` | `1.1.0` | Latest published Python release |
| npm `get-physics-done` | `1.1.0` | Latest published Node release |

The CI release workflow auto-detects the version. Default source: **GitHub** (reads `pyproject.toml` from `psi-oss/get-physics-done` main branch). Can be changed to PyPI or npm via the workflow dispatch dropdown.

**Triggering a release:**
```bash
# Auto-detect version from GitHub (default) — creates/updates a DRAFT release
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd

# Publish the draft when ready
gh workflow run gpd-publish-draft.yml --repo psi-oss/opencode --ref gpd
```

All releases start as drafts; assets upload per-platform as each matrix job finishes. If the resolved tag collides with an already-published release, the version auto-increments as `<base>-1`, `<base>-2`, … so redrops against the same sidecar version don't overwrite published assets.

Full release playbook, including publishing, redrops, contaminated releases, and per-platform diagnostics: **see `docs/RELEASING.md`**.

When `github` is selected, the CI also installs `get-physics-done` directly from the GitHub repo main branch (not PyPI), so the sidecar binary contains the latest code.

---

## LiteLLM Proxy (Railway)

### Access
- **URL:** `https://litellm-production-46bb.up.railway.app`
- **Admin UI:** `https://litellm-production-46bb.up.railway.app/ui`
- **Admin login:** `UI_USERNAME` / `UI_PASSWORD` (set in Railway env vars)
- **Master key:** `LITELLM_MASTER_KEY` (in Railway env vars — starts with `sk-`)
- **Railway project:** `https://railway.com/project/0ddad766-1ee1-44ed-95c2-f8f7d9cb5515`

### Models (14 total)

| Provider | Model | LiteLLM model_name |
|----------|-------|--------------------|
| Anthropic | Claude Opus 4.6 | `claude-opus-4-6` |
| Anthropic | Claude Sonnet 4.6 | `claude-sonnet-4-6` |
| Anthropic | Claude Haiku 4.5 | `claude-haiku-4-5` |
| OpenAI | GPT-5.4 | `gpt-5.4` |
| OpenAI | GPT-5.4 mini | `gpt-5.4-mini` |
| OpenAI | GPT-5.4 nano | `gpt-5.4-nano` |
| OpenAI | GPT-5.4 Pro | `gpt-5.4-pro` |
| OpenAI | GPT-5.3 Codex | `gpt-5.3-codex` |
| OpenAI | GPT-4.1 | `gpt-4.1` |
| OpenAI | GPT-4.1 mini | `gpt-4.1-mini` |
| OpenAI | o4-mini | `o4-mini` |
| Google | Gemini 3.1 Pro | `gemini-3.1-pro-preview` |
| Google | Gemini 3 Flash | `gemini-3-flash-preview` |
| Google | Gemini 3.1 Flash-Lite | `gemini-3.1-flash-lite-preview` |

### Key Management

**Generate a key for a professor:**
```bash
curl -X POST 'https://litellm-production-46bb.up.railway.app/key/generate' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "prof-smith",
    "key_alias": "prof-smith",
    "models": ["all-models"],
    "max_budget": 2000,
    "budget_duration": "30d"
  }'
```

**Revoke a key:**
```bash
curl -X POST 'https://litellm-production-46bb.up.railway.app/key/delete' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{"keys": ["sk-abc123..."]}'
```

**Check usage:**
```bash
curl 'https://litellm-production-46bb.up.railway.app/user/info?user_id=prof-smith' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

### Adding a New Model

```bash
curl -X POST 'https://litellm-production-46bb.up.railway.app/model/new' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model_name": "new-model-name",
    "litellm_params": {
      "model": "provider/model-id",
      "api_key": "os.environ/PROVIDER_API_KEY"
    },
    "model_info": {
      "access_groups": ["all-models"]
    }
  }'
```

Then add the model to `gpd_setup.rs:provider_config_json()` in the fork so the desktop app knows about it.

### Railway Environment Variables

| Variable | Purpose |
|----------|---------|
| `LITELLM_MASTER_KEY` | Admin auth for key management |
| `LITELLM_SALT_KEY` | DB encryption (immutable after first boot) |
| `UI_USERNAME` / `UI_PASSWORD` | Admin UI login |
| `ANTHROPIC_API_KEY` | Upstream Anthropic key |
| `OPENAI_API_KEY` | Upstream OpenAI key |
| `GOOGLE_API_KEY` | Upstream Google key |
| `STORE_MODEL_IN_DB` | `True` — manage models via API |
| `HOST` | `0.0.0.0` — required for Railway networking |
| `PORT` | `4000` |
| `LITELLM_NUM_RETRIES` | `3` |
| `LITELLM_REQUEST_TIMEOUT` | `120` |

---

## OpenCode Fork — What We Changed

### Branding (applies on every rebase)

| File | Change |
|------|--------|
| `packages/app/index.html` | Title → "GPD — Physics Research Workspace" |
| `packages/app/src/i18n/en.ts` | ~20 strings: "OpenCode" → "GPD", "Build anything" → "Get Physics Done" |
| `packages/app/src/i18n/*.ts` (16 files) | All non-English locales: "OpenCode" → "GPD" |
| `packages/desktop/index.html` | Same title |
| `packages/desktop/src/i18n/en.ts` | 6 desktop strings |
| `packages/desktop/src-tauri/tauri.conf.json` | productName "GPD Dev", identifier "inc.psi.gpd.dev", deep-link "gpd://" |
| `packages/desktop/src-tauri/tauri.beta.conf.json` | productName "GPD Beta" |
| `packages/desktop/src-tauri/tauri.prod.conf.json` | productName "GPD", disabled updater signing |
| `packages/ui/src/components/logo.tsx` | PSI Ψ SVG (Mark, Splash, Logo) |
| `packages/ui/src/components/favicon.tsx` | apple-mobile-web-app-title "GPD" |
| `packages/opencode/src/cli/logo.ts` | CLI block art "GPD" |
| `packages/opencode/src/cli/cmd/tui/app.tsx` | Terminal title "GPD" |
| `packages/desktop/src-tauri/icons/` | 159 icon files replaced with PSI Ψ |

### Welcome Screen + Auth Gate (GPD-specific code)

| File | What |
|------|------|
| `packages/app/src/components/welcome-screen.tsx` | New — PSI logo, key input, "Get Started" button |
| `packages/app/src/app.tsx` | `SetupGate` with localStorage gate, `__GPD_RESET_KEY__()` |
| `packages/app/src/pages/layout.tsx` | "Change GPD API Key" command palette entry |
| `packages/app/src/pages/layout/sidebar-shell.tsx` | Pencil icon button for key reset |

### Tauri First-Run Orchestration (GPD-specific code)

| File | What |
|------|------|
| `packages/desktop/src-tauri/src/gpd_setup.rs` | First-run detection, sidecar install, MCP merge, `provider_config_json()` |
| `packages/desktop/src-tauri/src/lib.rs` | Passes `OPENCODE_CONFIG_DIR` + `OPENCODE_CONFIG_CONTENT` to sidecar |
| `packages/desktop/src-tauri/src/cli.rs` | `extra_serve_env` parameter |
| `packages/desktop/src-tauri/src/server.rs` | `extra_env` parameter passthrough |
| `packages/desktop/src-tauri/tauri.conf.json` | `resources: ["gpd-sidecar-bundle/"]` |

### CI/CD

| File | What |
|------|------|
| `.github/workflows/gpd-release.yml` | Builds CLI + desktop (4 platforms) + GPD sidecar, creates release, updates download page |

### Scripts (in `scripts/gpd/`)

| File | What |
|------|------|
| `inject-litellm-provider.py` | Merges LiteLLM provider config into opencode.json (used by terminal install) |
| `sidecar_main.py` | PyInstaller entry point with `mcp-serve` and `list-servers` subcommands |
| `generate_pyinstaller_imports.py` | Auto-generates `--hidden-import` flags from `_BUILTIN_SERVERS` |

---

## How the Welcome Screen Works

1. `SetupGate` in `app.tsx` checks `localStorage.getItem("gpd.key.saved")`
2. If `null` → show `WelcomeScreen` component
3. Professor pastes LiteLLM virtual key → clicks "Get Started"
4. `auth.set({ providerID: "gpd", auth: { type: "api", key } })` writes to auth.json
5. `localStorage.setItem("gpd.key.saved", "true")` prevents future welcome screens
6. `global.dispose()` triggers re-bootstrap → provider connects → app loads

**Why it works:** The GPD provider definition is injected via `OPENCODE_CONFIG_CONTENT` env var when the OpenCode sidecar starts. This means `"gpd"` exists in OpenCode's provider database BEFORE the professor enters their key. When `auth.set` stores the key, the provider system finds the matching database entry and connects it.

**Resetting the key:** Command palette (Cmd+K) → "Change GPD API Key", or pencil icon in sidebar. Both clear `localStorage("gpd.key.saved")` and reload.

**Important: Tauri WebView localStorage** persists in `~/Library/WebKit/inc.psi.gpd*/` (macOS). Deleting the `.app` does NOT clear it. Full wipe requires:
```bash
rm -rf ~/Library/WebKit/inc.psi.gpd*
rm -rf ~/Library/Application\ Support/inc.psi.gpd*
rm -rf ~/Library/Caches/inc.psi.gpd*
rm -rf ~/Library/Preferences/inc.psi.gpd*
rm -rf ~/.local/share/opencode/
rm -rf ~/.config/gpd/
```

---

## How to Rebase on a New OpenCode Release

Our changes are a single squashed commit on top of an upstream tag. Rebasing onto a new upstream version:

```bash
# 1. Fetch latest upstream tags
git fetch upstream --tags

# 2. Note the current base tag (e.g., v1.4.6) and the new target (e.g., v1.5.0)
# 3. Rebase our single commit onto the new tag
git checkout gpd
git rebase --onto v1.5.0 v1.4.6 gpd

# 4. Resolve any conflicts (usually just i18n/en.ts — new strings added upstream)

# 5. Force push to psi-oss
git push psi-oss gpd --force

# 6. Trigger release
gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd
# Version auto-detected from get-physics-done. Override with: -f version=X.Y.Z
```

**Why this works:** We have ONE commit. `git rebase --onto <new-base> <old-base>` replays that single commit on the new tag. Conflicts are limited to files we actually modify.

**Highest conflict risk:** `packages/app/src/i18n/en.ts` (new strings added constantly). Our changes are isolated string replacements, so conflicts are usually trivial.

**After rebase:**
1. Run `cargo check` in `packages/desktop/src-tauri/` to verify Rust compiles
2. Trigger release: `gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd -f version=<VERSION>`
3. Download page auto-updates

**Branch structure:**
- `gpd` (default) — our single squashed commit on top of an upstream tag. This is where we work.
- `dev` — tracks upstream's dev branch. We don't work here. Can sync via GitHub's "Sync fork" button.
- `gh-pages` — download page. Independent of the above.

---

## How to Add a New Model

1. **Add to LiteLLM** (immediate, no rebuild needed):
```bash
curl -X POST 'https://litellm-production-46bb.up.railway.app/model/new' \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model_name": "new-model", "litellm_params": {"model": "provider/model-id", "api_key": "os.environ/PROVIDER_KEY"}, "model_info": {"access_groups": ["all-models"]}}'
```

2. **Add to the fork's provider config** (requires rebuild):
   - Edit `packages/desktop/src-tauri/src/gpd_setup.rs` → `provider_config_json()`
   - Add the model to the JSON string with name, capabilities, and limits
   - Commit, push, trigger release

3. **Update `inject-litellm-provider.py`** (for terminal install path):
   - Add the model to the `PROVIDER_CONFIG` dict

---

## How to Add a New Provider (e.g., xAI, DeepSeek)

1. **Add upstream API key to Railway:**
   ```bash
   railway variables --set "XAI_API_KEY=xai-..."
   ```

2. **Add models to LiteLLM** (via API, see above)

3. **Update `gpd_setup.rs:provider_config_json()`** with the new models

4. **Rebuild and release**

---

## How to Generate Keys in Bulk

```bash
#!/bin/bash
LITELLM_URL="https://litellm-production-46bb.up.railway.app"

while IFS=, read -r user_id email; do
  key=$(curl -s -X POST "$LITELLM_URL/key/generate" \
    -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"user_id\": \"$user_id\",
      \"key_alias\": \"$user_id\",
      \"models\": [\"all-models\"],
      \"max_budget\": 2000,
      \"budget_duration\": \"30d\"
    }" | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")
  echo "$user_id,$email,$key"
done < professors.csv > keys.csv
```

---

## Future: CLI Install Script

**Not yet built.** This would be the terminal-based alternative to the desktop app, hosted at `download.gpd.psi.inc/install.sh`.

```bash
curl -fsSL https://download.gpd.psi.inc/install.sh | bash
```

### What the script does

1. **Install our OpenCode fork binary** (not stock OpenCode)
   - Download the GPD-branded CLI binary from our GitHub releases
   - Same binary that's inside the desktop app (`opencode-cli` sidecar)
   - Detect OS/arch (macOS ARM/Intel, Linux x64/ARM)
   - Install to `~/.gpd/bin/opencode`
   - This is a fork of OpenCode's install script (`https://opencode.ai/install`) with the download URL changed to `psi-oss/opencode` releases

2. **Check for Python 3.11+**
   - Required for GPD's MCP servers
   - If missing, tell the user to install it (`brew install python3` / `apt install python3`)
   - Professors are physicists — they almost certainly have Python

3. **Install GPD Python package**
   - `pip3 install --user get-physics-done`
   - Provides 8 MCP servers + `gpd` CLI

4. **Run `gpd install opencode --global`**
   - Places 69 commands, 26 agents, MCP config in `~/.config/gpd/`
   - Uses `OPENCODE_CONFIG_DIR=~/.config/gpd`

5. **Inject LiteLLM provider config**
   - Run `scripts/gpd/inject-litellm-provider.py --config-dir ~/.config/gpd/`
   - Adds the GPD provider with all 14 models to opencode.json
   - Sets `enabled_providers: ["gpd"]` and default model

6. **Prompt for LiteLLM key**
   - `read -sp "Enter your GPD API key: " api_key`
   - Write to `~/.local/share/opencode/auth.json` with 0600 permissions

7. **Install `gpd` wrapper to PATH**
   ```bash
   mkdir -p ~/.gpd/bin
   cat > ~/.gpd/bin/gpd << 'EOF'
   #!/bin/bash
   export OPENCODE_CONFIG_DIR="$HOME/.config/gpd"
   export OPENCODE_CONFIG_CONTENT='<provider JSON>'
   if [[ "$1" == "--cli" ]]; then
     shift
     exec "$HOME/.gpd/bin/opencode" "$@"
   else
     exec "$HOME/.gpd/bin/opencode" web "$@"
   fi
   EOF
   chmod +x ~/.gpd/bin/gpd
   echo 'export PATH="$HOME/.gpd/bin:$PATH"' >> ~/.zshrc  # or detect shell
   ```

8. **Print success**
   ```
   ✓ OpenCode (GPD) installed
   ✓ GPD tools installed (8 MCP servers, 69 commands)
   ✓ API key saved
   ✓ 'gpd' command added to PATH

   Run 'gpd' to open the web UI.
   Run 'gpd --cli' for the terminal TUI.
   ```

### Implementation notes

- Fork OpenCode's install script at `https://opencode.ai/install` (~200 lines of bash)
- Change the download URL from `github.com/anomalyco/opencode/releases` to `github.com/psi-oss/opencode/releases`
- Change branding strings ("OpenCode" → "GPD")
- Add the GPD-specific steps (3-7) after the binary install
- Host at `download.gpd.psi.inc/install.sh` (add to gh-pages branch)
- The `OPENCODE_CONFIG_CONTENT` env var in the wrapper ensures the GPD provider is always available (same fix as the desktop app)
- The wrapper script calls our fork's binary, not stock `opencode`

### CLI vs Desktop comparison

| Feature | Desktop App | CLI Install |
|---------|------------|-------------|
| Terminal required | No | Yes |
| Python required | No (PyInstaller sidecar) | Yes |
| Welcome screen | GUI | Terminal prompt |
| `gpd` command | N/A (launches app) | `gpd` opens web, `gpd --cli` opens TUI |
| Auto-update | Not yet | Manual (`gpd update` or re-run install) |
| MCP servers | Via bundled sidecar | Via Python (`pip install get-physics-done`) |
| Gatekeeper/SmartScreen | Needs `xattr -cr` | N/A (no app bundle) |

---

## Professor Onboarding Flow

1. Admin generates a virtual key for the professor
2. Send email: "Download GPD from download.gpd.psi.inc. Your API key: sk-abc123..."
3. Professor downloads DMG, installs, runs `/usr/bin/xattr -cr /Applications/GPD.app`
4. Opens GPD → welcome screen → pastes key → clicks "Get Started"
5. GPD opens with model picker showing Claude/GPT/Gemini
6. Professor types `/gpd-new-project` to start

---

## Ongoing Maintenance

| Task | Frequency | How |
|------|-----------|-----|
| Generate keys for new professors | As needed | `curl` to `/key/generate` |
| Revoke keys | As needed | `curl` to `/key/delete` |
| Monitor spend | Weekly | LiteLLM admin UI |
| Add new models | When providers release | LiteLLM API + `gpd_setup.rs` update |
| Rebase on new OpenCode | When upstream releases a new tag | See `docs/UPDATING.md` |
| Update LiteLLM | Monthly | Railway redeploy |
| Release new GPD desktop version | When `get-physics-done` updates | `gh workflow run gpd-release.yml --repo psi-oss/opencode --ref gpd` (auto-detects version) |

---

## Known Limitations

- **macOS Gatekeeper:** Unsigned app requires `xattr -cr` before first open. Include in email instructions.
- **Windows SmartScreen:** Similar unsigned warning. "Run Anyway" needed.
- **No auto-update:** Professors must manually download new versions. Tauri updater disabled (no signing key).
- **MCP servers require PyInstaller sidecar:** If the sidecar isn't bundled (empty placeholder), MCP servers won't work. CI builds include it.
- **Code signing:** Not implemented. Would require Apple Developer Program ($99/year) + EV cert for Windows ($200-400/year).

---

## File Locations on Professor's Machine

| Path | What |
|------|------|
| `/Applications/GPD.app` | The app |
| `~/.config/gpd/` | OpenCode config dir (MCP servers, commands, agents) |
| `~/.local/share/opencode/auth.json` | API key storage |
| `~/.local/share/opencode/opencode*.db` | Session database |
| `~/Library/WebKit/inc.psi.gpd/` | Tauri WebView data (localStorage) |
| `~/Library/Application Support/inc.psi.gpd/` | Tauri app settings |

---

## Troubleshooting

**"GPD is damaged and can't be opened"**
→ `xattr -cr /Applications/GPD.app`

**Welcome screen doesn't appear / stuck**
→ Wipe: `rm -rf ~/Library/WebKit/inc.psi.gpd* ~/.local/share/opencode/ ~/.config/gpd/`

**API calls fail after entering key**
→ Verify the key works: `curl -s https://litellm-production-46bb.up.railway.app/v1/models -H "Authorization: Bearer <key>"`

**Wrong key entered**
→ Command palette (Cmd+K) → "Change GPD API Key"

**Models not showing**
→ The `OPENCODE_CONFIG_CONTENT` env var defines available models. Check `gpd_setup.rs:provider_config_json()`.

**MCP servers not connected**
→ Check if GPD sidecar bundle exists in the app: `GPD.app/Contents/Resources/gpd-sidecar-bundle/gpd-sidecar`
