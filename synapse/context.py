"""
SYNAPSE — Node Application Context & Lifecycle Manager
Unified dependency container orchestrating storage, security,
networking mesh, sensor hardware/simulators, and event processing.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from synapse import config
from synapse.api.server import create_api_app
from synapse.communication.manager import CommunicationManager
from synapse.processing.event_engine import EventEngine
from synapse.sensors.sensor_engine import SensorManager
from synapse.storage.database import Database

logger = logging.getLogger("synapse.context")


@dataclass
class NodeConfig:
    """Runtime configuration profile for a SYNAPSE node."""
    node_id: str = config.NODE_ID
    listen_host: str = config.LISTEN_HOST
    comm_port: int = config.COMMUNICATION_PORT
    discovery_port: int = config.DISCOVERY_PORT
    api_port: int = config.API_PORT
    broadcast_ip: str = config.BROADCAST_IP
    db_path: Optional[Path] = None
    keys_dir: Optional[Path] = None
    heartbeat_interval: float = config.HEARTBEAT_INTERVAL
    unresponsive_timeout: float = config.UNRESPONSIVE_TIMEOUT
    heartbeat_timeout: float = config.HEARTBEAT_TIMEOUT
    retry_interval: float = config.STORE_FORWARD_RETRY_INTERVAL
    auto_poll: float = 0.0
    log_level: str = config.LOG_LEVEL


class NodeContext:
    """
    Manages the lifecycle and dependencies of a SYNAPSE edge node.
    Provides clean initialization, startup, and graceful teardown.
    """

    def __init__(self, node_config: Optional[NodeConfig] = None):
        self.config = node_config or NodeConfig()
        
        # 1. Local Database
        resolved_db_path = (
            Path(self.config.db_path)
            if self.config.db_path
            else config.DATA_DIR / f"{self.config.node_id.lower()}_local.db"
        )
        self.db = Database(resolved_db_path)

        # 2. Key / Cryptographic directory
        self.keys_dir = Path(self.config.keys_dir) if self.config.keys_dir else config.KEYS_DIR

        # 3. Communication & Mesh Network Manager
        self.comm_manager = CommunicationManager(
            node_id=self.config.node_id,
            comm_port=self.config.comm_port,
            discovery_port=self.config.discovery_port,
            broadcast_ip=self.config.broadcast_ip,
            db=self.db,
            keys_dir=self.keys_dir,
            heartbeat_interval=self.config.heartbeat_interval,
            unresponsive_timeout=self.config.unresponsive_timeout,
            heartbeat_timeout=self.config.heartbeat_timeout,
            retry_interval=self.config.retry_interval
        )

        # 4. Sensor Subsystem & Event Engine
        self.sensor_manager = SensorManager()
        self.event_engine = EventEngine(
            node_id=self.config.node_id,
            sensor_manager=self.sensor_manager,
            comm_manager=self.comm_manager,
            db=self.db
        )

        # 5. Local FastAPI Application
        self.api_app = create_api_app(self.comm_manager, self.event_engine, self.db)

        self._is_running = False

    async def start(self):
        """Sequential startup: mesh network -> sensor polling/event engine."""
        logger.info(f"Bootstrapping SYNAPSE NodeContext [{self.config.node_id}]")
        await self.comm_manager.start()
        auto_poll = self.config.auto_poll if self.config.auto_poll > 0 else None
        await self.event_engine.start(auto_poll_interval=auto_poll)
        self._is_running = True
        logger.info(f"NodeContext [{self.config.node_id}] is fully operational.")

    async def stop(self):
        """Coordinated shutdown ensuring zero message drop and cleanly stopped loops."""
        if not self._is_running:
            return
        logger.info(f"Shutting down SYNAPSE NodeContext [{self.config.node_id}]...")
        self._is_running = False
        await self.event_engine.stop()
        await self.comm_manager.stop()
        logger.info(f"NodeContext [{self.config.node_id}] successfully terminated.")
