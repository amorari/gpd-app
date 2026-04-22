# GPD's LiteLLM image: stock upstream + our custom /gpd/log route.
#
# Pinned to a specific release (not rolling main-stable) because our
# hook.py monkey-patches internal LiteLLM state:
#   LiteLLMRoutes.openai_routes.value.append("/gpd/log")
# A rename of that field in any upstream release would silently break
# /gpd/log. The smoke-test GH workflow catches ABI breakage whenever we
# bump the pin.
#
# Upgrade procedure:
#   1. Check https://github.com/BerriAI/litellm/security/advisories for
#      CVEs against the current pin.
#   2. Pick the newest tag that patches all advisories (see LOGGING.md).
#   3. Bump the FROM line.
#   4. Locally: `railway up infra/litellm --path-as-root --service litellm`
#      and re-run the smoke test (GH Actions `litellm-smoke-test.yml`).
#   5. Commit.
#
# Current pin: v1.83.7-stable (patches GHSA-v4p8-mg3p-g94g,
# GHSA-r75f-5x8p-qvmc, GHSA-xqmj-j6mv-4862, GHSA-69x8-hrgq-fjj8,
# GHSA-53mr-6c8q-9789, GHSA-jjhc-v7c2-5hh6).
FROM ghcr.io/berriai/litellm:v1.83.7-stable

# asyncpg so gpd_tos.hook.ensure_schema() can (re-)create the custom
# gpd_tos_acceptance table on every worker start. Necessary because
# LiteLLM's bundled PrismaClient silently rolls DDL back on disconnect,
# AND LiteLLM's startup `prisma migrate` step drops unmanaged tables.
# Without this bootstrap, the table disappears on every redeploy.
RUN pip install --no-cache-dir asyncpg==0.31.0

# Our hook modules.
#   gpd_log → POST /gpd/log (session-event ingest to GCS). See
#             infra/litellm/gpd_log/README.md for architecture.
#   gpd_tos → POST /gpd/tos-accept + /gpd/tos-revoke (TOS audit writer,
#             separate Postgres via GPD_AUDIT_DATABASE_URL). See
#             docs/LOGGING.md + infra/litellm/gpd_tos/migrations/.
COPY gpd_log /app/gpd_log
COPY gpd_tos /app/gpd_tos

# Activate both hooks. LiteLLM iterates this comma-separated list during
# worker startup (proxy_server.py:777-803, PR #22931) and calls each
# entry as `module:function`. Both hooks run sequentially; failure in
# one does not halt the others (each register() has a try-local scope).
ENV LITELLM_WORKER_STARTUP_HOOKS=gpd_log.hook:register,gpd_tos.hook:register
ENV PYTHONPATH=/app
