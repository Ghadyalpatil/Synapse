# 🚀 SYNAPSE — Raspberry Pi Deployment Guide
Connecting your edge node to the Command Centre over the local network.

---

## Overview

```
┌─────────────────────────────┐          ┌──────────────────────────────────┐
│   Raspberry Pi               │          │   Windows PC (Command Centre)    │
│                              │          │                                  │
│  Thermal / Acoustic / Motion │          │  run_command_center.ps1          │
│  sensors via GPIO/USB        │          │  TCP port  : 5050                │
│                              │  Wi-Fi / │  Web UI    : http://localhost:9000│
│  python -m synapse           │◄────────►│                                  │
│  TCP port  : 5000            │  Ethernet│  Receives live sensor telemetry  │
│  Web UI    : :8080           │  LAN     │  over the SYNAPSE binary mesh    │
└─────────────────────────────┘          └──────────────────────────────────┘
        ▲
        │  Ed25519 signed, 4-byte framed TCP messages
        │  TYPE_SENSOR_DATA  every 3 s
        │  TYPE_TARGET_DETECTED  when threat fires
```

> [!IMPORTANT]
> Both devices must be on the **same LAN** (same Wi-Fi router / same Ethernet switch).
> No internet required — the SYNAPSE mesh is fully air-gapped.

---

## Step 0 — Find Your IP Addresses

### On your Windows PC (Command Centre machine)
Open PowerShell and run:
```powershell
ipconfig
```
Look for your **IPv4 Address** under your Wi-Fi or Ethernet adapter.  
Example: `192.168.1.10`  — **this is `<PC_IP>`** used below.

### On the Raspberry Pi
```bash
hostname -I
```
Example: `192.168.1.50` — **this is `<PI_IP>`** used below.

> [!NOTE]
> If your router assigns IPs via DHCP they can change on reboot. Assign a **static IP** on the Pi for reliability (see Step 5).

---

## Step 1 — Prepare the Raspberry Pi

### Requirements
- Raspberry Pi 3B+ / 4B / Zero 2 W (any model with Wi-Fi or Ethernet)
- Raspberry Pi OS **Bookworm** or **Bullseye** (64-bit recommended)
- Python **3.10 or newer** (pre-installed on Bookworm)
- SSH enabled (run `sudo raspi-config` → Interface Options → SSH → Enable)

### Verify Python version on the Pi
```bash
python3 --version
# Should print: Python 3.10.x or newer
```

---

## Step 2 — Copy the Code to the Raspberry Pi

### Option A — `rsync` from your PC (recommended)

Open PowerShell on your Windows machine and run:
```powershell
# Replace <PI_IP> with your Pi's IP address (e.g. 192.168.1.50)
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='var/' `
    "c:\Users\admin\setup\SYNAPSE COMMUNICATION/" `
    pi@<PI_IP>:/opt/synapse/
```
> If `rsync` is not available on Windows, install it via **Git Bash** or use Option B.

### Option B — `scp` (copy entire folder)
```powershell
scp -r "c:\Users\admin\setup\SYNAPSE COMMUNICATION" pi@<PI_IP>:/opt/synapse
```

### Option C — Git clone on the Pi directly
```bash
# On the Raspberry Pi terminal
git clone https://github.com/Ghadyalpatil/Synapse.git /opt/synapse
cd /opt/synapse
git checkout nishant
```

---

## Step 3 — Run the Automated Setup Script

SSH into the Pi and run the setup script. It will:
- Install all Python dependencies
- Create runtime directories (`/var/lib/synapse`, `/etc/synapse`, `/var/log/synapse`)
- Write the config to `/etc/synapse/node.env`
- Pre-generate Ed25519 cryptographic keys for this node
- Install and enable the `synapse-node.service` systemd unit

```bash
# SSH into the Pi
ssh pi@<PI_IP>

# Run the setup script
cd /opt/synapse
sudo bash deploy/scripts/setup_pi.sh SYNAPSE-PI-001 192.168.1.255
#                                      ^node ID        ^broadcast IP of your LAN
```

> [!TIP]
> Use your actual broadcast IP. For a `192.168.1.x` network it's `192.168.1.255`.
> For `192.168.0.x` it's `192.168.0.255`. You can find it with `ip route` on the Pi.

---

## Step 4 — Configure the Command Centre Peer

The most critical step: tell the Pi where to find the Command Centre PC.

Edit the environment file on the Pi:
```bash
sudo nano /etc/synapse/node.env
```

Add / update these lines:
```env
SYNAPSE_NODE_ID=SYNAPSE-PI-001
SYNAPSE_COMM_PORT=5000
SYNAPSE_DISCOVERY_PORT=5999
SYNAPSE_API_PORT=8080
SYNAPSE_BROADCAST_IP=192.168.1.255
SYNAPSE_LOG_LEVEL=INFO
SYNAPSE_DATA_DIR=/var/lib/synapse/data
SYNAPSE_KEYS_DIR=/etc/synapse/keys
```

Then edit the systemd service to add the Command Centre peer address:
```bash
sudo nano /etc/systemd/system/synapse-node.service
```

Find the `ExecStart=` line and replace `<PC_IP>` with your actual Windows PC IP:
```ini
ExecStart=/usr/bin/python3 -m synapse \
    --auto-poll 3.0 \
    --stream-telemetry \
    --telemetry-target COMMAND-CENTER \
    --peer COMMAND-CENTER@192.168.1.10:5050 \
    --db-path /var/lib/synapse/data/node.db \
    --keys-dir /etc/synapse/keys
```

