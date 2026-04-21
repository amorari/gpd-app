# Sidecar HTTP route inventory

Read-only audit for Task G1.2. Enumerates every HTTP route handler across
`packages/opencode/src/server/**/*.ts`, with cross-reference against the GPD
GUI test suite (`packages/desktop/tests-gui/`). Source-file line numbers are
given as `file:line` of the handler's method call (`.get(`, `.post(`, etc.).

All routes sit behind these server-wide middlewares (see
`packages/opencode/src/server/middleware.ts` and `instance/middleware.ts`):

- `AuthMiddleware` — HTTP Basic auth when `OPENCODE_SERVER_PASSWORD` is set.
  GPD sidecar always sets it; tests read creds from the sidecar process env
  (`gpd_tests/drivers/opencode_http.discover_sidecar_credentials`).
- `CorsMiddleware` — permits `localhost`, `127.0.0.1`, `tauri://localhost`
  and `*.opencode.ai` origins.
- `CompressionMiddleware` — gzip, except for SSE (`/event`, `/global/event`)
  and streaming message routes.
- `WorkspaceRouterMiddleware` (instance routes only) — resolves the target
  project via `?directory=` query, `x-opencode-directory` header, or `cwd`.
  May forward the request to a remote workspace adapter when the session
  belongs to a non-local workspace.
- `ErrorMiddleware` — maps `NamedError` subclasses to 4xx/5xx JSON.

All auth-required endpoints use HTTP Basic. None use bearer tokens.

---

## Route groups

| Group | Source file | Routes |
|---|---|---|
| `/` (control-plane) | `packages/opencode/src/server/control/index.ts` | 4 |
| `/global` | `packages/opencode/src/server/instance/global.ts` | 6 |
| `/` (instance root) | `packages/opencode/src/server/instance/index.ts` | 9 |
| `/project` | `packages/opencode/src/server/instance/project.ts` | 5 |
| `/pty` | `packages/opencode/src/server/instance/pty.ts` | 6 |
| `/config` | `packages/opencode/src/server/instance/config.ts` | 3 |
| `/health` | `packages/opencode/src/server/instance/health.ts` | 2 |
| `/experimental` | `packages/opencode/src/server/instance/experimental.ts` | 11 |
| `/experimental/httpapi/question` | `packages/opencode/src/server/instance/httpapi/*.ts` | 2 (catch-all to Effect HttpApi) |
| `/experimental/workspace` | `packages/opencode/src/server/instance/workspace.ts` | 5 |
| `/session` | `packages/opencode/src/server/instance/session.ts` | 27 |
| `/permission` | `packages/opencode/src/server/instance/permission.ts` | 2 |
| `/question` | `packages/opencode/src/server/instance/question.ts` | 3 |
| `/provider` | `packages/opencode/src/server/instance/provider.ts` | 4 |
| `/` (file routes) | `packages/opencode/src/server/instance/file.ts` | 7 |
| `/event` | `packages/opencode/src/server/instance/event.ts` | 1 (SSE) |
| `/mcp` | `packages/opencode/src/server/instance/mcp.ts` | 8 |
| `/tui` | `packages/opencode/src/server/instance/tui.ts` | 13 |
| `/*` (UI proxy) | `packages/opencode/src/server/ui/index.ts` | 1 (catch-all) |
| **Total** | | **119** |

The `/experimental/httpapi/question` group is two `all()` Hono routes that
forward to an Effect `HttpApi` runtime. The full API (`list`, `reply`) is
defined in `@opencode-ai/server`'s `questionApi`, not in this repo. For
coverage purposes the group is counted as 2 endpoints.

---

## All routes

Streaming column: `no` = plain JSON, `SSE` = server-sent events, `JSON stream`
= newline-delimited JSON chunked over a Hono `stream()`, `WS` = WebSocket
upgrade, `catch-all` = static/proxy response.

Auth column: `basic` = HTTP Basic when `OPENCODE_SERVER_PASSWORD` is set;
`basic(ws)` = same, on WebSocket upgrade. No routes bypass basic auth beyond
CORS preflight.

Covered column: YES = the route is exercised by at least one test under
`packages/desktop/tests-gui/tests/` (live or MockTransport). NO = not
exercised; DRIVER-ONLY = wrapped by `gpd_tests/drivers/opencode_http.py` but
not used from any test; OPENAPI = produced for documentation only.

