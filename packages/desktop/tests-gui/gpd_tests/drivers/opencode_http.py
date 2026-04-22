"""HTTP client for opencode-cli sidecar API."""
from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Literal

import httpx


LogLevel = Literal["debug", "info", "error", "warn"]


class HTTPClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        transport: httpx.BaseTransport | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        # Stash the caller's transport + timeout so rediscover() can rebuild
        # the underlying httpx.Client without losing them (e.g. MockTransport
        # in unit tests, or the default transport the fixture built with).
        self._transport = transport
        self._timeout_s = timeout_s
        self._client = httpx.Client(
            base_url=base_url,
            auth=(username, password),
            transport=transport,
            timeout=timeout_s,
        )

    def close(self) -> None:
        self._client.close()

    def rediscover(self, pid: int) -> None:
        """Re-point this client at a freshly-respawned sidecar.

        After a GPD quit+launch cycle (or a SIGKILL-then-respawn) the
        opencode-cli sidecar reappears on a new TCP port with new
        OPENCODE_SERVER_USERNAME/PASSWORD. The old httpx.Client is still
        pinned to the dead sidecar — calls fail with connection-refused or
        401. Call this with the new sidecar pid to rebuild the underlying
        client in place; the caller's transport + timeout are preserved.
        """
        port = discover_sidecar_port(pid=pid, timeout_s=15.0)
        user, pw = discover_sidecar_credentials(pid)
        self._client.close()
        self._client = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            auth=(user, pw),
            transport=self._transport,
            timeout=self._timeout_s,
        )

    def __enter__(self) -> "HTTPClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str) -> Any:
        r = self._client.get(path)
        r.raise_for_status()
        return r.json()

    def health(self) -> dict[str, Any]:
        return self._get("/global/health")

    def sessions(self, *, directory: str | None = None) -> list[dict[str, Any]]:
        if directory is not None:
            r = self._client.get("/session", params={"directory": directory})
            r.raise_for_status()
            return r.json()
        return self._get("/session")

    def providers(self) -> dict[str, Any]:
        return self._get("/config/providers")

    def path_info(self) -> dict[str, Any]:
        return self._get("/path")

    def _post(self, path: str, json: dict | list | None = None, params: dict | None = None) -> Any:
        r = self._client.post(path, json=json, params=params)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        ct = r.headers.get("content-type", "")
        if "json" in ct or r.text.startswith(("{", "[")):
            return r.json()
        return r.text

    def _delete(self, path: str) -> Any:
        r = self._client.delete(path)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    def _patch(self, path: str, json: dict | list | None = None) -> Any:
        r = self._client.patch(path, json=json)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return None
        ct = r.headers.get("content-type", "")
        if "json" in ct or r.text.startswith(("{", "[")):
            return r.json()
        return r.text

    # ------------------------------------------------------------------
    # /config and /provider wrappers
    # ------------------------------------------------------------------

    def get_config(self) -> dict[str, Any]:
        """GET /config — current project Config.Info."""
        return self._get("/config")

    def patch_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH /config — replace the whole Config.Info.

        The server's Config.Info schema is strict (Zod discriminated fields),
        so callers generally pass a GET-then-modify round-trip, not a sparse
        patch. The request body is validated by Zod; invalid shapes return 400.
        """
        return self._patch("/config", json=patch)

    def list_providers_full(self) -> dict[str, Any]:
        """GET /provider — deeper view than /config/providers.

        Returns ``{ all: Provider.Info[], default: Record<id, modelID>,
        connected: string[] }``.
        """
        return self._get("/provider")

    def provider_models(self, provider_id: str) -> dict[str, Any]:
        """Return the ``models`` dict for a single provider.

        Derived from ``list_providers_full()`` — there is no dedicated server
        endpoint for per-provider model listing; callers pick by ``id``.
        Raises ``KeyError`` if the provider is not in the response.
        """
        data = self.list_providers_full()
        for p in data.get("all", []):
            if p.get("id") == provider_id:
                return p.get("models", {})
        raise KeyError(f"provider {provider_id!r} not in /provider response")

    def enable_provider(self, provider_id: str) -> dict[str, Any]:
        """Ensure ``provider_id`` is enabled by updating Config.disabled_providers.

        Implementation: GET /config, remove ``provider_id`` from
        ``disabled_providers`` (and if ``enabled_providers`` is set, add it
        there), PATCH /config with the result. Returns the new config.
        There is no dedicated server endpoint for this toggle — the sidecar
        stores provider enable/disable state inside Config.Info.
        """
        cfg = self.get_config()
        disabled = list(cfg.get("disabled_providers", []) or [])
        if provider_id in disabled:
            disabled = [p for p in disabled if p != provider_id]
        cfg["disabled_providers"] = disabled
        enabled = cfg.get("enabled_providers")
        if isinstance(enabled, list) and provider_id not in enabled:
            cfg["enabled_providers"] = [*enabled, provider_id]
        return self.patch_config(cfg)

    def disable_provider(self, provider_id: str) -> dict[str, Any]:
        """Ensure ``provider_id`` is disabled by updating Config.disabled_providers.

        Adds ``provider_id`` to ``disabled_providers``; if ``enabled_providers``
        is an explicit allowlist that includes this provider, also remove it
        there to make the disable take effect. Returns the new config.
        """
        cfg = self.get_config()
        disabled = list(cfg.get("disabled_providers", []) or [])
        if provider_id not in disabled:
            disabled.append(provider_id)
        cfg["disabled_providers"] = disabled
        enabled = cfg.get("enabled_providers")
        if isinstance(enabled, list) and provider_id in enabled:
            cfg["enabled_providers"] = [p for p in enabled if p != provider_id]
        return self.patch_config(cfg)

    def create_session(
        self,
        *,
        directory: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if parent_id is not None:
            body["parentID"] = parent_id
        params = {"directory": directory} if directory is not None else None
        return self._post("/session", json=body, params=params)

    def send_message(
        self,
        session_id: str,
        *,
        parts: list[dict[str, Any]],
        model_id: str | None = None,
        provider_id: str | None = None,
        agent: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"parts": parts}
        if (model_id is None) != (provider_id is None):
            raise ValueError("model_id and provider_id must be provided together")
        if model_id is not None and provider_id is not None:
            body["model"] = {"modelID": model_id, "providerID": provider_id}
        if agent is not None:
            body["agent"] = agent
        return self._post(f"/session/{session_id}/message", json=body)

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        return self._get(f"/session/{session_id}/message")

    def abort(self, session_id: str) -> Any:
        return self._post(f"/session/{session_id}/abort")

    def delete_session(self, session_id: str) -> bool:
        r = self._delete(f"/session/{session_id}")
        return r is None or bool(r)

    # ------------------------------------------------------------------
    # Additional /session/* wrappers (Phase G3.1)
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> dict[str, Any]:
        """GET /session/:sessionID — single-session fetch.

        Returns the ``Session.Info`` dict. Raises ``httpx.HTTPStatusError``
        with a 404 response if the session does not exist.
        """
        return self._get(f"/session/{session_id}")

    def session_children(self, session_id: str) -> list[dict[str, Any]]:
        """GET /session/:sessionID/children — child sessions forked from parent."""
        return self._get(f"/session/{session_id}/children")

    def session_status(self) -> dict[str, Any]:
        """GET /session/status — busy-state projector, id → status info."""
        return self._get("/session/status")

    def patch_session(self, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """PATCH /session/:sessionID — update title / permission / time.archived.

        Server accepts ``{ title?, permission?, time?: { archived? } }``.
        Returns the updated ``Session.Info``.
        """
        return self._patch(f"/session/{session_id}", json=patch)

    def fork_session(
        self,
        session_id: str,
        *,
        after_message_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /session/:sessionID/fork — create a child session from this point.

        ``after_message_id`` maps to the server-side ``messageID`` field in
        ``Session.ForkInput`` (camelCase on the wire). When omitted, the
        server forks from the session's latest message.
        """
        body: dict[str, Any] = {}
        if after_message_id is not None:
            body["messageID"] = after_message_id
        return self._post(f"/session/{session_id}/fork", json=body)

    def get_session_diff(
        self,
        session_id: str,
        *,
        message_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /session/:sessionID/diff — file changes from a specific message.

        The server requires ``?messageID=...`` in practice; the driver does
        not inject a default so callers pick the message explicitly. When
        ``message_id`` is omitted, the query param is not sent (and the
        server will return 400).
        """
        if message_id is None:
            return self._get(f"/session/{session_id}/diff")
        r = self._client.get(
            f"/session/{session_id}/diff",
            params={"messageID": message_id},
        )
        r.raise_for_status()
        return r.json()

    def get_message(self, session_id: str, message_id: str) -> dict[str, Any]:
        """GET /session/:sessionID/message/:messageID — single message + parts."""
        return self._get(f"/session/{session_id}/message/{message_id}")

    def delete_message(self, session_id: str, message_id: str) -> bool:
        """DELETE /session/:sessionID/message/:messageID — destructive.

        Returns ``True`` on success (server returns ``true`` or ``204``).
        """
        r = self._delete(f"/session/{session_id}/message/{message_id}")
        return r is None or bool(r)

    def revert_message(
        self,
        session_id: str,
        *,
        message_id: str,
        part_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /session/:sessionID/revert — revert a message (and optional part).

        Maps to ``SessionRevert.RevertInput`` (minus sessionID). Returns the
        updated ``Session.Info``.
        """
        body: dict[str, Any] = {"messageID": message_id}
        if part_id is not None:
            body["partID"] = part_id
        return self._post(f"/session/{session_id}/revert", json=body)

    def unrevert_session(self, session_id: str) -> dict[str, Any]:
        """POST /session/:sessionID/unrevert — restore all reverted messages."""
        return self._post(f"/session/{session_id}/unrevert")

    def prompt_async(
        self,
        session_id: str,
        *,
        parts: list[dict[str, Any]],
        model_id: str | None = None,
        provider_id: str | None = None,
        agent: str | None = None,
    ) -> None:
        """POST /session/:sessionID/prompt_async — fire-and-forget prompt.

        Server returns 204 and continues processing on the server side. The
        wrapper mirrors :meth:`send_message` request shape (nested ``model``
        object). Completion is observed via the /event SSE stream, not this
        call's return value.
        """
        body: dict[str, Any] = {"parts": parts}
        if (model_id is None) != (provider_id is None):
            raise ValueError("model_id and provider_id must be provided together")
        if model_id is not None and provider_id is not None:
            body["model"] = {"modelID": model_id, "providerID": provider_id}
        if agent is not None:
            body["agent"] = agent
        # _post already maps 204 / empty-body to None.
        self._post(f"/session/{session_id}/prompt_async", json=body)
        return None

    # ------------------------------------------------------------------
    # /project wrappers (Phase G3.3)
    # ------------------------------------------------------------------

    def list_projects(self) -> list[dict[str, Any]]:
        """GET /project — all projects OpenCode has been opened against."""
        return self._get("/project")

    def current_project(self) -> dict[str, Any]:
        """GET /project/current — the Project.Info this sidecar is bound to."""
        return self._get("/project/current")

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Return the Project.Info whose ``id`` matches, or ``None``.

        The sidecar has no ``GET /project/:id`` route; we filter
        :meth:`list_projects` client-side.
        """
        for p in self.list_projects():
            if p.get("id") == project_id:
                return p
        return None

    def update_project(self, project_id: str, **patch: Any) -> dict[str, Any]:
        """PATCH /project/:projectID — update name/icon/commands.

        ``projectID`` travels in the URL only; the server's Zod schema
        strips it from the body, so callers pass it positionally.
        """
        # Drop None-valued kwargs so we never send `{"name": null}` and
        # accidentally clear a field on a sparse patch.
        body = {k: v for k, v in patch.items() if v is not None}
        return self._patch(f"/project/{project_id}", json=body)

    def delete_project(self, project_id: str) -> bool:
        """DELETE /project/:projectID — cascades to sessions + workspaces.

        Returns ``True`` on 204 (no body) or when the server returns a truthy
        body. Raises ``httpx.HTTPStatusError`` on 404 etc.
        """
        r = self._delete(f"/project/{project_id}")
        return r is None or bool(r)

    def project_git_init(self) -> dict[str, Any]:
        """POST /project/git/init — git-init the current project worktree."""
        return self._post("/project/git/init")

    # ------------------------------------------------------------------
    # /experimental/workspace wrappers (Phase G3.3)
    # ------------------------------------------------------------------

    def list_workspaces(self) -> list[dict[str, Any]]:
        """GET /experimental/workspace — workspaces for the current project."""
        return self._get("/experimental/workspace")

    def create_workspace(
        self,
        *,
        type: str,
        branch: str | None = None,
        extra: Any = None,
        id: str | None = None,
        directory: str | None = None,
    ) -> dict[str, Any]:
        """POST /experimental/workspace — create a workspace in the current project.

        Body is ``Workspace.CreateInput`` minus ``projectID`` (the server
        attaches the current project id). ``type`` must match a registered
        adaptor name (e.g. ``"worktree"``); invalid types return 400.

        Pass ``directory`` to route the request to a specific project instance
        (required when the sidecar's default project is not a git repo).
        """
        body: dict[str, Any] = {"type": type}
        if id is not None:
            body["id"] = id
        # branch / extra may be explicitly None to mean "no branch / no extra".
        # Always include them; the server's Zod schema expects nullable fields.
        body["branch"] = branch
        body["extra"] = extra
        params = {"directory": directory} if directory is not None else None
        return self._post("/experimental/workspace", json=body, params=params)

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        """Return the Workspace.Info whose ``id`` matches, or ``None``.

        The sidecar has no per-id GET route; we filter :meth:`list_workspaces`
        client-side.
        """
        for w in self.list_workspaces():
            if w.get("id") == workspace_id:
                return w
        return None

    def delete_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        """DELETE /experimental/workspace/:id — returns the removed info or None."""
        return self._delete(f"/experimental/workspace/{workspace_id}")

    def workspace_status(self) -> list[dict[str, Any]]:
        """GET /experimental/workspace/status — connection status per workspace."""
        return self._get("/experimental/workspace/status")

    def workspace_adaptors(self) -> list[dict[str, Any]]:
        """GET /experimental/workspace/adaptor — available adaptor types."""
        return self._get("/experimental/workspace/adaptor")

    # ------------------------------------------------------------------
    # /mcp — Model Context Protocol server registry + lifecycle (G3.4)
    # server: packages/opencode/src/server/instance/mcp.ts
    # ------------------------------------------------------------------

    def list_mcp_servers(self) -> dict[str, Any]:
        """GET /mcp → ``Record<name, MCP.Status>``. Shape-only; non-mutating.

        Server source: ``instance/mcp.ts:13``.
        """
        return self._get("/mcp")

    def invoke_mcp_tool(
        self,
        server: str,
        tool: str,
        args: dict[str, Any],
    ) -> Any:
        """POST /mcp/:name/tool/:tool — invoke a tool on an MCP server.

        Note: as of G3.4 the sidecar does NOT implement this route. The
        wrapper still targets a deterministic path + well-formed body so that
        (a) callers see an actionable 404 rather than an opaque crash and
        (b) if the server adds the endpoint later, the contract is already in
        place. MUTATES; tests must gate this call on
        ``PYTEST_OPTIN_MUTATE_SYSTEM``.
        """
        body = {"arguments": args if args is not None else {}}
        return self._post(f"/mcp/{server}/tool/{tool}", json=body)

    def connect_mcp_server(self, name: str) -> Any:
        """POST /mcp/:name/connect — connect an MCP server. MUTATES.

        Server source: ``instance/mcp.ts:199``.
        """
        return self._post(f"/mcp/{name}/connect")

    def disconnect_mcp_server(self, name: str) -> Any:
        """POST /mcp/:name/disconnect — disconnect an MCP server. MUTATES.

        Server source: ``instance/mcp.ts:222``.
        """
        return self._post(f"/mcp/{name}/disconnect")

    # ------------------------------------------------------------------
    # /experimental — flags / knobs, MCP resources, tool catalog (G3.4)
    # server: packages/opencode/src/server/instance/experimental.ts
    # ------------------------------------------------------------------

    def get_experimental_flags(self) -> dict[str, Any]:
        """GET /experimental/console → ``ConsoleState``. Shape-only.

        The sidecar does not expose a generic ``/experimental/flags`` route;
        the Console state is the nearest cluster of user-visible toggles
        (active account + org, managed provider IDs, switchable-org count).

        Server source: ``instance/experimental.ts:45``.
        """
        return self._get("/experimental/console")

    def set_experimental_flag(
        self,
        key: str,
        value: dict[str, Any],
    ) -> Any:
        """Narrow setter mapping a ``(key, value)`` pair to the correct write.

        Currently the only supported key is ``"console"``, which maps to
        POST /experimental/console/switch with a body of
        ``{"accountID": ..., "orgID": ...}``. Unknown keys and malformed
        payloads raise ``ValueError`` BEFORE any HTTP call is made so tests
        don't mask typos as generic 400s.

        MUTATES; tests must gate this call on
        ``PYTEST_OPTIN_MUTATE_SYSTEM``. Server source:
        ``instance/experimental.ts:119``.
        """
        if key == "console":
            required = {"accountID", "orgID"}
            missing = required - set(value or {})
            if missing:
                raise ValueError(
                    f"set_experimental_flag('console', ...) missing fields: "
                    f"{sorted(missing)}"
                )
            body = {
                "accountID": value["accountID"],
                "orgID": value["orgID"],
            }
            return self._post("/experimental/console/switch", json=body)
        raise ValueError(
            f"unknown experimental flag {key!r}; supported: ['console']"
        )

    def list_experimental_tool_ids(self) -> list[str]:
        """GET /experimental/tool/ids → ``string[]``. Shape-only.

        Server source: ``instance/experimental.ts:148``.
        """
        return self._get("/experimental/tool/ids")

    def list_experimental_resources(self) -> dict[str, Any]:
        """GET /experimental/resource → ``Record<uri, MCP.Resource>``. Shape-only.

        Server source: ``instance/experimental.ts:398``.
        """
        return self._get("/experimental/resource")

    # ------------------------------------------------------------------
    # /permission — server: packages/opencode/src/server/instance/permission.ts
    # ------------------------------------------------------------------

    # Permission.Reply zod enum (see packages/opencode/src/permission/index.ts):
    #   z.enum(["once", "always", "reject"])
    # Guarding client-side turns a typo into an immediate ValueError instead
    # of a 400 round-trip.
    _PERMISSION_REPLY_VALUES = frozenset({"once", "always", "reject"})

    def permissions(self) -> list[dict[str, Any]]:
        """GET /permission — list pending Permission.Request objects.

        GPD ships with ``permission: allow`` so this list is typically empty
        in the default configuration; the route still exists and is exercised
        here for shape-contract coverage.
        """
        return self._get("/permission")

    def permission_reply(
        self,
        request_id: str,
        *,
        reply: str,
        message: str | None = None,
    ) -> bool:
        """POST /permission/{requestID}/reply.

        ``reply`` must be one of ``'once' | 'always' | 'reject'`` (matches the
        server's ``Permission.Reply`` enum). ``message`` is an optional
        free-form explanation (typically paired with ``reject``).
        Server returns literal ``true`` on success.
        """
        if reply not in self._PERMISSION_REPLY_VALUES:
            raise ValueError(
                f"invalid permission reply {reply!r}; "
                f"expected one of {sorted(self._PERMISSION_REPLY_VALUES)}"
            )
        body: dict[str, Any] = {"reply": reply}
        if message is not None:
            body["message"] = message
        result = self._post(f"/permission/{request_id}/reply", json=body)
        return bool(result)

    # ------------------------------------------------------------------
    # /question — server: packages/opencode/src/server/instance/question.ts
    # ------------------------------------------------------------------

    def questions(self) -> list[dict[str, Any]]:
        """GET /question — list pending Question.Request objects."""
        return self._get("/question")

    def question_reply(
        self,
        request_id: str,
        *,
        answers: list[list[str]],
    ) -> bool:
        """POST /question/{requestID}/reply.

        ``answers`` is a list-of-lists: one entry per question, each a list of
        selected option labels. The server validator is
        ``z.object({ answers: Question.Answer.zod.array() })`` where
        ``Question.Answer`` is ``string[]``, so the shape is ``string[][]``.
        Passing a flat ``list[str]`` is a common mistake and is rejected
        client-side before the round-trip.
        """
        if not isinstance(answers, list):
            raise TypeError(
                f"answers must be list[list[str]], got {type(answers).__name__}"
            )
        for i, group in enumerate(answers):
            if not isinstance(group, list):
                raise ValueError(
                    f"answers[{i}] must be list[str] (selected labels), "
                    f"got {type(group).__name__}. Wrap single answers as "
                    "[['label']], not ['label']."
                )
            for j, label in enumerate(group):
                if not isinstance(label, str):
                    raise ValueError(
                        f"answers[{i}][{j}] must be str, got "
                        f"{type(label).__name__}"
                    )
        result = self._post(
            f"/question/{request_id}/reply", json={"answers": answers}
        )
        return bool(result)

    def question_reject(self, request_id: str) -> bool:
        """POST /question/{requestID}/reject — no body; server returns ``true``."""
        result = self._post(f"/question/{request_id}/reject")
        return bool(result)

    # ------------------------------------------------------------------
    # /global/* wrappers (beyond health)
    # ------------------------------------------------------------------

    def global_config_get(self) -> dict[str, Any]:
        """GET /global/config — read the merged global Config.Info."""
        return self._get("/global/config")

    def global_config_patch(self, config: dict[str, Any]) -> dict[str, Any]:
        """PATCH /global/config — merge the given partial config and return
        the updated Config.Info."""
        r = self._client.patch("/global/config", json=config)
        r.raise_for_status()
        return r.json()

    def global_dispose(self) -> bool:
        """POST /global/dispose — tear down all instances. DESTRUCTIVE."""
        r = self._post("/global/dispose")
        return r is None or bool(r)

    def global_upgrade(self, *, target: str | None = None) -> dict[str, Any]:
        """POST /global/upgrade — self-upgrade opencode. DESTRUCTIVE.

        target: version string. If omitted, server resolves to latest.
        """
        body: dict[str, Any] = {}
        if target is not None:
            body["target"] = target
        return self._post("/global/upgrade", json=body)

    @contextmanager
    def global_event_stream(
        self, *, timeout_s: float = 30.0
    ) -> Iterator[Iterator[dict[str, Any]]]:
        """GET /global/event — subscribe to the global SSE stream.

        Usage:

            with client.global_event_stream() as stream:
                for event in stream:
                    ...
                    if done:
                        break

        The context manager guarantees the underlying streaming Response is
        closed on exit (even after a partial read). Each yielded event is
        the decoded JSON payload of one `data:` SSE frame. Comment lines
        (starting with `:`) and blank separators are skipped.
        """
        # Use a longer per-request read timeout for streaming. Connect
        # timeout still obeys the client-wide default. Auth is applied
        # automatically from the Client's bound auth.
        req = self._client.build_request("GET", "/global/event")
        r = self._client.send(req, stream=True)
        r.raise_for_status()
        try:
            yield _iter_sse_events(r)
        finally:
            # close() is idempotent and safe even if iteration never
            # started; it releases the TCP connection back to the pool.
            r.close()

    # ------------------------------------------------------------------
    # /control/* wrappers
    # ------------------------------------------------------------------

    def control_openapi_doc(self) -> dict[str, Any]:
        """GET /doc — return the OpenAPI 3.1 spec as a dict."""
        return self._get("/doc")

    def control_log(
        self,
        *,
        service: str,
        level: LogLevel,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> bool:
        """POST /log — write a log entry into the sidecar's log stream.

        Raises ValueError if `level` is not one of debug/info/error/warn;
        the server would 400 but surfacing locally is friendlier.
        """
        if level not in ("debug", "info", "error", "warn"):
            raise ValueError(
                f"invalid log level {level!r}; "
                "must be one of debug/info/error/warn"
            )
        body: dict[str, Any] = {
            "service": service,
            "level": level,
            "message": message,
        }
        if extra is not None:
            body["extra"] = extra
        r = self._post("/log", json=body)
        return r is None or bool(r)

    def control_auth_set(self, provider_id: str, info: dict[str, Any]) -> bool:
        """PUT /auth/:providerID — set credentials for a provider. DESTRUCTIVE.

        Mutates ~/.local/share/opencode/auth.json.
        """
        r = self._client.put(f"/auth/{provider_id}", json=info)
        r.raise_for_status()
        if r.status_code == 204 or not r.content:
            return True
        return bool(r.json())

    def control_auth_remove(self, provider_id: str) -> bool:
        """DELETE /auth/:providerID — remove stored credentials. DESTRUCTIVE."""
        r = self._delete(f"/auth/{provider_id}")
        return r is None or bool(r)


def _iter_sse_events(resp: httpx.Response) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from an SSE stream.

    Handles:
      - `data: <json>` frames (the only kind opencode emits)
      - `: comment` lines (skipped)
      - blank separator lines (skipped)
      - multi-line `data:` accumulation per the SSE spec (joined with \n)

    A frame is dispatched when an empty line follows its data lines. If the
    stream closes mid-frame the partial frame is discarded silently — this
    matches EventSource semantics and is what we want for clean shutdown.
    """
    buf: list[str] = []
    for line in resp.iter_lines():
        # httpx.iter_lines yields str with the terminator already stripped.
        if line == "":
            if buf:
                payload = "\n".join(buf)
                buf = []
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    # Not a JSON frame — ignore rather than crashing the
                    # consumer. opencode only sends JSON `data:` frames
                    # today, but tolerating stray bytes keeps us robust.
                    continue
            continue
        if line.startswith(":"):
            # SSE comment — used for keep-alive. Skip.
            continue
        if line.startswith("data:"):
            # Strip the field name and one optional leading space.
            value = line[5:]
            if value.startswith(" "):
                value = value[1:]
            buf.append(value)
            continue
        # Other field names (event:, id:, retry:) are not used by opencode
        # so we ignore them without accumulating.


def discover_sidecar_port(
    *, pid: int | None = None, timeout_s: float = 15.0
) -> int:
    """Return the TCP port opencode-cli listens on.

    Retries up to `timeout_s`. If a `pid` was passed, re-validate it each
    attempt: a crashed-then-respawned sidecar has a new PID, so we must
    rediscover instead of hammering a dead one.
    """
    import time

    deadline = time.monotonic() + timeout_s
    last_err: str = ""
    probe_pid = pid
    while time.monotonic() < deadline:
        if probe_pid is not None and not _pid_alive(probe_pid):
            probe_pid = None  # force rediscovery on next iteration
        try:
            return _probe_port_once(pid=probe_pid)
        except RuntimeError as e:
            last_err = str(e)
            probe_pid = None  # rediscover PID in case sidecar respawned
            time.sleep(0.25)
    raise RuntimeError(f"no listening port after {timeout_s}s: {last_err}")


def _pid_alive(pid: int) -> bool:
    try:
        os_kill = subprocess.run(
            ["kill", "-0", str(pid)],
            capture_output=True,
            check=False,
        )
        return os_kill.returncode == 0
    except Exception:
        return False


def _probe_port_once(*, pid: int | None) -> int:
    if pid is None:
        out = subprocess.run(
            ["pgrep", "-f", "opencode-cli.*serve"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
        if not pids:
            raise RuntimeError("opencode-cli not running")
        pid = pids[0]
    # -a ANDs the filters; without it lsof returns every listening socket on
    # the system, so the first 127.0.0.1:... line may belong to a completely
    # unrelated process.
    out = subprocess.run(
        ["lsof", "-a", "-P", "-n", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in out.stdout.splitlines():
        if "127.0.0.1:" in line:
            port = line.rsplit("127.0.0.1:", 1)[1].split(" ", 1)[0]
            port = port.split("(")[0].strip()
            return int(port)
    raise RuntimeError(f"no listening port found for pid {pid}")


def discover_sidecar_credentials(pid: int) -> tuple[str, str]:
    """Read OPENCODE_SERVER_USERNAME/PASSWORD from the sidecar process env.

    On macOS, uses ``ps -E -p <pid>`` which prints the environment variables
    for same-user processes.

    On Linux, reads ``/proc/{pid}/environ`` directly (a null-delimited list of
    ``KEY=VALUE`` pairs), which is always available for same-user processes
    without any extra privileges.
    """
    if sys.platform == "darwin":
        out = subprocess.run(
            ["ps", "-E", "-ww", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        env_text = out.stdout
    else:
        # Linux (and other POSIX systems): /proc/{pid}/environ is a
        # null-delimited list of KEY=VALUE pairs.
        environ_path = f"/proc/{pid}/environ"
        try:
            raw = open(environ_path, "rb").read()
        except PermissionError as exc:
            raise RuntimeError(
                f"cannot read {environ_path} on {sys.platform}: "
                f"permission denied (are you the same user as the sidecar?)"
            ) from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"cannot read {environ_path} on {sys.platform}: "
                f"process {pid} not found or /proc not mounted"
            ) from exc
        # Replace null bytes with spaces so _extract_env can scan for
        # " KEY=VALUE" tokens with the existing space-delimited logic.
        env_text = " " + raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")

    user = _extract_env(env_text, "OPENCODE_SERVER_USERNAME") or "opencode"
    pw = _extract_env(env_text, "OPENCODE_SERVER_PASSWORD")
    if not pw:
        raise RuntimeError(
            f"OPENCODE_SERVER_PASSWORD not found in sidecar env "
            f"(pid={pid}, platform={sys.platform})"
        )
    return user, pw


def _extract_env(blob: str, key: str) -> str | None:
    token = f" {key}="
    idx = blob.find(token)
    if idx == -1:
        return None
    start = idx + len(token)
    end = blob.find(" ", start)
    if end == -1:
        end = len(blob)
    return blob[start:end]
