#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
if [ -f .env ]; then
  uv run --env-file .env gym-web
else
  uv run gym-web
fi
