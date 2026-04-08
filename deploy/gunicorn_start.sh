#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PORT="${FLASK_PORT:-8002}"
exec "$ROOT/venv/bin/gunicorn" \
  --bind "127.0.0.1:${PORT}" \
  --workers 1 \
  --threads 4 \
  --timeout 620 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
