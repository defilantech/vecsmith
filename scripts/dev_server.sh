#!/usr/bin/env bash
# Start the orchestrator in development mode with local service URLs.
set -euo pipefail

export VECSMITH_LLM_BASE_URL="${VECSMITH_LLM_BASE_URL:-http://localhost:8080/v1}"
export VECSMITH_FLUX_BASE_URL="${VECSMITH_FLUX_BASE_URL:-http://localhost:8081}"
export VECSMITH_HOST="${VECSMITH_HOST:-127.0.0.1}"
export VECSMITH_PORT="${VECSMITH_PORT:-8080}"

echo "Starting VecSmith Orchestrator (dev mode)"
echo "  LLM:  $VECSMITH_LLM_BASE_URL"
echo "  Flux: $VECSMITH_FLUX_BASE_URL"
echo "  Listen: $VECSMITH_HOST:$VECSMITH_PORT"
echo ""

cd "$(dirname "$0")/.."
exec python -m src.orchestrator.app
