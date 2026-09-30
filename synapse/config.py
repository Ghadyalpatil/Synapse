"""
SYNAPSE — Node Configuration
Configurable via environment variables or command-line flags.
Defaults are tailored for Raspberry Pi local-grid deployments.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = BASE_DIR / "var"
DATA_DIR = Path(os.environ.get("SYNAPSE_DATA_DIR", VAR_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

KEYS_DIR = Path(os.environ.get("SYNAPSE_KEYS_DIR", VAR_DIR / "keys"))
KEYS_DIR.mkdir(parents=True, exist_ok=True)

# Node Identity
NODE_ID: str = os.environ.get("SYNAPSE_NODE_ID", "SYNAPSE-001")

# Networking Configuration
LISTEN_HOST: str = os.environ.get("SYNAPSE_LISTEN_HOST", "0.0.0.0")
COMMUNICATION_PORT: int = int(os.environ.get("SYNAPSE_COMM_PORT", 5000))
DISCOVERY_PORT: int = int(os.environ.get("SYNAPSE_DISCOVERY_PORT", 5999))
BROADCAST_IP: str = os.environ.get("SYNAPSE_BROADCAST_IP", "255.255.255.255")

# Local API & Web Dashboard Port
API_PORT: int = int(os.environ.get("SYNAPSE_API_PORT", 8080))

# Heartbeat & Failure Detection Timers (in seconds)
HEARTBEAT_INTERVAL: float = float(os.environ.get("SYNAPSE_HEARTBEAT_INTERVAL", 5.0))
UNRESPONSIVE_TIMEOUT: float = float(os.environ.get("SYNAPSE_UNRESPONSIVE_TIMEOUT", 12.0))
HEARTBEAT_TIMEOUT: float = float(os.environ.get("SYNAPSE_HEARTBEAT_TIMEOUT", 25.0))

# Store-and-Forward Configuration
STORE_FORWARD_RETRY_INTERVAL: float = float(os.environ.get("SYNAPSE_RETRY_INTERVAL", 6.0))
MAX_OUTBOX_RETRIES: int = int(os.environ.get("SYNAPSE_MAX_RETRIES", 100))

# Protocol & Routing
DEFAULT_TTL: int = int(os.environ.get("SYNAPSE_DEFAULT_TTL", 5))
SOCKET_TIMEOUT: float = float(os.environ.get("SYNAPSE_SOCKET_TIMEOUT", 4.0))

# Local SQLite Database
DATABASE_PATH: Path = Path(os.environ.get("SYNAPSE_DB_PATH", DATA_DIR / f"{NODE_ID.lower()}_local.db"))

# Logging
LOG_LEVEL: str = os.environ.get("SYNAPSE_LOG_LEVEL", "INFO")
