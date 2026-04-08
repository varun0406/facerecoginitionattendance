#!/usr/bin/env bash
# Run on the VM while the app is listening. Helps debug "browser cannot connect".
set -euo pipefail
PORT="${FLASK_PORT:-8002}"
echo "=== Listening on $PORT (need 0.0.0.0:$PORT) ==="
ss -tlnp 2>/dev/null | grep -E ":$PORT\\b" || netstat -tlnp 2>/dev/null | grep -E ":$PORT\\b" || echo "(install iproute2: ss, or use netstat)"
echo ""
echo "=== curl localhost (should return HTML) ==="
curl -sS -o /dev/null -w "HTTP %{http_code}\n" "http://127.0.0.1:$PORT/" || true
echo ""
echo "=== UFW (inactive = no Ubuntu firewall blocking) ==="
sudo ufw status 2>/dev/null || echo "ufw not installed"
echo ""
echo "=== Public IPs (open TCP $PORT in your CLOUD panel for these) ==="
hostname -I 2>/dev/null || true
curl -sS --connect-timeout 2 https://api.ipify.org 2>/dev/null && echo " (outbound IP)" || true
echo ""
echo "If curl localhost works but your laptop cannot:"
echo "  1) In Hostinger / AWS / GCP / etc.: add inbound rule TCP $PORT (or use nginx on :80)."
echo "  2) On VM: sudo ufw allow $PORT/tcp && sudo ufw reload"
