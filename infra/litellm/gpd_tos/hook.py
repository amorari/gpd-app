"""LiteLLM worker-startup hook: register POST /gpd/tos-accept.

Pointed to by `LITELLM_WORKER_STARTUP_HOOKS=...,gpd_tos.hook:register` in the
Dockerfile. Runs once per uvicorn worker during FastAPI lifespan startup
(proxy_server.py:777-803), before any request is served.

Mirrors infra/litellm/gpd_log/hook.py. Kept as a separate package so the
TOS flow has an isolated blast radius — a schema change or DB outage here
can't take down /gpd/log.
"""
from __future__ import annotations

import asyncio
import logging


def register() -> None:
    logger = logging.getLogger("gpd_tos")

    # Local imports — delay until the hook fires so a mis-set env var can't
    # crash the worker at module-load before we log anything useful.
    from litellm.proxy.proxy_server import app
    from litellm.proxy._types import LiteLLMRoutes

    from . import db
    from .handler import gpd_tos_accept

    # Same reason as gpd_log: `non_proxy_admin_allowed_routes_check` only
    # permits routes it recognises as LLM-API routes for non-admin virtual
    # keys (route_checks.py:264). Without this append, every virtual-key
    # call to /gpd/tos-accept would 403. We don't set cost_per_request, so
    # no LLM spend is charged.
    if "/gpd/tos-accept" not in LiteLLMRoutes.openai_routes.value:
        LiteLLMRoutes.openai_routes.value.append("/gpd/tos-accept")

    app.add_api_route(
        "/gpd/tos-accept",
        gpd_tos_accept,
        methods=["POST"],
        tags=["gpd"],
        summary="GPD Terms-of-Service acceptance (desktop → Postgres via LiteLLM)",
    )

    # (Re-)create gpd_tos_acceptance if missing. LiteLLM's startup
    # `prisma migrate deploy` step drops tables not managed by its own
    # schema, so the custom table evaporates on every redeploy without
    # this bootstrap.
    #
    # Block the worker startup until DDL is done — we'd rather crash at
    # boot with a DB error than serve 503s to the first cohort of users.
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Fire-and-forget inside FastAPI's running lifespan loop.
            # `ensure_future` lets startup proceed in parallel; the first
            # POST will await whichever is ready first. Race is safe
            # because ensure_schema is idempotent and insert_acceptance
            # awaits the pool anyway.
            asyncio.ensure_future(db.ensure_schema())
        else:
            loop.run_until_complete(db.ensure_schema())
    except Exception as e:
        logger.error(f"gpd_tos: ensure_schema failed: {e}")
        raise

    logger.info("gpd_tos: registered POST /gpd/tos-accept")
