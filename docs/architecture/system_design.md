# SYNAPSE Architecture & System Design Specification

## 1. Overview & Operational Model

SYNAPSE is an autonomous, zero-cloud edge intelligence and resilient mesh communication platform designed for tactical surveillance outposts. It operates entirely off-grid without satellite uplinks or cloud dependencies.

```
┌────────────────────────────────────────────────────────┐
│                   TACTICAL OPERATOR                    │
│   FastAPI Web UI Dashboard    │    Operator CLI        │
└───────────────────────────┬────────────────────────────┘
                            │ REST / WebSocket / Local IPC
┌───────────────────────────▼────────────────────────────┐
│                  SYNAPSE NODE CONTEXT                  │
│       Lifecycle Manager  │   Dependency Container      │
├───────────────────────────┬────────────────────────────┤
│ 1. Perception & Fusion    │ 4. Resilient Mesh Grid     │
│    - Sensor Drivers & HAL │    - Autonomous Discovery  │
│    - Multi-modal Fusion   │    - Dynamic Hop Router    │
│    - Event Threat Engine  │    - Store-and-Forward Q   │
├───────────────────────────┼────────────────────────────┤
│ 2. Cryptographic Defense  │ 5. Local Storage           │
│    - Ed25519 Signatures   │    - SQLite 3 (WAL Mode)   │
│    - Curve25519 Encryption│    - Outbox & Event Logs   │
│    - Replay Defense Ring  │                            │
└───────────────────────────┴────────────────────────────┘
```

## 2. Subsystem Specifications

### 2.1 Hardware Abstraction Layer (HAL) & Drivers
Located in `synapse/hal/` and `synapse/sensors/`:
- Interfaces with thermal imagers (FLIR Lepton, MLX90640), acoustic arrays (I2S MEMS), and motion sensors.
- Standardized `sample()` interface returning normalized telemetry payloads with confidence scores and timestamps.

### 2.2 Intelligence & Multi-Modal Sensor Fusion
Located in `synapse/ml/`:
- Convolutional/Transformer embedding backbones extracting modality-agnostic latent vectors.
- Cross-modal attention dynamically weighting reliable sensors under degraded conditions (e.g. fog, darkness, acoustic interference).
- Domain classification heads tailored for border security, perimeter defense, or smart infrastructure.

### 2.3 Event Engine & Threat Assessment
Located in `synapse/processing/`:
- Threshold evaluation rules mapping multi-sensor readings to threat levels (`P0`, `P1`, `P2`).
- Deduplication and spatial correlation preventing alert storms.
- Direct persistence to local SQLite WAL database and dispatch to the communication mesh router.

### 2.4 Resilient Mesh Network
Located in `synapse/network/` and `synapse/communication/`:
- **Discovery**: UDP broadcast beacons on port 5999 for automated zero-config neighbor discovery.
- **Transport**: Asynchronous TCP connections on port 5000 with Big-Endian 4-byte length-prefixed binary framing.
- **Routing**: Distance-vector and latency-scored loop-free hop routing.
- **Store-and-Forward**: Outbox table in SQLite preserving undelivered frames with exponential backoff retries when nodes become partitioned.
- **Security**: Ed25519 digital signatures on every packet, Curve25519 sealed box encryption for sensitive payloads, and 60-second replay attack defenses.

### 2.5 Storage Tier
Located in `synapse/storage/`:
- SQLite WAL mode for high concurrency between sensor polling, network IO, and web dashboard reads.
- Tables: `nodes`, `events`, `alerts`, `outbox`.

### 2.6 Gateway & Operator Telemetry
Located in `synapse/gateway/` and `synapse/api/`:
- FastAPI server serving real-time REST endpoints and WebSocket telemetry.
- Embedded tactical dashboard (HTML/CSS/JS) with live node topology, threat event streams, and trigger simulations.
