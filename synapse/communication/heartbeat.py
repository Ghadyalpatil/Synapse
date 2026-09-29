"""
SYNAPSE — Heartbeat & Failure Detection Subsystem
Proactively probes known grid nodes, transitions state machine
(ONLINE -> UNRESPONSIVE -> OFFLINE), and signals recovery to store-and-forward.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

from .node_manager import (
    NodeManager,
    STATUS_ONLINE,
    STATUS_UNRESPONSIVE,
    STATUS_OFFLINE
)
from .transport import TcpTransportClient

logger = logging.getLogger("synapse.heartbeat")


class HeartbeatWatchdog:
    """Probes grid peers, tracks latency/packet loss, and triggers outbox flush on recovery."""

    def __init__(self, node_manager: NodeManager,
                 tcp_client: TcpTransportClient,
                 interval: float = 5.0,
                 unresponsive_timeout: float = 12.0,
                 heartbeat_timeout: float = 25.0,
                 on_node_recovered: Optional[Callable[[str], None]] = None):
        self.node_manager = node_manager
        self.tcp_client = tcp_client
        self.interval = interval
        self.unresponsive_timeout = unresponsive_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.on_node_recovered = on_node_recovered

        self._task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        """Starts the heartbeat probe loop."""
        self._is_running = True
        self._task = asyncio.create_task(self._probe_loop())
        logger.info(f"Heartbeat watchdog active (interval={self.interval}s, timeout={self.heartbeat_timeout}s)")

    async def stop(self):
        """Stops the heartbeat probe loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Heartbeat watchdog stopped.")

    async def _probe_loop(self):
        """Main periodic probe loop."""
        while self._is_running:
            peers = self.node_manager.get_all_peers()
            now = time.time()
            recovered_nodes = []

            for node_id, peer in list(peers.items()):
                ip = peer["ip"]
                port = peer["port"]
                current_status = peer.get("status")
                last_seen = peer.get("last_seen") or 0.0

                # Perform probe
                is_alive, latency_ms = await self.tcp_client.ping_probe(ip, port, timeout=2.0)
                self.node_manager.record_attempt(node_id, is_alive, latency_ms)

                if is_alive:
                    if current_status != STATUS_ONLINE:
                        logger.info(f"[Watchdog] Node {node_id} RECOVERED -> ONLINE (latency: {latency_ms}ms)")
                        self.node_manager.set_status(node_id, STATUS_ONLINE)
                        recovered_nodes.append(node_id)
                else:
                    elapsed = now - last_seen
                    if elapsed >= self.heartbeat_timeout:
                        if current_status != STATUS_OFFLINE:
                            logger.warning(f"[Watchdog] Node {node_id} timed out ({elapsed:.1f}s) -> OFFLINE")
                            self.node_manager.set_status(node_id, STATUS_OFFLINE)
                    elif elapsed >= self.unresponsive_timeout:
                        if current_status == STATUS_ONLINE:
                            logger.warning(f"[Watchdog] Node {node_id} unresponsive ({elapsed:.1f}s) -> UNRESPONSIVE")
                            self.node_manager.set_status(node_id, STATUS_UNRESPONSIVE)

            # If any nodes recovered, trigger immediate outbox retry
            for rec_nid in recovered_nodes:
                if self.on_node_recovered:
                    try:
                        self.on_node_recovered(rec_nid)
                    except Exception as e:
                        logger.error(f"Error in on_node_recovered callback: {e}")

            await asyncio.sleep(self.interval)
