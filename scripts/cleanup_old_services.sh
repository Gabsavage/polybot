#!/bin/bash
# Cleanup separate indexer services — now integrated in polybot-bot.service
set -e

for svc in polybot-markets polybot-proxy-factory polybot-resolutions polybot-onchain polybot-trades; do
    echo "Stopping ${svc}..."
    systemctl stop "${svc}.timer" 2>/dev/null || true
    systemctl stop "${svc}.service" 2>/dev/null || true
    systemctl disable "${svc}.timer" 2>/dev/null || true
    systemctl disable "${svc}.service" 2>/dev/null || true
    rm -f "/etc/systemd/system/${svc}.service" "/etc/systemd/system/${svc}.timer"
done

systemctl daemon-reload
echo "Old services cleaned up. All indexers now run inside polybot-bot.service."
