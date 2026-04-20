#!/bin/bash
# VPS provisioning script — run as root on fresh Ubuntu 24.04
set -euo pipefail

echo "=== Polybot VPS Setup ==="

# System updates
apt update && apt upgrade -y
apt install -y ufw fail2ban git curl

# SSH hardening
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

# fail2ban
systemctl enable fail2ban
systemctl start fail2ban

# Create polybot user
useradd -m -s /bin/bash polybot || true
mkdir -p /opt/polybot /var/log/polybot /data
chown polybot:polybot /opt/polybot /var/log/polybot /data

# Install uv (as polybot user)
su - polybot -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'

echo ""
echo "=== Base setup complete ==="
echo ""
echo "Next steps (as polybot user):"
echo "  1. Clone repo to /opt/polybot"
echo "  2. cp .env.example .env && edit with real credentials"
echo "  3. ~/.local/bin/uv sync --extra dev"
echo "  4. ~/.local/bin/uv run python scripts/init_db.py --db /data/pm.duckdb"
echo ""
echo "Then as root:"
echo "  5. cp /opt/polybot/deploy/polybot-*.service /etc/systemd/system/"
echo "  6. cp /opt/polybot/deploy/polybot-*.timer /etc/systemd/system/"
echo "  7. systemctl daemon-reload"
echo "  8. systemctl enable --now polybot-snapshot.timer polybot-universe-refresh.timer polybot-healthcheck.timer"
echo "  9. systemctl list-timers polybot-*"
