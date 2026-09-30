# SYNAPSE — Raspberry Pi 4/5 Deployment Guide

## 1. Prerequisites
- Raspberry Pi 4 Model B (4GB/8GB) or Raspberry Pi 5.
- Raspberry Pi OS (64-bit, Debian Bookworm recommended).
- Python 3.10, 3.11, or 3.12.

## 2. Fast Installation

```bash
# Clone the repository
git clone https://github.com/Ghadyalpatil/Synapse.git /opt/synapse
cd /opt/synapse

# Install system dependencies
sudo apt update && sudo apt install -y python3-pip python3-venv libsodium-dev

# Create virtual environment and install package
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Provision cryptographic identity
python deploy/scripts/provision_keys.py --node-id SYNAPSE-RPI-01 --keys-dir var/keys

# Run node
python -m synapse --node-id SYNAPSE-RPI-01 --comm-port 5000 --discovery-port 5999 --api-port 8080
```

## 3. Production Daemon Setup
```bash
sudo bash deploy/scripts/install_systemd.sh
sudo systemctl start synapse-node
```
