#!/bin/bash
# 🚀 Quick Deploy Script for DigitalOcean Droplet
# Usage: ./deploy/droplet-deploy.sh <droplet-ip>

set -e

DROPLET_IP=$1
APP_DIR="/root/aureon-trading"
SERVICE_NAME="aureon-trading"

if [ -z "$DROPLET_IP" ]; then
    echo "❌ Error: Please provide droplet IP"
    echo "Usage: ./deploy/droplet-deploy.sh <droplet-ip>"
    exit 1
fi

echo "🚀 Deploying Aureon Trading to $DROPLET_IP"

# 1. Update code on droplet
echo "📦 Pushing code to droplet..."
ssh root@$DROPLET_IP << 'ENDSSH'
cd /root/aureon-trading || {
    echo "First time setup..."
    cd /root
    git clone https://github.com/RA-CONSULTING/aureon-trading.git
    cd aureon-trading
}

# Pull latest changes
git fetch origin
git reset --hard origin/main
git pull origin main

# Install/update dependencies
source venv/bin/activate 2>/dev/null || python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup systemd service
if [ ! -f /etc/systemd/system/aureon-trading.service ]; then
    echo "Installing systemd service..."
    cp deploy/systemd/aureon-trading.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable aureon-trading
fi

# Restart service
echo "🔄 Restarting service..."
systemctl restart aureon-trading
sleep 3

# Check status
systemctl status aureon-trading --no-pager
ENDSSH

echo "✅ Deployment complete!"
echo ""
echo "📊 Check logs: ssh root@$DROPLET_IP 'journalctl -u aureon-trading -f'"
echo "📈 Check status: ssh root@$DROPLET_IP 'systemctl status aureon-trading'"
