# GPD's LiteLLM image: stock upstream + our custom /gpd/log route.
#
# Rolling tag: each Railway redeploy rebuilds from the latest
# ghcr.io/berriai/litellm-database:main-stable. That's how LiteLLM
# upgrades flow through — you don't have to touch anything locally,
# just click "Redeploy" in Railway.
FROM ghcr.io/berriai/litellm:main-stable

# Our hook module — see infra/litellm/gpd_log/README.md for architecture.
COPY gpd_log /app/gpd_log

# Activate the hook. LiteLLM iterates this comma-separated list during
# worker startup (proxy_server.py:777-803, PR #22931) and calls each
# entry as `module:function`.
ENV LITELLM_WORKER_STARTUP_HOOKS=gpd_log.hook:register
ENV PYTHONPATH=/app
