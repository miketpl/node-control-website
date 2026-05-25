#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# NodeControl License API — DGX Spark Deployment Script
# Run as root (or with sudo) on a fresh Ubuntu 22+ box.
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# Before running:
#   1. Copy the backend/ folder to /opt/nodecontrol-api/
#   2. Create /opt/nodecontrol-api/.env from .env.example
#   3. Point api.nodecontrol.io DNS (A record) to this server's IP
# ──────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/nodecontrol-api"
LOG_DIR="/var/log/nodecontrol-api"

echo "==> NodeControl License API Setup"
echo ""

# ── 1. System packages ──────────────────────────────────────
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx

# ── 2. Create log directory ─────────────────────────────────
echo "[2/7] Creating log directory..."
mkdir -p "$LOG_DIR"
chown www-data:www-data "$LOG_DIR"

# ── 3. Check app directory exists ───────────────────────────
echo "[3/7] Checking app files..."
if [ ! -f "$APP_DIR/app.py" ]; then
    echo "ERROR: $APP_DIR/app.py not found."
    echo "Copy the backend files first:"
    echo "  sudo mkdir -p $APP_DIR"
    echo "  sudo cp -r backend/* $APP_DIR/"
    exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
    echo "ERROR: $APP_DIR/.env not found."
    echo "Create it from .env.example:"
    echo "  sudo cp $APP_DIR/.env.example $APP_DIR/.env"
    echo "  sudo nano $APP_DIR/.env"
    exit 1
fi

# ── 4. Python venv + dependencies ───────────────────────────
echo "[4/7] Setting up Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$APP_DIR/venv/bin/pip" install --quiet python-dotenv

# Set ownership
chown -R www-data:www-data "$APP_DIR"

# ── 5. Nginx config ─────────────────────────────────────────
echo "[5/7] Configuring nginx..."
cp "$APP_DIR/deploy/nginx-api.conf" /etc/nginx/sites-available/nodecontrol-api
ln -sf /etc/nginx/sites-available/nodecontrol-api /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# ── 6. Systemd service ──────────────────────────────────────
echo "[6/7] Installing systemd service..."
cp "$APP_DIR/deploy/nodecontrol-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable nodecontrol-api
systemctl start nodecontrol-api

# ── 7. SSL certificate ──────────────────────────────────────
echo "[7/7] Requesting SSL certificate..."
echo "  (If DNS hasn't propagated yet, run this later:)"
echo "  sudo certbot --nginx -d api.nodecontrol.io"
echo ""
read -p "Run certbot now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    certbot --nginx -d api.nodecontrol.io --non-interactive --agree-tos --email mike.irwin@live.com
fi

# ── Done ────────────────────────────────────────────────────
echo ""
echo "==> Setup complete!"
echo ""
echo "Service status:"
systemctl status nodecontrol-api --no-pager -l
echo ""
echo "Test it:"
echo "  curl http://localhost:5000/api/health"
echo "  curl https://api.nodecontrol.io/api/health"
echo ""
echo "Useful commands:"
echo "  sudo systemctl restart nodecontrol-api    # restart after .env changes"
echo "  sudo journalctl -u nodecontrol-api -f     # live logs"
echo "  sudo tail -f $LOG_DIR/error.log           # gunicorn errors"
