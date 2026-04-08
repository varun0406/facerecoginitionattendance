#!/usr/bin/env bash
# Always runs from the project root (avoids "can't open app.py" when cwd is wrong).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
export FLASK_PORT="${FLASK_PORT:-8002}"
echo "Starting Flask on 0.0.0.0:${FLASK_PORT} (set FLASK_PORT to change)"
exec python3 app.py
