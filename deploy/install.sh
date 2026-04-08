#!/usr/bin/env bash
# Install or update the app on an Ubuntu/Debian VM (as a normal user with sudo).
# Usage:
#   ./deploy/install.sh                 # full install from repo root
#   ./deploy/install.sh /opt/face-attendance
#   ./deploy/install.sh --build-only    # npm build + optional systemctl restart
set -euo pipefail

BUILD_ONLY=false
INSTALL_ROOT=""

for arg in "$@"; do
  case "$arg" in
    --build-only) BUILD_ONLY=true ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
    *)
      if [[ -z "$INSTALL_ROOT" ]]; then
        INSTALL_ROOT="$arg"
      fi
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "$INSTALL_ROOT" ]]; then
  INSTALL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

cd "$INSTALL_ROOT"
echo "==> Install root: $INSTALL_ROOT"

chmod +x "$INSTALL_ROOT/deploy/install.sh" \
  "$INSTALL_ROOT/deploy/pack_static_for_vm.sh" \
  "$INSTALL_ROOT/deploy/gunicorn_start.sh" \
  "$INSTALL_ROOT/run_server.sh" 2>/dev/null || true

SKIP_NPM=false
if [[ ! -f "$INSTALL_ROOT/frontend/package.json" ]]; then
  if [[ -f "$INSTALL_ROOT/static/index.html" ]]; then
    echo "==> No frontend/ but static/index.html exists — skipping npm build."
    SKIP_NPM=true
  else
    echo "" >&2
    echo "ERROR: No frontend/package.json and no static/index.html" >&2
    echo "" >&2
    echo "Pick one:" >&2
    echo "  A) Push full repo with frontend/, or: scp -r ./frontend root@SERVER:$INSTALL_ROOT/" >&2
    echo "  B) On laptop run:  export VITE_API_URL=http://SERVER:PORT/api && ./deploy/pack_static_for_vm.sh" >&2
    echo "     then: scp static-for-vm.tar.gz root@SERVER:$INSTALL_ROOT/ && ssh SERVER 'cd $INSTALL_ROOT && tar xzvf static-for-vm.tar.gz'" >&2
    echo "" >&2
    exit 1
  fi
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" &>/dev/null; then
  echo "python3 not found. Install: sudo apt install python3 python3-venv python3-pip" >&2
  exit 1
fi
if [[ "$BUILD_ONLY" != true ]] && ! command -v npm &>/dev/null; then
  echo "npm not found. Install: sudo apt install nodejs npm" >&2
  exit 1
fi

if [[ "$BUILD_ONLY" == true ]]; then
  ENV_FILE="/etc/face-attendance.env"
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
  elif [[ -f "$INSTALL_ROOT/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$INSTALL_ROOT/.env"
    set +a
  fi
  if ! command -v npm &>/dev/null; then
    echo "npm not found. Install: sudo apt install nodejs npm" >&2
    exit 1
  fi
  if [[ -z "${VITE_API_URL:-}" ]]; then
    echo "VITE_API_URL not set. Set it in /etc/face-attendance.env (see deploy/env.example)" >&2
    exit 1
  fi
  echo "==> Building frontend with VITE_API_URL=$VITE_API_URL"
  cd "$INSTALL_ROOT/frontend"
  npm ci
  VITE_API_URL="$VITE_API_URL" npm run build
  cd "$INSTALL_ROOT"
  if command -v systemctl &>/dev/null && systemctl is-active --quiet face-attendance 2>/dev/null; then
    sudo systemctl restart face-attendance
    echo "==> Restarted face-attendance"
  fi
  exit 0
fi

echo "==> Creating venv"
if [[ ! -d "$INSTALL_ROOT/venv" ]]; then
  "$PYTHON_BIN" -m venv "$INSTALL_ROOT/venv"
fi
# shellcheck source=/dev/null
source "$INSTALL_ROOT/venv/bin/activate"
pip install --upgrade pip wheel
pip install -r "$INSTALL_ROOT/requirements.txt"

if [[ ! -f /etc/face-attendance.env ]]; then
  echo "==> No /etc/face-attendance.env yet."
  echo "    sudo cp $INSTALL_ROOT/deploy/env.example /etc/face-attendance.env"
  echo "    sudo chmod 640 /etc/face-attendance.env"
  echo "    sudo editor /etc/face-attendance.env   # set DATABASE_* and VITE_API_URL"
  echo ""
  if [[ "${NONINTERACTIVE:-}" != "1" ]]; then
    read -r -p "Create /etc/face-attendance.env from example now? [y/N] " ans || true
  else
    ans="n"
  fi
  if [[ "${ans:-}" =~ ^[yY]$ ]]; then
    sudo cp "$INSTALL_ROOT/deploy/env.example" /etc/face-attendance.env
    sudo chmod 640 /etc/face-attendance.env
    echo "    Edit with: sudo nano /etc/face-attendance.env"
  fi
fi

if [[ -f /etc/face-attendance.env ]]; then
  set -a
  # shellcheck source=/dev/null
  source /etc/face-attendance.env
  set +a
fi

if [[ "$SKIP_NPM" == true ]]; then
  :
elif [[ -z "${VITE_API_URL:-}" ]]; then
  echo "VITE_API_URL missing. Set it in /etc/face-attendance.env then run:" >&2
  echo "  ./deploy/install.sh --build-only" >&2
else
  echo "==> Building frontend (VITE_API_URL=$VITE_API_URL)"
  cd "$INSTALL_ROOT/frontend"
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  VITE_API_URL="$VITE_API_URL" npm run build
  cd "$INSTALL_ROOT"
fi

DEPLOY_USER="${DEPLOY_USER:-${SUDO_USER:-}}"
DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"

echo "==> Installing systemd unit (user=$DEPLOY_USER)"
SERVICE_SRC="$INSTALL_ROOT/deploy/face-attendance.service"
SERVICE_DST="/etc/systemd/system/face-attendance.service"
TMP_SVC="$(mktemp)"
sed -e "s|__INSTALL_ROOT__|$INSTALL_ROOT|g" -e "s|__DEPLOY_USER__|$DEPLOY_USER|g" "$SERVICE_SRC" >"$TMP_SVC"
sudo cp "$TMP_SVC" "$SERVICE_DST"
rm -f "$TMP_SVC"
sudo systemctl daemon-reload
sudo systemctl enable face-attendance
echo "==> Start with: sudo systemctl start face-attendance"
echo "==> Logs:       sudo journalctl -u face-attendance -f"
