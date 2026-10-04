# Synapse — Edge AI & Embedded Intelligence

> Prototype 01 · Technology flagship

Multi-modal sensor fusion nodes that see, hear and sense simultaneously —
making real-time AI decisions at the edge with zero cloud dependency.

One hardware platform reconfigured for six application domains through modular
sensor payloads and domain-specific inference heads sharing a common
feature-extraction backbone.

## Layout

```
synaps/
├── firmware/   Sensor interfacing, payload drivers, PCB carrier control
├── ml/         Fusion backbone, cross-modal attention, domain heads
├── docs/       Architecture notes, benchmarks, design decisions
└── data/       Dataset configs only — never raw data (see .gitignore)
```

## Platform

| | |
|---|---|
| **Compute** | Jetson Orin Nano Super · 8 GB LPDDR5 · 67 TOPS INT8 |
| **OS** | JetPack SDK · CUDA · cuDNN · TensorRT |
| **Stack** | PyTorch · TF Lite · ONNX Runtime · ROS 2 |

## Architecture

The innovation is the fusion architecture, not the sensor selection.

```
Sensor streams → Shared CNN backbone → Cross-modal attention → Domain heads
```

A shared convolutional backbone extracts modality-agnostic embeddings from each
sensor stream. A cross-modal attention layer learns to weight each modality's
contribution dynamically, per inference. Domain-specific heads sit on top, so
one deployment is re-tasked with minimal retraining.

Precedent exists in the literature (multi-modal transformers, ViLBERT,
Perceiver IO), but with no known deployment on a low-cost edge platform for
these domains. Novelty lies in the deployment context and optimisation for a
67-TOPS envelope. A patent filing is planned following this academic year.

## Application domains

| Domain | Payload |
|---|---|
| Defence & Security | Thermal · LWIR · low-light CMOS · acoustic array |
| Agriculture | Multispectral · soil moisture & NPK · ambient |
| Industrial Safety | MQ-series gas · thermal · vibration · worker vision |
| Environment | PM2.5 / PM10 · VOC · pH & TDS · acoustic |
| Smart Cities | RGB camera · LiDAR (optional) · traffic-flow |
| Cross-domain R&D | Common feature core · pluggable heads |

## Deliverables

- [ ] Working prototype hardware with at least two swappable sensor payloads (defence and agriculture)
- [ ] Trained baseline models for both domains, field-demonstrable on a curated in-house test set
- [ ] Documented cross-modal attention architecture, benchmarked against a single-modality baseline
- [ ] First-iteration custom PCB carrier for sensor interfacing and power management

## Setup

<!-- TODO: fill in once the toolchain is pinned -->
```bash
cd synaps/ml
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Weights and datasets are not in this repo.** See [`data/README.md`](data/README.md).

---

## Edge Grid Communication & Mesh Network (Branch `nishant`)

SYNAPSE includes a zero-cloud, resilient local-grid mesh communication subsystem designed for autonomous surveillance edge nodes (Raspberry Pi / Jetson).

### Layered Architecture

```
Layer 10: Local FastAPI Server, Tactical Web Dashboard, Node CLI & Integration Test Grid
Layer 9 : Multi-Modal Sensor Subsystem (Thermal, Acoustic, Motion) & Threat Event Pipeline
Layer 8 : Master Communication Orchestrator (CommunicationManager)
Layer 7 : Loop-Free Hop Router & Persistent Store-and-Forward Outbox
Layer 6 : Heartbeat Link Watchdog & Node State Machine (ONLINE / UNRESPONSIVE / OFFLINE)
Layer 5 : Peer Topology Management & Autonomous UDP Discovery
Layer 4 : Reliable Async TCP Transport with Framed Delivery ACKs
Layer 3 : Cryptographic Identity, Ed25519 Signing, Curve25519 Box & Replay Defense
Layer 2 : Big-Endian Length-Prefixed Binary Framing & SynapseMessage Protocol
Layer 1 : Centralized Config, SQLite Persistence with WAL Mode & Outbox Queue
```

### Running a Local Node

```bash
# Install dependencies
pip install -r requirements.txt

# Run node entrypoint
python main.py --node-id SYNAPSE-001 --comm-port 5000 --discovery-port 5999 --api-port 8080

# Access tactical web dashboard
open http://127.0.0.1:8080
```

### Operator CLI

```bash
# Check local node status
python cli.py status

# Inspect known grid peers and route scores
python cli.py nodes

# View surveillance events and active alerts
python cli.py events
python cli.py alerts

# Trigger a simulated multi-modal threat
python cli.py trigger --type thermal --confidence 0.95
```

### Tactical Command Centre & Live Multi-Sensor Demonstration

SYNAPSE includes a dedicated **Tactical Command Centre (C2)** workstation designed to demonstrate the complete edge surveillance system. Edge modules stream all raw sensor inputs (thermal, acoustic, motion) across the independent TCP mesh grid using length-prefixed binary framing and Ed25519 signatures directly to the Command Centre.

#### One-Click Multi-Window Demonstration:
```powershell
# Launches Node 001, Node 002, and the Command Centre in separate desktop windows:
.\launch_demonstration.ps1
# Or on Windows cmd:
launch_demonstration.bat
```
The Command Centre dashboard will automatically open at `http://127.0.0.1:9000`.

#### Running Components Individually:
```bash
# Terminal 1: Edge Node 001 with sensor streaming enabled
python -m synapse --node-id SYNAPSE-001 --comm-port 5000 --api-port 8080 --peer COMMAND-CENTER@127.0.0.1:5050 --auto-poll 2.5 --stream-telemetry

# Terminal 2: Edge Node 002 with sensor streaming enabled
python -m synapse --node-id SYNAPSE-002 --comm-port 5001 --api-port 8081 --peer COMMAND-CENTER@127.0.0.1:5050 --auto-poll 3.0 --stream-telemetry

# Terminal 3: Tactical Command Centre Workstation
python command_center.py --node-id COMMAND-CENTER --comm-port 5050 --port 9000 --open-browser
```

### Running Test Suite

```bash
pytest
```

