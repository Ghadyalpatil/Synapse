# Real-Hardware Deployment Audit
Will the code work on actual Raspberry Pi + LAN? — Honest answer.

---

## TL;DR

> **The communication system will work correctly on real hardware.**
> The networking layer, TCP framing, cryptography, store-and-forward, and Command Centre dashboard are all real-hardware ready. Three things need attention before your first live deployment.

---

## ✅ What Will Work Without Any Changes

### 1. TCP Communication Layer — ✅ Ready
The TCP server binds to `0.0.0.0` (all interfaces), not `127.0.0.1`.

```python
# transport.py — line 58-62
self.tcp_server = TcpTransportServer(
    host="0.0.0.0",      # ← listens on ALL network interfaces
    port=self.comm_port,
    message_handler=self.handle_incoming_message
)
```
When deployed on the Pi, any device on the LAN can connect to it on port 5000.  
The Command Centre similarly binds `0.0.0.0:5050` — reachable from the Pi.

---

### 2. Static Peer Registration — ✅ Ready
The `--peer COMMAND-CENTER@<PC_IP>:5050` flag registers the PC's IP at startup.
The node will **immediately attempt to deliver** sensor data to that address without needing UDP discovery to work first.

```python
# __main__.py — peer registration loop
p_ip, p_port = p_addr.split(":")
comm_manager.node_manager.register_peer(p_id, p_ip, int(p_port))
```
This is the correct way to connect Pi ↔ PC across a real LAN.

---

### 3. Store-and-Forward Queue — ✅ Ready
If the Wi-Fi drops mid-transmission, packets are queued to SQLite and retried every 6s automatically. The Pi continues sampling sensors during an outage and delivers buffered data when the link recovers.

---

### 4. Ed25519 Cryptography — ✅ Ready
Keys are generated on first run and stored in `--keys-dir`. Trust-On-First-Use (TOFU) is implemented — the Pi and Command Centre exchange verify keys on the first message. Works the same on real hardware.

---

### 5. UDP Discovery — ✅ Ready (bonus feature)
Even without `--peer`, the UDP discovery service broadcasts on the LAN subnet so nodes auto-discover each other. It also sends link-local multicast (`224.0.0.251`) for direct Ethernet cables with no router.

---

## ⚠️ Things That Need Attention

### Issue 1 — Windows Firewall Will Block Port 5050
**Impact: HIGH — Pi cannot reach Command Centre at all**

Windows Defender Firewall blocks inbound TCP connections by default. When the Pi tries `connect(PC_IP, 5050)` it will get `Connection refused` and fall to store-and-forward queue.

**Fix — Run once in PowerShell (as Administrator):**
```powershell
New-NetFirewallRule -DisplayName "SYNAPSE Command Centre" `
    -Direction Inbound -Protocol TCP -LocalPort 5050 -Action Allow

New-NetFirewallRule -DisplayName "SYNAPSE Discovery" `
    -Direction Inbound -Protocol UDP -LocalPort 5997 -Action Allow
```
After this, the Pi can reach the PC.

---

### Issue 2 — Sensors Are Simulated (Random Data)
**Impact: MEDIUM — System works end-to-end, but values are fake**

The `SensorManager` auto-registers three **simulated** sensors that generate random numbers:

```python
# sensor_engine.py — lines 96-99
def __init__(self):
    self.sensors: Dict[str, BaseSensor] = {}
    self.register_sensor(SimulatedThermalSensor("TH-01"))   # random temp
    self.register_sensor(SimulatedAcousticSensor("AC-01"))  # random dB
    self.register_sensor(SimulatedMotionSensor("MO-01"))    # random motion
```

For a **demonstration** this is fine — real-looking data streams to the Command Centre dashboard.  
For production, you replace these with real GPIO/hardware drivers (see below).

