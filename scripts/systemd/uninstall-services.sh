#!/bin/bash
# NPD Systemd Services Uninstallation Script
# Run with sudo

set -e

echo "Stopping and disabling NPD systemd services..."

# Stop and disable services
systemctl stop npd-smee-webhook.service 2>/dev/null || true
systemctl stop npd-email-monitor.timer 2>/dev/null || true
systemctl stop npd-email-monitor.service 2>/dev/null || true

systemctl disable npd-smee-webhook.service 2>/dev/null || true
systemctl disable npd-email-monitor.timer 2>/dev/null || true
systemctl disable npd-email-monitor.service 2>/dev/null || true

# Remove service files
rm -f /etc/systemd/system/npd-smee-webhook.service
rm -f /etc/systemd/system/npd-email-monitor.service
rm -f /etc/systemd/system/npd-email-monitor.timer

# Reload systemd
systemctl daemon-reload

echo "NPD systemd services removed."
echo "Log files in /var/log/npd/ were preserved."