### Control plane (`/`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| PUT | `/auth/:providerID` | `control/index.ts:17` | `Auth.Info` (zod) | `true` | basic | no | NO |
| DELETE | `/auth/:providerID` | `control/index.ts:54` | — | `true` | basic | no | NO |
| GET | `/doc` | `control/index.ts:89` | — | OpenAPI JSON | basic | no | OPENAPI |
| POST | `/log` | `control/index.ts:111` | `{ service, level, message, extra? }` | `true` | basic | no | NO |

### Global (`/global`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/global/health` | `instance/global.ts:75` | — | `{ healthy, version }` | basic | no | YES — `tests/smoke/test_launch.py`, `tests/lifecycle/test_sidecar_respawn.py` |
| GET | `/global/event` | `instance/global.ts:96` | — | `GlobalEvent` SSE | basic | SSE | NO |
| GET | `/global/config` | `instance/global.ts:139` | — | `Config.Info` | basic | no | NO |
| PATCH | `/global/config` | `instance/global.ts:160` | `Config.Info` | `Config.Info` | basic | no | NO (referenced in `test_provider_switch.py` docstring as the target for a future write flow) |
| POST | `/global/dispose` | `instance/global.ts:185` | — | `true` | basic | no | NO |
| POST | `/global/upgrade` | `instance/global.ts:214` | `{ target?: string }` | `{ success, version? } \| { success: false, error }` | basic | no | NO |

### Instance root (`/`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| POST | `/instance/dispose` | `instance/index.ts:47` | — | `true` | basic | no | NO |
| GET | `/path` | `instance/index.ts:69` | — | `{ home, state, config, worktree, directory }` | basic | no | DRIVER-ONLY (`http.path_info()` defined but no test calls it) |
| GET | `/vcs` | `instance/index.ts:108` | — | `Vcs.Info` | basic | no | NO |
| GET | `/vcs/diff` | `instance/index.ts:139` | `?mode=...` | `Vcs.FileDiff[]` | basic | no | NO |
| GET | `/command` | `instance/index.ts:173` | — | `Command.Info[]` | basic | no | NO |
| GET | `/agent` | `instance/index.ts:194` | — | `Agent.Info[]` | basic | no | NO |
| GET | `/skill` | `instance/index.ts:217` | — | `Skill.Info[]` | basic | no | NO |
| GET | `/lsp` | `instance/index.ts:244` | — | `LSP.Status[]` | basic | no | NO |
| GET | `/formatter` | `instance/index.ts:266` | — | `Format.Status[]` | basic | no | NO |

### Project (`/project`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/project` | `instance/project.ts:16` | — | `Project.Info[]` | basic | no | NO |
| GET | `/project/current` | `instance/project.ts:39` | — | `Project.Info` | basic | no | NO |
| POST | `/project/git/init` | `instance/project.ts:60` | — | `Project.Info` | basic | no | NO |
| PATCH | `/project/:projectID` | `instance/project.ts:93` | `Project.UpdateInput` (minus `projectID`) | `Project.Info` | basic | no | NO |
| DELETE | `/project/:projectID` | `instance/project.ts:120` | — | `204` | basic | no | NO |

### PTY (`/pty`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/pty` | `instance/pty.ts:14` | — | `Pty.Info[]` | basic | no | NO |
| POST | `/pty` | `instance/pty.ts:43` | `Pty.CreateInput` | `Pty.Info` | basic | no | NO |
| GET | `/pty/:ptyID` | `instance/pty.ts:72` | — | `Pty.Info` | basic | no | NO |
| PUT | `/pty/:ptyID` | `instance/pty.ts:104` | `Pty.UpdateInput` | `Pty.Info` | basic | no | NO |
| DELETE | `/pty/:ptyID` | `instance/pty.ts:134` | — | `true` | basic | no | NO |
| GET | `/pty/:ptyID/connect` | `instance/pty.ts:163` | — (WS) | bi-directional | basic(ws) | WS | NO |

### Config (`/config`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/config` | `instance/config.ts:18` | — | `Config.Info` | basic | no | NO |
| PATCH | `/config` | `instance/config.ts:39` | `Config.Info` | `Config.Info` | basic | no | NO |
| GET | `/config/providers` | `instance/config.ts:64` | — | `{ providers, default }` | basic | no | YES — `tests/smoke/test_providers.py`, `tests/flows/test_provider_switch.py` |

