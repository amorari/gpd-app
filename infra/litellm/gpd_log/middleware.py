"""Reject outsized /gpd/log requests before the body hits memory.

LiteLLM's `user_api_key_auth` dependency calls `await request.body()`,
which for Starlette means the full body is drained into RAM before our
handler runs. A malicious valid-key client could POST 64MB bodies to
pressure the proxy. We gate on Content-Length in middleware so the
rejection happens before the ASGI receive loop reads the body.

Middleware registration at worker startup is safe because
`build_middleware_stack()` is called lazily on the first request, which
always happens after `LITELLM_WORKER_STARTUP_HOOKS` have run.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_BYTES = 64 * 1024 * 1024


class GpdLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path != "/gpd/log":
            return await call_next(request)

        cl_raw = request.headers.get("content-length")
        if cl_raw is None:
            return JSONResponse(
                {"error": "Content-Length header required"}, status_code=411
            )
        try:
            cl = int(cl_raw)
        except ValueError:
            return JSONResponse(
                {"error": "invalid Content-Length"}, status_code=400
            )
        if cl <= 0 or cl > MAX_BYTES:
            return JSONResponse(
                {"error": f"Content-Length must be 1..{MAX_BYTES}"}, status_code=413
            )

        return await call_next(request)
