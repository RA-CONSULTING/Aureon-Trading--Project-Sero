#!/bin/bash
# 🔧 Initial Setup Script for DigitalOcean Droplet
# Run this ONCE on a fresh Ubuntu 24.04 droplet
# Usage: curl -sSL https://raw.githubusercontent.com/RA-CONSULTING/aureon-trading/main/deploy/droplet-setup.sh | bash

set -e

echo "🚀 Aureon Trading - DigitalOcean Droplet Setup"
echo "=============================================="

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install Python 3.12 and dependencies
echo "🐍 Installing Python 3.12..."
apt install -y python3.12 python3.12-venv python3-pip git build-essential curl

# Install Docker (optional but recommended)
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Install DigitalOcean agent for monitoring
echo "📊 Installing DO monitoring agent..."
curl -sSL https://repos.insights.digitalocean.com/install.sh | bash

# Create application directory
echo "📁 Setting up application..."
cd /root
if [ ! -d "aureon-trading" ]; then
    git clone https://github.com/RA-CONSULTING/aureon-trading.git
fi
cd aureon-trading

# Create Python virtual environment
echo "🔧 Creating Python virtual environment..."
python3.12 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📚 Installing Python packages..."
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Create .env template
echo "📝 Creating .env template..."
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || touch .env
    echo "⚠️  IMPORTANT: Please edit .env with your API keys!"
fi

# Install Systemd Service
echo "⚙️ Installing Systemd Service..."
cp deploy/orca-kill-cycle.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable orca-kill-cycle
systemctl start orca-kill-cycle

echo "✅ Setup Complete! The Orca Kill Cycle is running."
echo "👉 Check logs with: journalctl -u orca-kill-cycle -f"
echo "👉 Edit config with: nano .env"
# 🔑 API Keys - Replace with your actual keys
KRAKEN_API_KEY=your_kraken_key_here
KRAKEN_API_SECRET=your_kraken_secret_here

BINANCE_API_KEY=your_binance_key_here
BINANCE_API_SECRET=your_binance_secret_here

ALPACA_API_KEY=your_alpaca_key_here
ALPACA_API_SECRET=your_alpaca_secret_here

CAPITAL_API_KEY=your_capital_key_here
CAPITAL_API_PASSWORD=your_capital_password_here
CAPITAL_IDENTIFIER=your_capital_identifier_here

# System Configuration
PYTHONIOENCODING=utf-8
LOG_LEVEL=INFO
EOF
    chmod 600 .env
    echo "⚠️  IMPORTANT: Edit /root/aureon-trading/.env with your API keys!"
fi

# Install systemd service
echo "⚙️  Installing systemd service..."
cp deploy/systemd/aureon-trading.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable aureon-trading

# Setup log rotation
echo "📜 Configuring log rotation..."
cat > /etc/logrotate.d/aureon-trading << 'EOF'
/var/log/aureon-trading*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        systemctl reload aureon-trading > /dev/null 2>&1 || true
    endscript
}
EOF

# Setup firewall (allow SSH only)
echo "🔒 Configuring firewall..."
ufw --force enable
ufw allow 22/tcp
ufw allow 80/tcp  # Optional: if you add a web dashboard
ufw allow 443/tcp # Optional: if you add a web dashboard

# Create backup script
echo "💾 Creating backup script..."
mkdir -p /root/aureon-backups
cat > /root/backup-aureon.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/aureon-backups"
mkdir -p $BACKUP_DIR

# Backup state files
tar -czf $BACKUP_DIR/aureon-state-$DATE.tar.gz \
  /root/aureon-trading/*.json \
  /root/aureon-trading/state/ 2>/dev/null || true

# Keep only last 7 days
find $BACKUP_DIR -name "aureon-state-*.tar.gz" -mtime +7 -delete

echo "✅ Backup created: aureon-state-$DATE.tar.gz"
EOF

chmod +x /root/backup-aureon.sh

# Add backup to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-aureon.sh >> /var/log/aureon-backup.log 2>&1") | crontab -

# Print completion message
echo ""
echo "✅ Setup complete!"
echo "=============================================="
echo ""
echo "📝 Next steps:"
echo "1. Edit API keys: nano /root/aureon-trading/.env"
echo "2. Start service: systemctl start aureon-trading"
echo "3. Check status: systemctl status aureon-trading"
echo "4. View logs: journalctl -u aureon-trading -f"
echo ""
echo "🔗 Useful commands:"
echo "  systemctl restart aureon-trading  # Restart trading system"
echo "  journalctl -u aureon-trading -f   # Follow logs"
echo "  /root/backup-aureon.sh            # Manual backup"
echo ""
echo "⚠️  Don't forget to edit /root/aureon-trading/.env with your API keys!"