**HAL is pluggable** — `BaseSensor` is an abstract class. Adding a real sensor:
```python
# Example: replace simulated thermal with real MLX90640 thermal camera
from your_sensor_library import MLX90640

class RealThermalSensor(BaseSensor):
    def __init__(self):
        super().__init__("TH-01", "thermal")
        self.cam = MLX90640()   # init real hardware

    def sample(self) -> Dict[str, Any]:
        frame = self.cam.read_frame()
        max_temp = max(frame)
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "temperature_celsius": round(max_temp, 1),
            "target_detected": max_temp > 34.0,
            "confidence": 0.9 if max_temp > 34.0 else 0.1,
            "timestamp": time.time()
        }
```
Then register it in `sensor_engine.py`'s `SensorManager.__init__`.

---

### Issue 3 — Node ID Collision if You Deploy Two Identical Pis
**Impact: LOW — Both nodes appear as one on the dashboard**

Each Pi **must** have a unique `--node-id`. If two Pis both run with `SYNAPSE-001`, the Command Centre sees only one node.

**Fix — pass a different ID to each Pi's setup script:**
```bash
# Pi 1:
sudo bash deploy/scripts/setup_pi.sh SYNAPSE-PI-001 192.168.1.255

# Pi 2:
sudo bash deploy/scripts/setup_pi.sh SYNAPSE-PI-002 192.168.1.255
```
And register both from the Command Centre side:
```powershell
python command_center.py ... `
    --peer SYNAPSE-PI-001@192.168.1.50:5000 `
    --peer SYNAPSE-PI-002@192.168.1.51:5000
```

---

## Network Diagram (Real Deployment)

```
192.168.1.0/24 LAN (Wi-Fi router or Ethernet switch)
│
├── 192.168.1.10  Windows PC
│     └── python command_center.py
│           TCP  :5050  ← receives sensor data from Pi(s)
│           UDP  :5997  ← discovery beacons
│           Web  :9000  → http://localhost:9000
│
├── 192.168.1.50  Raspberry Pi #1  (SYNAPSE-PI-001)
│     └── python -m synapse --stream-telemetry
│           TCP  :5000  ← heartbeats, commands from C2
│           UDP  :5999  ← discovery beacons
│           Web  :8080  → http://192.168.1.50:8080
│
└── 192.168.1.51  Raspberry Pi #2  (SYNAPSE-PI-002)
      └── python -m synapse --stream-telemetry
            TCP  :5001  (use different port or same port on different IP)
```

> [!NOTE]
> Two Pis on the same LAN can each use port 5000 because they are on **different IP addresses**. Ports only conflict on the same machine.

---

## Pre-Flight Checklist

| # | Check | How to verify |
|---|---|---|
| 1 | Both devices on same LAN subnet | `ping <PI_IP>` from PC returns replies |
| 2 | Windows Firewall rule added for TCP 5050 | `Test-NetConnection -ComputerName <PC_IP> -Port 5050` from Pi |
| 3 | Pi has correct `--peer COMMAND-CENTER@<PC_IP>:5050` | Pi logs show `Sent SENSOR_DATA -> COMMAND-CENTER (Delivered: ['COMMAND-CENTER'])` |
| 4 | Command Centre has correct `--peer SYNAPSE-PI-001@<PI_IP>:5000` | C2 Mesh Topology tab shows node as ONLINE |
| 5 | Each Pi has unique `--node-id` | Dashboard Sensor Matrix shows separate node filter chips |
| 6 | Broadcast IP matches your subnet | IP ends in `.255` for your actual subnet |

---

## Summary Table

| Component | Status on Real Hardware |
|---|---|
| TCP framing + delivery | ✅ Works — binds `0.0.0.0` |
| UDP peer discovery | ✅ Works — broadcasts on LAN subnet |
| Ed25519 crypto + key exchange | ✅ Works — file-based, Pi persistent |
| Store-and-forward recovery | ✅ Works — SQLite on Pi's SD card |
| Command Centre WebSocket dashboard | ✅ Works — browser on PC |
| Sensor data (thermal/acoustic/motion) | ⚠️ Simulated values — real driver needed for production |
| Windows Firewall port 5050 | ⚠️ Must open manually (one-time) |
| Node ID uniqueness | ⚠️ Must use different `--node-id` per Pi |
