"""LiteLLM worker-startup hook: register /gpd/log route + Content-Length middleware.

Pointed to by `LITELLM_WORKER_STARTUP_HOOKS=gpd_log.hook:register` in the
Dockerfile. Runs once per uvicorn worker during FastAPI lifespan startup
(proxy_server.py:777-803), before any request is served.
"""
from __future__ import annotations

import logging


def register() -> None:
    logger = logging.getLogger("gpd_log")

    # Local imports: these pull in Starlette / google.cloud.storage / redis,
    # which are already in the stock LiteLLM image but we delay the imports
    # until the hook fires to keep module-load cost zero on workers that
    # don't serve /gpd/log traffic (Starlette doesn't tree-shake like JS,
    # but this still avoids a crash if someone mis-sets env vars at boot).
    from litellm.proxy.proxy_server import app
    from litellm.proxy._types import LiteLLMRoutes

    from .handler import gpd_log

    # Tell LiteLLM's RouteChecks to treat /gpd/log as an LLM API route. Without
    # this, `non_proxy_admin_allowed_routes_check` falls into its "admin only"
    # branch for any route that isn't in openai_routes / anthropic_routes /
    # google_routes / mcp_routes / etc. (route_checks.py:264). With this, the
    # `is_llm_api_route(route="/gpd/log")` check returns True and non-admin
    # virtual keys can hit us normally. We don't set `cost_per_request` on
    # this route, so no LLM spend is charged — the per-key budget stays
    # reserved for real completions.
    if "/gpd/log" not in LiteLLMRoutes.openai_routes.value:
        LiteLLMRoutes.openai_routes.value.append("/gpd/log")

    app.add_api_route(
        "/gpd/log",
        gpd_log,
        methods=["POST"],
        tags=["gpd"],
        summary="GPD session log ingest (desktop → GCS via LiteLLM)",
    )

    logger.info("gpd_log: registered POST /gpd/log")
