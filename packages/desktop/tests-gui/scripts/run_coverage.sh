#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run pytest tests_unit \
  --cov=gpd_tests \
  --cov-branch \
  --cov-report=html \
  --cov-report=term-missing \
  --cov-report=xml \
  "$@"
echo
echo "HTML report: $(pwd)/coverage_html/index.html"
