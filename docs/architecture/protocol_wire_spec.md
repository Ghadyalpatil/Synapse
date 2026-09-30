# SYNAPSE Protocol & Wire Specification

## 1. Framing Architecture

All TCP communication between SYNAPSE nodes utilizes a **Big-Endian Length-Prefixed Binary Frame**:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Payload Length (N)                       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                     Payload Data (N Bytes)                    +
|                       (UTF-8 Encoded JSON)                    |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

- **Header**: 4 bytes, unsigned 32-bit integer in network byte order (Big-Endian `>I`).
- **Payload**: Length $N$ bytes of UTF-8 encoded JSON.
- **Maximum Frame Size**: Configurable, default 16 MB limit to prevent memory exhaustion attacks.

## 2. Message Envelope Schema

```json
{
  "message_id": "MSG-A1B2C3D4E5F6",
  "source_node": "SYNAPSE-001",
  "destination_node": "SYNAPSE-002",
  "message_type": "ALERT",
  "priority": "P0",
  "payload": {
    "event_id": "EVT-889102",
    "threat_type": "PERIMETER_BREACH",
    "confidence": 0.96,
    "timestamp": 1727701234.56
  },
  "ttl": 5,
  "hop_count": 0,
  "route": ["SYNAPSE-001"],
  "timestamp": 1727701234.56,
  "signature": "3a8b...64-byte-hex-string..."
}
```

## 3. Prioritization & QoS

| Level | Priority | Traffic Class | Description |
| :--- | :--- | :--- | :--- |
| **P0** | Critical | Flash Override | Real-time threat alerts, perimeter breach alarms, kill-switch commands. |
| **P1** | High | Immediate | Target detections, node status transitions, routing table updates. |
| **P2** | Normal | Routine | Periodic sensor telemetry, link watchdog heartbeats, sync queries. |
