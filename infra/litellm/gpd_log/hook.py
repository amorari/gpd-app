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

    from .handler import gpd_log
    from .middleware import GpdLogMiddleware

    app.add_middleware(GpdLogMiddleware)
    app.add_api_route(
        "/gpd/log",
        gpd_log,
        methods=["POST"],
        tags=["gpd"],
        summary="GPD session log ingest (desktop → GCS via LiteLLM)",
    )

    logger.info("gpd_log: registered POST /gpd/log + Content-Length middleware")
