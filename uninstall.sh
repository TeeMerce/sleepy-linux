#!/bin/bash
echo "Uninstalling Sleepy Linux..."

# Stop and Disable User Service
systemctl --user stop sleepy-listener 2>/dev/null || true
systemctl --user disable sleepy-listener 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/sleepy-listener.service"
systemctl --user daemon-reload

# Stop System Services
sudo systemctl stop sleepy-boot sleepy-shutdown 2>/dev/null || true
sudo systemctl disable sleepy-boot sleepy-shutdown 2>/dev/null || true
sudo rm -f /etc/systemd/system/sleepy-boot.service /etc/systemd/system/sleepy-shutdown.service
sudo systemctl daemon-reload

# Cleanup Files
sudo rm -rf /opt/sleepy-linux
sudo rm -f /usr/local/bin/sleepy-ctl

echo "Done."