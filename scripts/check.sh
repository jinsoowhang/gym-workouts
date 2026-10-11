#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DO_NOT_TRACK=1
export GYM_DBT_DATABASE_PATH=data/warehouse/gym_ci.duckdb
export GYM_USE_SYNTHETIC=true

uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m compileall -q src
uv run dbt debug --profiles-dir .
uv run dbt parse --profiles-dir .
uv run dbt seed --full-refresh --profiles-dir .
uv run dbt build --exclude resource_type:seed --profiles-dir .
uv run sqlfluff lint models analyses tests/dbt
uv run python scripts/check_public_files.py