### Health (`/health`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/health/doctor` | `instance/health.ts:475` | — | `DoctorResponse` | basic | no | NO |
| GET | `/health/presets` | `instance/health.ts:498` | — | `PresetsResponse` | basic | no | NO |

### Experimental (`/experimental`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/experimental/console` | `instance/experimental.ts:45` | — | `ConsoleState` | basic | no | NO |
| GET | `/experimental/console/orgs` | `instance/experimental.ts:79` | — | `{ orgs: ConsoleOrgOption[] }` | basic | no | NO |
| POST | `/experimental/console/switch` | `instance/experimental.ts:119` | `{ accountID, orgID }` | `true` | basic | no | NO |
| GET | `/experimental/tool/ids` | `instance/experimental.ts:148` | — | `string[]` | basic | no | NO |
| GET | `/experimental/tool` | `instance/experimental.ts:177` | `?provider&model` | `ToolListItem[]` | basic | no | NO |
| POST | `/experimental/worktree` | `instance/experimental.ts:239` | `Worktree.CreateInput?` | `Worktree.Info` | basic | no | NO |
| GET | `/experimental/worktree` | `instance/experimental.ts:264` | — | `string[]` | basic | no | NO |
| DELETE | `/experimental/worktree` | `instance/experimental.ts:286` | `Worktree.RemoveInput` | `true` | basic | no | NO |
| POST | `/experimental/worktree/reset` | `instance/experimental.ts:314` | `Worktree.ResetInput` | `true` | basic | no | NO |
| GET | `/experimental/session` | `instance/experimental.ts:339` | query filters | `Session.GlobalInfo[]` | basic | no | NO |
| GET | `/experimental/resource` | `instance/experimental.ts:398` | — | `Record<string, MCP.Resource>` | basic | no | NO |

### Experimental HTTP API — Questions (`/experimental/httpapi/question`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| ALL | `/experimental/httpapi/question` | `instance/httpapi/index.ts:6` / `question.ts:12` | delegated to `questionApi` Effect HttpApi | delegated | basic | no | NO |
| ALL | `/experimental/httpapi/question/*` | `instance/httpapi/index.ts:6` / `question.ts:12` | delegated | delegated | basic | no | NO |

### Experimental Workspace (`/experimental/workspace`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/experimental/workspace/adaptor` | `instance/workspace.ts:18` | — | `WorkspaceAdaptor[]` | basic | no | NO |
| POST | `/experimental/workspace` | `instance/workspace.ts:40` | `Workspace.create.schema` (minus `projectID`) | `Workspace.Info` | basic | no | NO |
| GET | `/experimental/workspace` | `instance/workspace.ts:73` | — | `Workspace.Info[]` | basic | no | NO |
| GET | `/experimental/workspace/status` | `instance/workspace.ts:93` | — | `Workspace.ConnectionStatus[]` | basic | no | NO |
| DELETE | `/experimental/workspace/:id` | `instance/workspace.ts:116` | — | `Workspace.Info?` | basic | no | NO |

