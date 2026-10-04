# SYNAPSE — Raspberry Pi Deployment Guide
### Deploying an Edge Surveillance Node and Connecting it to the Command Centre PC

---

## System Overview

```
┌────────────────────────────────┐          ┌──────────────────────────────────────┐
│   Raspberry Pi (Edge Node)     │          │   Windows PC (Command Centre)        │
│                                │          │                                      │
│  Thermal / Acoustic / Motion   │  Wi-Fi   │  python command_center.py            │
│  sensors → SensorManager       │◄────────►│  TCP port  : 5050                    │
│                                │  or      │  Web UI    : http://localhost:9000   │
│  python -m synapse             │  Ethernet│                                      │
│  TCP  : 5000  (mesh)           │   LAN    │  Live sensor data appears here       │
│  UDP  : 5999  (discovery)      │          │  within 5 seconds of Pi boot         │
│  API  : 8080  (local UI)       │          │                                      │
└────────────────────────────────┘          └──────────────────────────────────────┘
```

Both devices must be on the **same LAN** (same Wi-Fi router or Ethernet switch).  
No internet is needed — the SYNAPSE mesh is fully air-gapped.

---

## Part 1 — Prepare Your Network

### Step 1.1 — Find the IP address of your Windows PC

Open PowerShell on your PC and run:
```powershell
ipconfig
```
Look for **IPv4 Address** under your active adapter (Wi-Fi or Ethernet).

Example output:
```
Wireless LAN adapter Wi-Fi:
   IPv4 Address. . . . . . . : 192.168.1.10   ← This is <PC_IP>
   Subnet Mask . . . . . . . : 255.255.255.0
   Default Gateway . . . . . : 192.168.1.1
```

Your **broadcast IP** = replace the last octet with `255` → `192.168.1.255`

### Step 1.2 — Open Windows Firewall (run once, as Administrator)

The Pi needs to reach your PC on TCP port 5050. By default Windows Defender blocks this.

Open PowerShell **as Administrator** and run:
```powershell
New-NetFirewallRule -DisplayName "SYNAPSE Command Centre TCP" `
    -Direction Inbound -Protocol TCP -LocalPort 5050 -Action Allow

New-NetFirewallRule -DisplayName "SYNAPSE Discovery UDP" `
    -Direction Inbound -Protocol UDP -LocalPort 5997 -Action Allow
```

Verify the rule is active:
```powershell
Get-NetFirewallRule -DisplayName "SYNAPSE Command Centre TCP" | Select-Object Enabled
# Should print: Enabled = True
```

### Step 1.3 — Find your Pi's IP address

After connecting the Pi to your network, find its IP from your router's admin page, or run on the Pi:
```bash
hostname -I
# Example: 192.168.1.50
```

> **Tip:** Assign the Pi a static IP so it doesn't change on reboot (see Appendix A).

---

## Part 2 — Set Up the Raspberry Pi

### Step 2.1 — Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Hardware | Raspberry Pi 3B+ | Raspberry Pi 4B (4GB) |
| OS | Raspberry Pi OS Bullseye 64-bit | Raspberry Pi OS Bookworm 64-bit |
| Python | 3.10 | 3.11 or 3.12 |
| Storage | 8 GB SD card | 16+ GB SD card |
| Network | Wi-Fi or Ethernet | Ethernet (more reliable) |

Enable SSH before booting: in Raspberry Pi Imager → Advanced Options → Enable SSH.

### Step 2.2 — SSH into the Pi

From your Windows PC (PowerShell):
```powershell
ssh pi@192.168.1.50
# Default password: raspberry (change it after first login)
```

### Step 2.3 — Get the SYNAPSE code onto the Pi

**Option A — Git clone directly on the Pi (simplest):**
```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Ghadyalpatil/Synapse.git /opt/synapse
cd /opt/synapse
git checkout nishant
```

**Option B — Copy from your PC with rsync:**
```powershell
# Run this in PowerShell on your PC (Git Bash / WSL)
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='var/' `
    "c:\Users\admin\setup\SYNAPSE COMMUNICATION/" `
    pi@192.168.1.50:/opt/synapse/
```

**Option C — Copy with scp:**
```powershell
scp -r "c:\Users\admin\setup\SYNAPSE COMMUNICATION" pi@192.168.1.50:/opt/synapse
```

### Step 2.4 — Run the One-Command Setup Script

This script installs all dependencies, creates directories, generates crypto keys, and installs the systemd service.

```bash
cd /opt/synapse
sudo bash deploy/scripts/setup_pi.sh SYNAPSE-PI-001 192.168.1.255
#                                      ^node-id        ^broadcast IP of your LAN
```

