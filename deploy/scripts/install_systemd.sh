#!/usr/bin/env bash
# SYNAPSE Edge Node Systemd Installation Script
set -e

if [ "$EUID" -ne 0 ]; then
  echo "[-] Please run as root: sudo bash deploy/scripts/install_systemd.sh"
  exit 1
fi

echo "[+] Installing SYNAPSE edge daemon..."
mkdir -p /opt/synapse
mkdir -p /var/lib/synapse/data
mkdir -p /etc/synapse/keys
mkdir -p /var/log/synapse

# Copy systemd service file
cp deploy/systemd/synapse-node.service /etc/systemd/system/synapse-node.service

# Reload and enable
systemctl daemon-reload
systemctl enable synapse-node.service

echo "[+] SYNAPSE edge service successfully installed."
echo "[+] Start with: sudo systemctl start synapse-node"
echo "[+] Status with: sudo systemctl status synapse-node"