### Session (`/session`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/session` | `instance/session.ts:34` | query filters | `Session.Info[]` | basic | no | YES — `tests/flows/test_new_session.py`, `tests/lifecycle/test_session_list_persistence.py`, `tests/surfaces/test_project.py` |
| GET | `/session/status` | `instance/session.ts:79` | — | `Record<id, SessionStatus.Info>` | basic | no | NO |
| GET | `/session/:sessionID` | `instance/session.ts:102` | — | `Session.Info` | basic | no | NO (not called directly; session object comes from list/create) |
| GET | `/session/:sessionID/children` | `instance/session.ts:133` | — | `Session.Info[]` | basic | no | NO |
| GET | `/session/:sessionID/todo` | `instance/session.ts:164` | — | `Todo.Info[]` | basic | no | NO |
| POST | `/session` | `instance/session.ts:194` | `Session.CreateInput` | `Session.Info` | basic | no | YES — multiple tests via `http.create_session()` |
| DELETE | `/session/:sessionID` | `instance/session.ts:219` | — | `true` | basic | no | YES — every flows test cleans up via `http.delete_session()` |
| PATCH | `/session/:sessionID` | `instance/session.ts:249` | `{ title?, permission?, time? }` | `Session.Info` | basic | no | NO |
| POST | `/session/:sessionID/init` | `instance/session.ts:313` | `{ modelID, providerID, messageID }` | `true` | basic | no | NO |
| POST | `/session/:sessionID/fork` | `instance/session.ts:363` | `Session.ForkInput` (minus `sessionID`) | `Session.Info` | basic | no | NO |
| POST | `/session/:sessionID/abort` | `instance/session.ts:394` | — | `true` | basic | no | YES — `tests/flows/test_abort_flow.py` |
| POST | `/session/:sessionID/share` | `instance/session.ts:423` | — | `Session.Info` | basic | no | NO |
| GET | `/session/:sessionID/diff` | `instance/session.ts:460` | `?messageID=...` | `Snapshot.FileDiff[]` | basic | no | NO |
| DELETE | `/session/:sessionID/share` | `instance/session.ts:503` | — | `Session.Info` | basic | no | NO |
| POST | `/session/:sessionID/summarize` | `instance/session.ts:540` | `{ providerID, modelID, auto? }` | `true` | basic | no | NO |
| GET | `/session/:sessionID/message` | `instance/session.ts:610` | `?limit&before` | `MessageWithParts[]` + `Link`/`X-Next-Cursor` headers | basic | no | YES — `http.messages(sid)` across multiple tests |
| GET | `/session/:sessionID/message/:messageID` | `instance/session.ts:696` | — | `{ info, parts }` | basic | no | NO |
| DELETE | `/session/:sessionID/message/:messageID` | `instance/session.ts:735` | — | `true` | basic | no | NO |
| DELETE | `/session/:sessionID/message/:messageID/part/:partID` | `instance/session.ts:777` | — | `true` | basic | no | NO |
| PATCH | `/session/:sessionID/message/:messageID/part/:partID` | `instance/session.ts:816` | `MessageV2.Part` | `MessageV2.Part` | basic | no | NO |
| POST | `/session/:sessionID/message` | `instance/session.ts:854` | `SessionPrompt.PromptInput` (minus `sessionID`) | single-chunk `MessageWithParts` | basic | JSON stream | YES — `http.send_message()` across most flow tests |
| POST | `/session/:sessionID/prompt_async` | `instance/session.ts:897` | `SessionPrompt.PromptInput` (minus `sessionID`) | `204` | basic | no | NO |
| POST | `/session/:sessionID/command` | `instance/session.ts:932` | `SessionPrompt.CommandInput` (minus `sessionID`) | `MessageWithParts` | basic | no | NO |
| POST | `/session/:sessionID/shell` | `instance/session.ts:969` | `SessionPrompt.ShellInput` (minus `sessionID`) | `MessageWithParts` | basic | no | NO |
| POST | `/session/:sessionID/revert` | `instance/session.ts:1001` | `SessionRevert.RevertInput` (minus `sessionID`) | `Session.Info` | basic | no | NO |
| POST | `/session/:sessionID/unrevert` | `instance/session.ts:1040` | — | `Session.Info` | basic | no | NO |
| POST | `/session/:sessionID/permissions/:permissionID` | `instance/session.ts:1070` | `{ response }` | `true` | basic | no | NO (DEPRECATED; superseded by `/permission/:id/reply`) |

### Permission (`/permission`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| POST | `/permission/:requestID/reply` | `instance/permission.ts:12` | `{ reply, message? }` | `true` | basic | no | NO |
| GET | `/permission` | `instance/permission.ts:52` | — | `Permission.Request[]` | basic | no | NO |

### Question (`/question`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/question` | `instance/question.ts:19` | — | `Question.Request[]` | basic | no | NO |
| POST | `/question/:requestID/reply` | `instance/question.ts:41` | `{ answers }` | `true` | basic | no | NO |
| POST | `/question/:requestID/reject` | `instance/question.ts:80` | — | `true` | basic | no | NO |

### Provider (`/provider`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/provider` | `instance/provider.ts:20` | — | `{ all, default, connected }` | basic | no | NO |
| GET | `/provider/auth` | `instance/provider.ts:77` | — | `Record<id, ProviderAuth.Method[]>` | basic | no | NO |
| POST | `/provider/:providerID/oauth/authorize` | `instance/provider.ts:98` | `{ method, inputs? }` | `ProviderAuth.Authorization?` | basic | no | NO |
| POST | `/provider/:providerID/oauth/callback` | `instance/provider.ts:144` | `{ method, code? }` | `true` | basic | no | NO |