> Use a unique node ID for every Pi you deploy (e.g. `SYNAPSE-PI-001`, `SYNAPSE-PI-002`).

The script will print a summary when done:
```
============================================================
 SYNAPSE setup complete for node [SYNAPSE-PI-001]

 Configuration : /etc/synapse/node.env
 Keys          : /etc/synapse/keys
 Data          : /var/lib/synapse/data
 Logs          : journalctl -u synapse-node -f

 Start  : sudo systemctl start synapse-node
 Status : sudo systemctl status synapse-node
============================================================
```

---

## Part 3 — Connect the Pi to the Command Centre

### Step 3.1 — Configure the Command Centre peer address

This is the most important step. You must tell the Pi **where your PC is on the LAN**.

Edit the systemd service:
```bash
sudo nano /etc/systemd/system/synapse-node.service
```

Find the `ExecStart=` block and replace `<PC_IP>` with your actual PC IP:
```ini
ExecStart=/usr/bin/python3 -m synapse \
    --auto-poll 3.0 \
    --stream-telemetry \
    --telemetry-target COMMAND-CENTER \
    --peer COMMAND-CENTER@192.168.1.10:5050 \
    --db-path /var/lib/synapse/data/node.db \
    --keys-dir /etc/synapse/keys
```

Also confirm the environment variables in the same file match your network:
```ini
Environment=SYNAPSE_NODE_ID=SYNAPSE-PI-001
Environment=SYNAPSE_BROADCAST_IP=192.168.1.255
```

Reload and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable synapse-node   # auto-start on reboot
sudo systemctl start synapse-node
```

### Step 3.2 — Edit `/etc/synapse/node.env` (alternative config method)

Instead of editing the service file directly, you can set all config in `/etc/synapse/node.env`:
```bash
sudo nano /etc/synapse/node.env
```

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

Then restart:
```bash
sudo systemctl restart synapse-node
```

---

## Part 4 — Start the Command Centre on Your PC

### Step 4.1 — Using the batch script (easiest)

Double-click or run in PowerShell:
```powershell
cd "c:\Users\admin\setup\SYNAPSE COMMUNICATION"
.\run_command_center.ps1
```

Or the batch version:
```cmd
run_command_center.bat
```

### Step 4.2 — Manual launch with Pi peer registered

```powershell
python command_center.py `
    --node-id    COMMAND-CENTER `
    --comm-port  5050 `
    --disc-port  5997 `
    --port       9000 `
    --broadcast-ip 192.168.1.255 `
    --peer       SYNAPSE-PI-001@192.168.1.50:5000 `
    --db-path    var/data/command_center.db `
    --keys-dir   var/keys/command_center `
    --open-browser `
    --log-level  INFO
```

> Add `--peer SYNAPSE-PI-002@192.168.1.51:5000` for a second Pi, and so on.

The browser will open **http://localhost:9000** automatically.

---

## Part 5 — Verify the Connection

### Step 5.1 — Check Pi logs (live)
```bash
sudo journalctl -u synapse-node -f
```

**Success** — you should see every ~3 seconds:
```
[CommManager] Sent MSG-XXXXXXXX (SENSOR_DATA) -> COMMAND-CENTER  (Delivered: ['COMMAND-CENTER'])
```

**Failure** — if you see this, the PC firewall is blocking port 5050:
```
[CommManager] QUEUED_STORE_AND_FORWARD: COMMAND-CENTER (No reachable path)
```
→ Fix: re-run the firewall rule from Step 1.2.

### Step 5.2 — Check the Command Centre dashboard

Open your browser to:

| URL | What to check |
|---|---|
| `http://localhost:9000` | Sensor Matrix tab — see live SYNAPSE-PI-001 cards |
| `http://localhost:9000/api/status` | `"total_sensors_reporting": 3` |
| `http://localhost:9000/api/sensors/latest` | Thermal / acoustic / motion readings from the Pi |
| `http://localhost:9000/api/nodes` | Pi node shown as `ONLINE` |

### Step 5.3 — Check the Pi's own local API
```
http://192.168.1.50:8080/api/status
```

### Step 5.4 — Connectivity test from the Pi
```bash
# Can the Pi reach the PC?
ping 192.168.1.10

# Is port 5050 open on the PC?
nc -zv 192.168.1.10 5050
# Should print: Connection to 192.168.1.10 5050 port [tcp/*] succeeded!
```

---

## Part 6 — Multiple Pis (Expanding the Mesh)

Each additional Pi is the same process. Use a different node ID and, optionally, a different API port.

### Pi #2 setup
```bash
sudo bash deploy/scripts/setup_pi.sh SYNAPSE-PI-002 192.168.1.255
```

