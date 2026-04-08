#!/usr/bin/env bash
# Run on YOUR LAPTOP inside the full repo (must have frontend/package.json).
# Produces static-for-vm.tar.gz — upload to the server if you cannot run npm there.
#
# Usage:
#   export VITE_API_URL=http://72.61.240.38:8002/api   # same host:port as FLASK_PORT on VM
#   ./deploy/pack_static_for_vm.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/frontend/package.json" ]]; then
  echo "ERROR: $ROOT/frontend/package.json not found. Use a full clone of the project." >&2
  exit 1
fi

if [[ -z "${VITE_API_URL:-}" ]]; then
  echo "Set VITE_API_URL to your VM URL (must match FLASK_PORT), e.g.:" >&2
  echo "  export VITE_API_URL=http://YOUR_IP:8002/api" >&2
  exit 1
fi

echo "==> Building with VITE_API_URL=$VITE_API_URL"
cd "$ROOT/frontend"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
VITE_API_URL="$VITE_API_URL" npm run build
cd "$ROOT"

OUT="$ROOT/static-for-vm.tar.gz"
tar -czvf "$OUT" static/
echo ""
echo "==> Created: $OUT"
echo "    Upload:  scp $OUT root@YOUR_SERVER:/opt/facerecoginitionattendance/"
echo "    On VM:   cd /opt/facerecoginitionattendance && tar xzvf static-for-vm.tar.gz"