### File / search (`/` — instance-scoped)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/find` | `instance/file.ts:18` | `?pattern=...` | `Ripgrep.Match.data[]` | basic | no | NO |
| GET | `/find/file` | `instance/file.ts:49` | `?query&dirs?&type?&limit?` | `string[]` | basic | no | NO |
| GET | `/find/symbol` | `instance/file.ts:95` | `?query` | `LSP.Symbol[]` (always `[]` as of G1.2) | basic | no | NO |
| GET | `/file` | `instance/file.ts:122` | `?path=...` | `File.Node[]` | basic | no | NO |
| GET | `/file/content` | `instance/file.ts:155` | `?path=...` | `File.Content` | basic | no | NO |
| GET | `/file/status` | `instance/file.ts:188` | — | `File.Info[]` | basic | no | NO |
| POST | `/file/edit-line` | `instance/file.ts:214` | `{ path, line, oldContent, newContent }` | `File.EditLineResult` or 409 `File.EditLineConflict` | basic | no | NO |

### Event stream (`/event`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/event` | `instance/event.ts:14` | — | `Event` SSE (BusEvent payloads + heartbeat) | basic | SSE | NO |

### MCP (`/mcp`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| GET | `/mcp` | `instance/mcp.ts:13` | — | `Record<id, MCP.Status>` | basic | no | NO |
| POST | `/mcp` | `instance/mcp.ts:34` | `{ name, config }` | `Record<id, MCP.Status>` | basic | no | NO |
| POST | `/mcp/:name/auth` | `instance/mcp.ts:65` | — | `{ authorizationUrl }` | basic | no | NO |
| POST | `/mcp/:name/auth/callback` | `instance/mcp.ts:106` | `{ code }` | `MCP.Status` | basic | no | NO |
| POST | `/mcp/:name/auth/authenticate` | `instance/mcp.ts:138` | — | `MCP.Status` | basic | no | NO |
| DELETE | `/mcp/:name/auth` | `instance/mcp.ts:175` | — | `{ success: true }` | basic | no | NO |
| POST | `/mcp/:name/connect` | `instance/mcp.ts:199` | — | `true` | basic | no | NO |
| POST | `/mcp/:name/disconnect` | `instance/mcp.ts:222` | — | `true` | basic | no | NO |

### TUI (`/tui`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| POST | `/tui/append-prompt` | `instance/tui.ts:81` | `TuiEvent.PromptAppend` | `true` | basic | no | NO |
| POST | `/tui/open-help` | `instance/tui.ts:105` | — | `true` | basic | no | NO |
| POST | `/tui/open-sessions` | `instance/tui.ts:129` | — | `true` | basic | no | NO |
| POST | `/tui/open-themes` | `instance/tui.ts:153` | — | `true` | basic | no | NO |
| POST | `/tui/open-models` | `instance/tui.ts:177` | — | `true` | basic | no | NO |
| POST | `/tui/submit-prompt` | `instance/tui.ts:201` | — | `true` | basic | no | NO |
| POST | `/tui/clear-prompt` | `instance/tui.ts:225` | — | `true` | basic | no | NO |
| POST | `/tui/execute-command` | `instance/tui.ts:249` | `{ command }` | `true` | basic | no | NO |
| POST | `/tui/show-toast` | `instance/tui.ts:291` | `TuiEvent.ToastShow` | `true` | basic | no | NO |
| POST | `/tui/publish` | `instance/tui.ts:314` | `{ type, properties }` (discriminated union) | `true` | basic | no | NO |
| POST | `/tui/select-session` | `instance/tui.ts:353` | `{ sessionID }` | `true` | basic | no | NO |
| GET | `/tui/control/next` | `instance/tui.ts:32` | — | `TuiRequest` | basic | no (long-poll via queue) | NO |
| POST | `/tui/control/response` | `instance/tui.ts:54` | `any` | `true` | basic | no | NO |

### UI catch-all (`/*`)

