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
