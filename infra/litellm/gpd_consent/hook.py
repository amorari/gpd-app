"""LiteLLM worker-startup hook: register ConsentGateLogger.

Pointed to by `LITELLM_WORKER_STARTUP_HOOKS=...,gpd_consent.hook:register`
in the Dockerfile. Must run AFTER `gpd_tos.hook:register` so the audit-DB
pool is alive (the gate queries `gpd_tos_acceptance`).

Registration pattern: append a `CustomLogger` instance to `litellm.callbacks`
via `logging_callback_manager.add_litellm_callback`. The proxy iterates
this list on every LLM API call at
`litellm/proxy/utils.py:1419-1434`, invoking `async_pre_call_hook` for any
callback that OVERRIDES the base `CustomLogger.async_pre_call_hook` (line
1422-1424 equality check). ConsentGateLogger does override it, so it fires.

NOT monkey-patching `proxy_logging_obj.pre_call_hook`: that would wipe
LiteLLM's built-in rate-limiter and budget tracker, which register on the
same object. Callbacks-list pattern composes safely.

NOTE on revocation propagation lag: with a 300s in-process TTL cache per
worker, revocations take up to 5 minutes to take effect on any worker that
had cached the pre-revoke state. If legal requires immediate global
invalidation, swap `gpd_consent/cache.py` for a Redis pub/sub variant where
the revoke handler PUBLISHes an eviction and workers SUBSCRIBE.
"""
from __future__ import annotations

import logging


def register() -> None:
    logger = logging.getLogger("gpd_consent")

    # Local import: keep module-load cost zero on the off chance LiteLLM
    # re-orders hook invocation and calls us before it's fully initialised.
    import litellm

    from .consent_gate import ConsentGateLogger

    # Idempotent registration: re-registering the hook on worker reload
    # would add duplicate instances and double-query the DB per request.
    # Check by class, not identity, since instances are fresh each boot.
    for existing in litellm.callbacks:
        if isinstance(existing, ConsentGateLogger):
            logger.info("gpd_consent: gate already registered; skipping")
            return

    gate = ConsentGateLogger()
    litellm.logging_callback_manager.add_litellm_callback(gate)
    logger.info(
        "gpd_consent: registered ConsentGateLogger on litellm.callbacks "
        "(blocks LLM routes + /gpd/log for revoked users; 300s cache TTL)"
    )