| Method | Path | Source (file:line) | Request body | Response body | Auth | Streaming? | Covered by test? |
|---|---|---|---|---|---|---|---|
| ALL | `/*` | `ui/index.ts:20` | — | static file or proxied `app.opencode.ai` HTML/JS/CSS with CSP header | basic | catch-all | NO |

---

## Uncovered routes (priority list)

Ranked by perceived user impact inside the GPD desktop experience. These feed
Phase G3 targets (route-group-cluster round-trip tests).

**Priority 1 — core session/message surface (user-visible regression risk)**
1. `POST /session/:sessionID/prompt_async` — fires the "send without waiting" path Phase G6.3's multi-turn with tool use will exercise.
2. `GET /session/:sessionID` — single-session fetch used by the deep-link flow; currently implicit only.
3. `PATCH /session/:sessionID` — session rename & archive; powers the sidebar rename surfaces.
4. `POST /session/:sessionID/fork` — session fork path feeds Phase G6.6 directly.
5. `GET /session/:sessionID/diff` — file-change diff per user message; feeds the "Changes" tab.
6. `DELETE /session/:sessionID/message/:messageID` and `.../part/:partID` — destructive message surgery.
7. `POST /session/:sessionID/revert` / `/unrevert` — revert-message surface on message hover.
8. `POST /session/:sessionID/command` and `/shell` — slash-command + shell-block flows.
9. `POST /session/:sessionID/summarize` — compaction button.
10. `POST /session/:sessionID/share` / `DELETE /session/:sessionID/share` — share button on titlebar.
11. `POST /session/:sessionID/init` — deprecated in docstring but still live.
12. `GET /session/status` — busy-state projector used for progress indicators.
13. `GET /session/:sessionID/children` — parent/child fork traversal.
14. `GET /session/:sessionID/todo` — todo panel.
15. `GET /session/:sessionID/message/:messageID` — single-message fetch used when deep-linking into a message.

**Priority 2 — config, providers, permissions, questions (dialog surfaces)**
16. `GET /config` / `PATCH /config` — settings dialog reads/writes. G3.2 target.
17. `GET /provider` / `GET /provider/auth` — `dialog-select-provider`, `dialog-connect-provider`. G3.2 target.
18. `POST /provider/:id/oauth/authorize` + `/callback` — OAuth connect flow.
19. `GET /permission`, `POST /permission/:id/reply` — permission prompt dialog. G3.5 target.
20. `GET /question`, `POST /question/:id/reply`, `POST /question/:id/reject` — question dialog. G3.5 target.
21. `GET /global/config`, `PATCH /global/config` — global settings persistence (feeds G6.5).
22. `PUT /auth/:providerID`, `DELETE /auth/:providerID` — API-key storage contract.
23. `POST /log` — used by the renderer for structured logging.

**Priority 3 — projects & workspaces**
24. `GET /project`, `GET /project/current`, `PATCH /project/:id`, `DELETE /project/:id`, `POST /project/git/init` — projects CRUD + git-init surface. G3.3 target.
25. `GET /experimental/workspace`, `POST /experimental/workspace`, `DELETE /experimental/workspace/:id`, `GET /experimental/workspace/status`, `GET /experimental/workspace/adaptor` — workspace list/create/remove.
26. `GET /experimental/session` — global (cross-project) session feed for the sidebar.
27. `POST /experimental/worktree`, `GET /experimental/worktree`, `DELETE /experimental/worktree`, `POST /experimental/worktree/reset` — sandbox worktrees. Opt-in marker.

**Priority 4 — health, VCS, tools, paths (read-only informational)**
28. `GET /health/doctor`, `GET /health/presets` — runtime readiness panel (G5.8 settings-gpd target).
29. `GET /path` — has driver stub, no test.
30. `GET /vcs`, `GET /vcs/diff` — VCS info + working-tree diff.
31. `GET /command`, `GET /agent`, `GET /skill` — picker content.
32. `GET /lsp`, `GET /formatter` — status-bar badges.
33. `GET /experimental/tool`, `GET /experimental/tool/ids` — tool list with params (used to show tool badges).
34. `GET /find`, `GET /find/file`, `GET /file`, `GET /file/content`, `GET /file/status`, `POST /file/edit-line` — file panel + inline file editor. G5.6 target.