Edit `/etc/systemd/system/synapse-node.service` on Pi #2:
```ini
Environment=SYNAPSE_NODE_ID=SYNAPSE-PI-002
ExecStart=/usr/bin/python3 -m synapse \
    --auto-poll 3.0 \
    --stream-telemetry \
    --telemetry-target COMMAND-CENTER \
    --peer COMMAND-CENTER@192.168.1.10:5050 \
    --peer SYNAPSE-PI-001@192.168.1.50:5000 \
    --db-path /var/lib/synapse/data/node.db \
    --keys-dir /etc/synapse/keys
```

> Adding `--peer SYNAPSE-PI-001@...` lets the two Pis communicate directly with each other, not just through the Command Centre.

### Command Centre launch with two Pis
```powershell
python command_center.py `
    --node-id COMMAND-CENTER `
    --comm-port 5050 `
    --broadcast-ip 192.168.1.255 `
    --peer SYNAPSE-PI-001@192.168.1.50:5000 `
    --peer SYNAPSE-PI-002@192.168.1.51:5000 `
    --port 9000 --open-browser
```

---

## Service Management Quick Reference

```bash
# Start / Stop / Restart
sudo systemctl start   synapse-node
sudo systemctl stop    synapse-node
sudo systemctl restart synapse-node

# Enable / Disable auto-start on boot
sudo systemctl enable  synapse-node
sudo systemctl disable synapse-node

# Check service status
sudo systemctl status  synapse-node

# Live logs (Ctrl+C to exit)
sudo journalctl -u synapse-node -f

# Last 100 log lines
sudo journalctl -u synapse-node -n 100 --no-pager

# Manual run for debugging (runs in foreground, shows all output)
cd /opt/synapse
python3 -m synapse \
  --node-id SYNAPSE-PI-001 \
  --auto-poll 3.0 \
  --stream-telemetry \
  --telemetry-target COMMAND-CENTER \
  --peer COMMAND-CENTER@192.168.1.10:5050 \
  --log-level DEBUG
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard empty / no sensors | Firewall blocking port 5050 | Run the firewall rule in Step 1.2 as Administrator |
| `QUEUED_STORE_AND_FORWARD` in Pi logs | Pi can't reach PC | Check firewall; ping PC from Pi |
| `Connection refused` on Pi | Command Centre not running | Start `run_command_center.ps1` first, then start Pi service |
| Node shows OFFLINE on dashboard | Heartbeat packets not arriving | Both on same subnet? Check broadcast IP matches LAN |
| Two Pis appear as one | Same node ID on both | Use unique `--node-id` per Pi |
| `pynacl` install fails | Missing libsodium | `sudo apt install libsodium-dev` then retry setup |
| Python version error | Pi has Python < 3.10 | `sudo apt install python3.11` |
| Sensor data arrives but is random | Simulated sensors active | Expected for demo; replace with real HAL drivers for production |

---

## Appendix A — Assign a Static IP to the Pi

Prevents the Pi's IP from changing after reboot.

```bash
sudo nano /etc/dhcpcd.conf
```

Add at the bottom:
```
interface wlan0          # use eth0 if on Ethernet
static ip_address=192.168.1.50/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

Apply:
```bash
sudo reboot
```

After reboot, verify:
```bash
hostname -I
# Should print: 192.168.1.50
```

---

## Appendix B — Port Reference

| Node | Protocol | Port | Purpose |
|---|---|---|---|
| Raspberry Pi | TCP | 5000 | SYNAPSE mesh — receives messages from peers |
| Raspberry Pi | UDP | 5999 | Discovery beacons |
| Raspberry Pi | TCP | 8080 | Local REST API / mini dashboard |
| Command Centre (PC) | TCP | 5050 | SYNAPSE mesh — receives sensor data from Pis |
| Command Centre (PC) | UDP | 5997 | Discovery beacons |
| Command Centre (PC) | TCP | 9000 | Web dashboard (browser) |

---

## Appendix C — Sensor Data Flow

```
Pi GPIO / USB sensors
        ↓
SensorManager.sample_all()   (every 3 seconds)
        ↓
EventEngine.broadcast_sensor_telemetry()
        ↓
TYPE_SENSOR_DATA message  (Ed25519 signed, 4-byte length-prefixed TCP frame)
        ↓
CommunicationManager → TcpTransportClient
        ↓
TCP connect → 192.168.1.10:5050  (Command Centre)
        ↓
Command Centre handle_incoming_message()
        ↓  saves to SQLite        ↓  fires WebSocket push
Browser dashboard ← live update  (< 1 second latency)
```

If the network drops mid-delivery, the message is saved to the Pi's local SQLite database and retried automatically every 6 seconds until delivery succeeds.
