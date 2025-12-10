#!/bin/bash
# NPD Systemd Services Installation Script
# Run with sudo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/npd"

echo "Installing NPD systemd services..."

# Create log directory
mkdir -p "$LOG_DIR"
chown pbrown:pbrown "$LOG_DIR"

# Copy service files
cp "$SCRIPT_DIR/npd-smee-webhook.service" /etc/systemd/system/
cp "$SCRIPT_DIR/npd-email-monitor.service" /etc/systemd/system/
cp "$SCRIPT_DIR/npd-email-monitor.timer" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

echo ""
echo "Services installed. To enable:"
echo ""
echo "  # Smee webhook forwarder (edit channel URL first!):"
echo "  sudo systemctl enable --now npd-smee-webhook.service"
echo ""
echo "  # Email monitor cron (5 min interval):"
echo "  sudo systemctl enable --now npd-email-monitor.timer"
echo ""
echo "IMPORTANT: Before starting npd-smee-webhook.service:"
echo "  1. Create a smee.io channel at https://smee.io/new"
echo "  2. Edit /etc/systemd/system/npd-smee-webhook.service"
echo "  3. Replace YOUR_CHANNEL with your actual channel URL"
echo "  4. Run: sudo systemctl daemon-reload"