**Priority 5 — MCP & experimental console**
35. `GET /mcp`, `POST /mcp`, `POST /mcp/:name/connect`, `POST /mcp/:name/disconnect` — MCP status & server add/toggle. G3.4 target.
36. `POST /mcp/:name/auth`, `POST /mcp/:name/auth/callback`, `POST /mcp/:name/auth/authenticate`, `DELETE /mcp/:name/auth` — MCP OAuth flows.
37. `GET /experimental/resource` — MCP resource list.
38. `GET /experimental/console`, `GET /experimental/console/orgs`, `POST /experimental/console/switch` — Console provider switcher.

**Priority 6 — streaming, WebSocket, TUI, dispose, upgrade (special care)**
39. `GET /event` (SSE) — server-sent bus event stream; requires streaming test helper.
40. `GET /global/event` (SSE) — global events incl. sync; requires streaming test helper.
41. `GET /pty/:ptyID/connect` (WS) — PTY attach; needs websockets test.
42. `GET /pty`, `POST /pty`, `GET /pty/:id`, `PUT /pty/:id`, `DELETE /pty/:id` — PTY CRUD.
43. `POST /session/:sessionID/permissions/:permissionID` — deprecated; needs one shape test to document the contract.
44. All 13 `/tui/*` routes — used by headless TUI runs; likely low priority for GPD.
45. `GET /tui/control/next`, `POST /tui/control/response` — TUI queue pump.
46. `POST /global/dispose`, `POST /instance/dispose` — destructive lifecycle; opt-in marker.
47. `POST /global/upgrade` — self-upgrade; destructive; opt-in marker.
48. `ALL /experimental/httpapi/question` + `/question/*` — delegated Effect `HttpApi`; document as external API.
49. `ALL /*` — UI static proxy; tested implicitly via app launch but no direct HTTP assertion.
50. `GET /doc` — OpenAPI JSON; tested implicitly by type-generation pipeline.

---

## Summary

- **Total routes:** 119 (108 unique Hono route declarations + 2 `ALL` catch-alls on the HttpApi mount + 1 root `/*` UI proxy, plus 8 routes that are pure controllers of the same underlying Effect handler pair for `/experimental/httpapi/question/*`).
- **Covered (live test hits the real endpoint over HTTP):** 7
  - `GET /global/health`
  - `GET /config/providers`
  - `GET /session`
  - `POST /session`
  - `DELETE /session/:sessionID`
  - `POST /session/:sessionID/abort`
  - `GET /session/:sessionID/message`
  - `POST /session/:sessionID/message` (streamed JSON chunk)
- **Driver-wrapped but no test call:** 1 (`GET /path`).
- **Uncovered:** 111 (≈ 93%).
- **Streaming routes:** 4 — `GET /event` (SSE), `GET /global/event` (SSE), `GET /pty/:ptyID/connect` (WS), `POST /session/:sessionID/message` (newline-delimited JSON chunk via `stream()`). None of the SSE or WS routes currently has a dedicated test; the streaming `POST message` is covered at the one-chunk level only. Phase G3.1 and G6.3 need explicit multi-chunk SSE/WS helpers.
- **Auth-bypass routes:** 0. Every endpoint honors `AuthMiddleware` when `OPENCODE_SERVER_PASSWORD` is set, which GPD always sets. CORS preflight (`OPTIONS`) is the only exemption.
- **Destructive routes that must be opt-in in tests:** `POST /global/dispose`, `POST /instance/dispose`, `POST /global/upgrade`, `POST /session/:sessionID/summarize` (model call), `POST /session/:sessionID/init` (model call), `POST /experimental/worktree/reset`, `DELETE /experimental/worktree`, `DELETE /project/:projectID` cascade.

### Cross-reference: Python driver methods vs. routes

`gpd_tests/drivers/opencode_http.HTTPClient` exposes 10 method wrappers:
`health`, `sessions`, `providers`, `path_info`, `create_session`,
`send_message`, `messages`, `abort`, `delete_session`, plus the
internal `_get`/`_post`/`_delete`. That covers 8 of the 119 routes. All
other Phase G3 tests must either extend this driver or use the raw
`self._client` in the style of `docs/superpowers/plans/2026-04-20-phase2-surfaces-plan.md:728`
(`http._client.post("/project", json=...)`). A natural next step
alongside G3 is to broaden the driver itself to cover the Priority 1
session routes.
