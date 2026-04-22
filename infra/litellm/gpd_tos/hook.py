"""LiteLLM worker-startup hook: register routes + run audit DB migrations.

Pointed to by `LITELLM_WORKER_STARTUP_HOOKS=...,gpd_tos.hook:register` in
the Dockerfile. LiteLLM awaits coroutine hooks (proxy_server.py:777-803),
so `register()` itself is async and `await`s the migration step — no more
fire-and-forget race that could 503 the first POST after a cold deploy.

Mirrors infra/litellm/gpd_log/hook.py for the route-registration + enum-
monkey-patch parts, but owns migration state in its own asyncpg-managed
audit database (GPD_AUDIT_DATABASE_URL).
"""
from __future__ import annotations

import logging


async def register() -> None:
    logger = logging.getLogger("gpd_tos")

    # Local imports — delay until the hook fires so a mis-set env var can't
    # crash the worker at module-load before we log anything useful.
    from litellm.proxy.proxy_server import app
    from litellm.proxy._types import LiteLLMRoutes

    from . import migrate
    from .handler import gpd_tos_accept, gpd_tos_revoke

    # LiteLLM's `non_proxy_admin_allowed_routes_check` only permits routes
    # it recognises as LLM-API routes for non-admin virtual keys. Without
    # this append, every virtual-key call to /gpd/tos-accept or
    # /gpd/tos-revoke would 403. No `cost_per_request`, so no LLM spend is
    # charged.
    for path in ("/gpd/tos-accept", "/gpd/tos-revoke"):
        if path not in LiteLLMRoutes.openai_routes.value:
            LiteLLMRoutes.openai_routes.value.append(path)

    app.add_api_route(
        "/gpd/tos-accept",
        gpd_tos_accept,
        methods=["POST"],
        tags=["gpd"],
        summary="GPD Terms-of-Service acceptance (desktop → audit Postgres)",
    )
    app.add_api_route(
        "/gpd/tos-revoke",
        gpd_tos_revoke,
        methods=["POST"],
        tags=["gpd"],
        summary="GPD Terms-of-Service revocation + account-erase kickoff",
    )

    # BLOCK worker startup on migration completion. We'd rather crash at
    # boot with a visible DB error than silently serve 503s to the first
    # cohort of users.
    #
    # The previous fire-and-forget design (`asyncio.ensure_future(...)`)
    # could race the first POST against DDL completion; the pool in db.py
    # does NOT serialise against this task, so INSERTs could land before
    # CREATE TABLE committed. Awaiting here is the right fix.
    await migrate.apply_migrations()

    logger.info("gpd_tos: registered POST /gpd/tos-accept + /gpd/tos-revoke")
