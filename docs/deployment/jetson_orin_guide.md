# SYNAPSE — NVIDIA Jetson Orin Nano Deployment Guide

## 1. Hardware & Platform
- NVIDIA Jetson Orin Nano Developer Kit (8GB LPDDR5, 67 TOPS INT8).
- NVIDIA JetPack 5.1.2 or JetPack 6.0 (Ubuntu 22.04 LTS).
- CUDA 12.2, cuDNN 8.9, TensorRT 8.6.

## 2. Installation & Optimization

```bash
# Setup repository
git clone https://github.com/Ghadyalpatil/Synapse.git /opt/synapse
cd /opt/synapse

# Python Environment
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .

# Run with Jetson Orin environment profile
export $(cat configs/jetson_orin_node.env | xargs)
python -m synapse
```
