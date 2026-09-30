# SYNAPSE — Fully Air-Gapped Raspberry Pi Mesh Deployment Guide

> **No WiFi. No internet. No NTP. No cloud. No DHCP required.**  
> SYNAPSE is designed from the ground up to work autonomously on a **direct wired Ethernet mesh** between Raspberry Pi surveillance nodes.

---

## 1. Network Topology Options

SYNAPSE supports three deployment topologies, all fully air-gapped:

### Option A — Direct Ethernet Cable (2 Nodes, No Switch)
Connect two Raspberry Pi units with a **single Ethernet cable**. Uses IPv4 link-local auto-addressing (`169.254.x.x`) or manually assigned static IPs.

```
[RPi Node A] ─── Ethernet cable ─── [RPi Node B]
    192.168.10.1                        192.168.10.2
```

### Option B — Wired Mesh via Unmanaged Switch (2–12 Nodes)
Connect all nodes to a portable **unmanaged switch** in the field. No router, no internet.

```
[RPi-A]──┐
[RPi-B]──┤  NETGEAR GS305       (offline LAN only)
[RPi-C]──┘  Unmanaged Switch
              No DHCP · No Gateway
```

### Option C — WiFi Access Point (AP Mode on One Pi, No Internet)
One Raspberry Pi runs `hostapd` as a local WiFi access point. Other nodes connect to it as Wi-Fi clients. All traffic stays on-device, zero cloud.

```
[RPi-A: Access Point] ← WiFi (192.168.99.x) → [RPi-B]
                                               [RPi-C]
```

---

## 2. Static IP Setup (Required for Reliable Mesh)

**Do not rely on DHCP or link-local auto-addressing** for tactical deployments.  
Assign static IPs before the field mission using `dhcpcd` or NetworkManager.

### Via `/etc/dhcpcd.conf` (Raspberry Pi OS default)

```bash
sudo nano /etc/dhcpcd.conf
```

Append for each node (replace `eth0` with your interface, `X` with node number):

```
interface eth0
static ip_address=192.168.10.X/24
static routers=
static domain_name_servers=
noarp
```

- Node A → `192.168.10.1/24`
- Node B → `192.168.10.2/24`
- Node C → `192.168.10.3/24`
- Broadcast → `192.168.10.255`

Then reboot: `sudo reboot`

---

## 3. Node Configuration for Air-Gapped Mesh

Use the RPi profile and set the subnet broadcast address for your static network:

```bash
# Copy and customise RPi profile
cp configs/rpi_border_node.env configs/node_alpha.env
nano configs/node_alpha.env
```

Set these values per-node:

```env
SYNAPSE_NODE_ID=SYNAPSE-ALPHA
SYNAPSE_BROADCAST_IP=192.168.10.255   # Your subnet broadcast
SYNAPSE_COMM_PORT=5000
SYNAPSE_DISCOVERY_PORT=5999
SYNAPSE_API_PORT=8080
SYNAPSE_DATA_DIR=/var/lib/synapse/data
SYNAPSE_KEYS_DIR=/etc/synapse/keys
```

Run with the profile:

```bash
export $(cat configs/node_alpha.env | xargs)
python -m synapse
```

---

## 4. Clock Synchronisation Without NTP

SYNAPSE handles clock drift on air-gapped Pi nodes automatically:

### Automatic Offline Clock Correction

At startup, SYNAPSE reads `var/run/epoch_anchor.json`, which is persisted after every clean shutdown. If the current system clock is more than 60 seconds behind the last known-good timestamp (e.g. after a reboot with no RTC battery), SYNAPSE applies a forward correction offset to all message timestamps.

This means **nodes can reliably exchange messages even if their wall clocks differ by minutes**.

### Recommended: Add a Hardware RTC Module

For permanent field deployments, add a real-time clock (RTC) breakout board. Once set, it keeps time without a network:

```bash
# DS3231 RTC (connects via I2C on GPIO pins 3/5)
sudo apt install python3-smbus i2c-tools
sudo raspi-config  # Enable I2C interface
# Add to /boot/config.txt:
dtoverlay=i2c-rtc,ds3231
```

### Manual Clock Set for Air-Gapped Start

```bash
# Set date/time manually (no internet required)
sudo date -s "2026-09-30 18:30:00"
# Write to hardware RTC if fitted:
sudo hwclock -w
```

---

## 5. Firewall Rules for LAN-Only Operation

Lock down the Raspberry Pi to reject all traffic except the SYNAPSE mesh ports:

```bash
# Flush all existing rules
sudo iptables -F
sudo iptables -X

# Default policy: DROP all inbound
sudo iptables -P INPUT DROP
sudo iptables -P FORWARD DROP
sudo iptables -P OUTPUT ACCEPT

# Allow loopback
sudo iptables -A INPUT -i lo -j ACCEPT

# Allow established/related connections
sudo iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# SYNAPSE TCP Mesh Communication
sudo iptables -A INPUT -p tcp --dport 5000 -j ACCEPT

# SYNAPSE UDP Discovery
sudo iptables -A INPUT -p udp --dport 5999 -j ACCEPT

# SYNAPSE UDP Discovery multicast (link-local, no-router fallback)
sudo iptables -A INPUT -p udp -d 224.0.0.251 --dport 5999 -j ACCEPT

# SYNAPSE Tactical Web Dashboard (localhost only)
sudo iptables -A INPUT -p tcp --dport 8080 -s 127.0.0.1 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -s 192.168.10.0/24 -j ACCEPT

# Make persistent
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

---

## 6. Running as a System Service (Auto-Start on Boot)

```bash
# Deploy systemd service
sudo cp deploy/systemd/synapse-node.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable synapse-node.service
sudo systemctl start synapse-node.service

# Verify it's running
sudo systemctl status synapse-node.service
```

---

## 7. Verify the Air-Gapped Mesh is Working

```bash
# Check local node status via CLI
python cli.py status

# List discovered grid peers
python cli.py nodes

# View surveillance events
python cli.py events

# Simulate a threat detection event
python cli.py trigger --type thermal --confidence 0.97

# Verify the tactical dashboard is serving (operator device only)
curl http://192.168.10.1:8080/api/status
```

---

## 8. Offline Installation (No pip / internet on field nodes)

Pre-download packages on a machine with internet and transfer via USB:

```bash
# On internet-connected machine:
pip download -r requirements.txt -d ./offline_packages/
# Transfer offline_packages/ to RPi via USB stick

# On air-gapped RPi:
pip install --no-index --find-links=./offline_packages/ -r requirements.txt
```

---

## 9. Removing All Internet Access (Network Hardening)

```bash
# Disable WiFi
sudo rfkill block wifi

# Disable Bluetooth
sudo rfkill block bluetooth

# Prevent systemd-resolved from trying external DNS
sudo systemctl disable systemd-resolved
sudo systemctl stop systemd-resolved

# Remove default gateway (no internet routing possible)
sudo ip route del default 2>/dev/null || true
```

After these steps, the node will only communicate on the local `192.168.10.x/24` subnet through SYNAPSE's encrypted mesh.
