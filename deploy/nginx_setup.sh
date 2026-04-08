#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# nginx_setup.sh — one-shot nginx ecosystem setup for face-attendance
# Safe on a multi-site server: only touches /etc/nginx/sites-* for this app.
# Run from the repo root: sudo bash deploy/nginx_setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_IP="72.61.240.38"
APP_PORT=8002
NGINX_SITE_NAME="face-attendance"
SITE_AVAILABLE="/etc/nginx/sites-available/${NGINX_SITE_NAME}"
SITE_ENABLED="/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
STATIC_DIR="${INSTALL_ROOT}/static"

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  Face-Attendance  nginx setup"
echo "  Install root : ${INSTALL_ROOT}"
echo "  Server IP    : ${SERVER_IP}"
echo "  Gunicorn port: ${APP_PORT}"
echo "══════════════════════════════════════════════════════════"
echo ""

# ── 1. nginx installed? ───────────────────────────────────────────────────────
if ! command -v nginx &>/dev/null; then
    echo "[1/7] Installing nginx..."
    apt-get update -qq
    apt-get install -y nginx
else
    echo "[1/7] nginx already installed: $(nginx -v 2>&1)"
fi

# ── 2. Verify gunicorn is bound to loopback only ─────────────────────────────
echo "[2/7] Checking gunicorn bind address in gunicorn_start.sh..."
GUNICORN_SCRIPT="${INSTALL_ROOT}/deploy/gunicorn_start.sh"
if grep -q "0.0.0.0" "${GUNICORN_SCRIPT}"; then
    echo "  WARNING: gunicorn binds to 0.0.0.0 — changing to 127.0.0.1 (loopback only)"
    sed -i 's/0\.0\.0\.0/127.0.0.1/g' "${GUNICORN_SCRIPT}"
fi
echo "  gunicorn bind: $(grep -- '--bind' "${GUNICORN_SCRIPT}")"

# ── 3. Install nginx site config ─────────────────────────────────────────────
echo "[3/7] Installing nginx site config → ${SITE_AVAILABLE}"
cp "${INSTALL_ROOT}/deploy/nginx-face-attendance.conf" "${SITE_AVAILABLE}"

# Patch static path to actual install root
sed -i "s|/opt/face-attendance/static|${STATIC_DIR}|g" "${SITE_AVAILABLE}"
sed -i "s|72\.61\.240\.38|${SERVER_IP}|g" "${SITE_AVAILABLE}"

echo "  Installed: ${SITE_AVAILABLE}"

# ── 4. Enable site (symlink) ──────────────────────────────────────────────────
echo "[4/7] Enabling site..."
if [[ ! -L "${SITE_ENABLED}" ]]; then
    ln -sf "${SITE_AVAILABLE}" "${SITE_ENABLED}"
    echo "  Symlink created: ${SITE_ENABLED}"
else
    echo "  Symlink already exists: ${SITE_ENABLED}"
fi

# ── 5. Remove default site if still enabled (it catches all traffic on port 80) ─
DEFAULT_ENABLED="/etc/nginx/sites-enabled/default"
if [[ -L "${DEFAULT_ENABLED}" ]] || [[ -f "${DEFAULT_ENABLED}" ]]; then
    echo "[5/7] Removing default catch-all site (it would intercept our traffic)..."
    rm -f "${DEFAULT_ENABLED}"
    echo "  Removed: ${DEFAULT_ENABLED}"
else
    echo "[5/7] No default site enabled — OK."
fi

# ── 6. nginx.conf global tweaks (only if not already set) ────────────────────
echo "[6/7] Checking nginx.conf global settings..."
NGINX_CONF="/etc/nginx/nginx.conf"
# proxy_read_timeout in http{} block
if ! grep -q "proxy_read_timeout" "${NGINX_CONF}"; then
    # Insert after http { 
    sed -i '/^http {/a\\tproxy_read_timeout 620s;\n\tproxy_send_timeout 620s;\n\tproxy_connect_timeout 10s;' "${NGINX_CONF}"
    echo "  Added global proxy timeouts to nginx.conf"
else
    echo "  proxy_read_timeout already in nginx.conf — not modified"
fi
# server_tokens off
if ! grep -q "server_tokens" "${NGINX_CONF}"; then
    sed -i '/^http {/a\\tserver_tokens off;' "${NGINX_CONF}"
    echo "  Added server_tokens off"
fi

# ── 7. Test config and reload ────────────────────────────────────────────────
echo "[7/7] Testing nginx config..."
nginx -t
echo "  Config OK — reloading nginx..."
systemctl reload nginx
echo "  nginx reloaded."

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  DONE.  nginx site active at http://${SERVER_IP}/"
echo ""
echo "  Check status:    systemctl status nginx"
echo "  Active sites:    ls -la /etc/nginx/sites-enabled/"
echo "  App logs:        journalctl -u face-attendance -f"
echo "  nginx logs:      tail -f /var/log/nginx/access.log"
echo "  nginx err log:   tail -f /var/log/nginx/error.log"
echo ""
echo "  NEXT (camera requires HTTPS):"
echo "    sudo apt install certbot python3-certbot-nginx"
echo "    sudo certbot --nginx -d attendance.yourdomain.com"
echo "══════════════════════════════════════════════════════════"
