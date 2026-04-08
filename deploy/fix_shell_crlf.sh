#!/usr/bin/env bash
# On Linux: fixes /usr/bin/env: bash\r — Windows CRLF in .sh files
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for f in "$ROOT/run_server.sh" "$ROOT/start.sh" "$ROOT/deploy"/*.sh; do
  [[ -f "$f" ]] || continue
  sed -i 's/\r$//' "$f"
done
chmod +x "$ROOT/run_server.sh" "$ROOT/deploy"/*.sh 2>/dev/null || true
echo "OK: CRLF stripped in shell scripts under $ROOT"
