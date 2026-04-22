"""LiteLLM worker-startup hook: register POST /gpd/tos-accept.

Pointed to by `LITELLM_WORKER_STARTUP_HOOKS=...,gpd_tos.hook:register` in the
Dockerfile. Runs once per uvicorn worker during FastAPI lifespan startup
(proxy_server.py:777-803), before any request is served.

Mirrors infra/litellm/gpd_log/hook.py. Kept as a separate package so the
TOS flow has an isolated blast radius — a schema change or DB outage here
can't take down /gpd/log.
"""
from __future__ import annotations

import logging


def register() -> None:
    logger = logging.getLogger("gpd_tos")

    # Local imports — delay until the hook fires so a mis-set env var can't
    # crash the worker at module-load before we log anything useful.
    from litellm.proxy.proxy_server import app
    from litellm.proxy._types import LiteLLMRoutes

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

    logger.info("gpd_tos: registered POST /gpd/tos-accept")
