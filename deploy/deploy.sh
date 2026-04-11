#!/usr/bin/env bash
# One-shot deploy: git pull (whole repo) → Python deps → frontend build → static copy → restart Gunicorn.
#
# Usage (on server, from repo root or anywhere):
#   sudo bash deploy/deploy.sh
#   sudo bash deploy/deploy.sh --no-pull     # skip git (only build + restart)
#
# Expects /etc/face-attendance.env for production (same file systemd uses). Optional keys:
#   VITE_API_URL   e.g. https://jigness.rovark.in/attendance/api
#   VITE_BASE_PATH default /attendance/
#   STATIC_DEPLOY  default /var/www/face-attendance/static
#   GIT_BRANCH     default main

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

DO_PULL=1
for arg in "$@"; do
  case "$arg" in
    --no-pull) DO_PULL=0 ;;
  esac
done

# Load server env (VITE_*, FLASK_*, etc.) — same as face-attendance.service
if [[ -f /etc/face-attendance.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source /etc/face-attendance.env
  set +a
fi

GIT_BRANCH="${GIT_BRANCH:-main}"
VITE_BASE_PATH="${VITE_BASE_PATH:-/attendance/}"
VITE_API_URL="${VITE_API_URL:-https://jigness.rovark.in/attendance/api}"
STATIC_DEPLOY="${STATIC_DEPLOY:-/var/www/face-attendance/static}"
VENV="${VENV:-${REPO_ROOT}/venv}"
SERVICE_NAME="${SERVICE_NAME:-face-attendance}"

log() { echo "[deploy] $*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  log "Run as root so we can copy static files and restart systemd (sudo bash deploy/deploy.sh)"
  exit 1
fi

if [[ "$DO_PULL" -eq 1 ]]; then
  log "git fetch && git pull origin ${GIT_BRANCH}"
  git fetch origin
  git pull origin "$GIT_BRANCH"
else
  log "Skipping git pull (--no-pull)"
fi

if [[ ! -d "$VENV" ]]; then
  log "No venv at $VENV — create with: python3 -m venv venv && $VENV/bin/pip install -r requirements.txt"
  exit 1
fi

log "pip install -r requirements.txt"
"$VENV/bin/pip" install -q -r "$REPO_ROOT/requirements.txt"

if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
  log "npm ci (first time / clean)"
  (cd "$REPO_ROOT/frontend" && npm ci)
else
  log "npm install"
  (cd "$REPO_ROOT/frontend" && npm install)
fi

log "vite build (VITE_BASE_PATH=$VITE_BASE_PATH VITE_API_URL=$VITE_API_URL)"
(
  cd "$REPO_ROOT/frontend"
  export VITE_BASE_PATH
  export VITE_API_URL
  npm run build
)

if [[ ! -f "$REPO_ROOT/static/index.html" ]]; then
  log "ERROR: expected $REPO_ROOT/static/index.html after build — check frontend/vite.config.js outDir"
  exit 1
fi

log "rsync static/ → $STATIC_DEPLOY/"
mkdir -p "$STATIC_DEPLOY"
rsync -a --delete "$REPO_ROOT/static/" "$STATIC_DEPLOY/"

if id www-data &>/dev/null; then
  chown -R www-data:www-data "$STATIC_DEPLOY"
fi
chmod -R a+rX "$STATIC_DEPLOY"

log "systemctl restart $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 1
systemctl is-active --quiet "$SERVICE_NAME" || {
  log "Service failed to stay active; last logs:"
  journalctl -u "$SERVICE_NAME" -n 30 --no-pager
  exit 1
}

if command -v nginx &>/dev/null; then
  nginx -t && systemctl reload nginx
  log "nginx reloaded"
fi

log "Done. Quick check:"
curl -sS -o /dev/null -w "  GET /api/status HTTP %{http_code}\n" --max-time 10 "http://127.0.0.1:${FLASK_PORT:-8002}/api/status" || true