Reload and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable synapse-node
sudo systemctl start synapse-node
```

---

## Step 5 — Start the Command Centre on your PC

Open PowerShell in the SYNAPSE project folder on your Windows machine:
```powershell
cd "c:\Users\admin\setup\SYNAPSE COMMUNICATION"
.\run_command_center.ps1
```

Or directly:
```powershell
python command_center.py `
    --node-id COMMAND-CENTER `
    --comm-port 5050 `
    --discovery-port 5997 `
    --port 9000 `
    --broadcast-ip 192.168.1.255 `
    --peer SYNAPSE-PI-001@192.168.1.50:5000 `
    --db-path var/data/command_center.db `
    --keys-dir var/keys/command_center `
    --open-browser `
    --log-level INFO
```

> [!IMPORTANT]
> Replace `192.168.1.50` with your Pi's actual IP and `192.168.1.255` with your LAN broadcast.

The browser will open **http://localhost:9000** automatically. You should see the Sensor Matrix populate within 5–10 seconds as the Pi starts streaming.

---

## Step 6 — Verify the Connection

### On the Pi — check logs
```bash
sudo journalctl -u synapse-node -f
```
You should see:
```
[INFO] [CommManager] Sent MSG-XXXXXXXX (SENSOR_DATA) -> COMMAND-CENTER (Delivered: ['COMMAND-CENTER'])
[INFO] [CommManager] Sent MSG-XXXXXXXX (TARGET_DETECTED) -> BROADCAST (Delivered: ['COMMAND-CENTER'])
```

### On the PC — check the API
Open a browser to:
- **http://localhost:9000** — Live C2 Dashboard (Sensor Matrix tab)
- **http://localhost:9000/api/status** — Should show `total_sensors_reporting: 3`
- **http://localhost:9000/api/sensors/latest** — Should show thermal, acoustic, motion readings from `SYNAPSE-PI-001`

### On the Pi — check the Pi's own API
```
http://<PI_IP>:8080/api/status
```

---

## Step 5b — (Optional) Assign a Static IP to the Pi

To prevent the Pi's IP from changing on reboot:
```bash
sudo nano /etc/dhcpcd.conf
```
Add at the end:
```
interface wlan0       # or eth0 if using Ethernet
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```
Then reboot: `sudo reboot`

---

## Firewall / Port Check (Windows)

The Command Centre listens on **TCP port 5050**. If Windows Defender Firewall blocks it:

```powershell
# Run PowerShell as Administrator
New-NetFirewallRule -DisplayName "SYNAPSE Command Centre" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 5050 `
    -Action Allow
```

---

## Architecture Reference

| Component | Host | TCP (Mesh) | UDP (Discovery) | Web UI |
|---|---|---|---|---|
| `SYNAPSE-PI-001` | Raspberry Pi | 5000 | 5999 | `:8080` |
| `COMMAND-CENTER` | Windows PC | 5050 | 5997 | `:9000` |

### Message Flow
```
[Pi sensors poll every 3s]
       ↓
EventEngine.broadcast_sensor_telemetry()
       ↓
TYPE_SENSOR_DATA  →  TCP framed binary (Ed25519 signed)
       ↓
CommunicationManager.router.forward_or_deliver()
       ↓
TCP connect → 192.168.1.10:5050 (Command Centre)
       ↓
Command Centre handle_incoming_message()
       ↓ saves to SQLite  ↓ fires WebSocket push
Dashboard browser ← WS event (real-time, < 1s latency)
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| No sensors on dashboard | Pi can't reach PC on port 5050 | Check Windows firewall (see above). Ping the PC from Pi: `ping 192.168.1.10` |
| `Connection refused` in Pi logs | Command Centre not running | Start `run_command_center.ps1` first, then start the Pi service |
| Data arrives but node shows OFFLINE | Heartbeat packets lost | Both devices on same subnet? Check `--broadcast-ip` matches LAN |
| `QUEUED_STORE_AND_FORWARD` in logs | Temporary network drop | Automatic — the Pi will retry and deliver buffered packets when connectivity resumes |
| Python 3.9 error on Pi | Too old | `sudo apt install python3.11` or `sudo apt install python3.10` |
| `pynacl` install fails | Missing libsodium | `sudo apt install libsodium-dev` then `pip install pynacl` |

---

## Quick Commands Reference

```bash
# Service control on the Pi
sudo systemctl start synapse-node
sudo systemctl stop synapse-node
sudo systemctl restart synapse-node
sudo systemctl status synapse-node

# Live logs
sudo journalctl -u synapse-node -f

# Manual run (for testing — not as service)
cd /opt/synapse
python3 -m synapse \
  --node-id SYNAPSE-PI-001 \
  --auto-poll 3.0 \
  --stream-telemetry \
  --telemetry-target COMMAND-CENTER \
  --peer COMMAND-CENTER@192.168.1.10:5050 \
  --log-level DEBUG

# Check what's in the local sensor DB on the Pi
sqlite3 /var/lib/synapse/data/node.db \
  "SELECT sensor_id, sensor_type, timestamp FROM sensor_data ORDER BY timestamp DESC LIMIT 10;"
```
