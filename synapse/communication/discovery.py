"""
SYNAPSE — Local UDP Node Discovery
Autonomous peer discovery across the local IP network.
Zero-cloud, zero-external-dependencies.
"""

import asyncio
import json
import logging
import socket
import time
from typing import Callable, Dict, Optional

logger = logging.getLogger("synapse.discovery")


class DiscoveryProtocol(asyncio.DatagramProtocol):
    """Async UDP Protocol for sending and receiving node discovery beacons."""

    def __init__(self, node_id: str, comm_port: int, public_key: str,
                 discovery_callback: Callable[[Dict[str, any], str], None]):
        self.node_id = node_id
        self.comm_port = comm_port
        self.public_key = public_key
        self.discovery_callback = discovery_callback
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        # Enable broadcast
        sock = transport.get_extra_info("socket")
        if sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            msg = json.loads(data.decode("utf-8"))
            sender_node_id = msg.get("node_id")

            # Ignore our own discovery beacons
            if sender_node_id == self.node_id:
                return

            sender_ip = addr[0]
            self.discovery_callback(msg, sender_ip)

            # If it's a DISCOVERY query, reply with DISCOVERY_RESPONSE
            if msg.get("type") == "DISCOVERY" and self.transport:
                response = {
                    "type": "DISCOVERY_RESPONSE",
                    "node_id": self.node_id,
                    "comm_port": self.comm_port,
                    "public_key": self.public_key,
                    "timestamp": time.time()
                }
                resp_bytes = json.dumps(response).encode("utf-8")
                self.transport.sendto(resp_bytes, addr)

        except Exception as e:
            logger.debug(f"Discovery packet parsing error from {addr}: {e}")

    def error_received(self, exc: Exception):
        logger.debug(f"Discovery UDP error: {exc}")


class NodeDiscoveryService:
    """Manages UDP discovery broadcasting and listening."""

    def __init__(self, node_id: str, comm_port: int, discovery_port: int,
                 public_key: str, broadcast_ip: str,
                 on_node_discovered: Callable[[str, str, int, Optional[str]], None]):
        self.node_id = node_id
        self.comm_port = comm_port
        self.discovery_port = discovery_port
        self.public_key = public_key
        self.broadcast_ip = broadcast_ip
        self.on_node_discovered = on_node_discovered

        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[DiscoveryProtocol] = None
        self._beacon_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        """Binds the UDP socket and starts periodic discovery beacons."""
        loop = asyncio.get_running_loop()

        # Create UDP socket with SO_REUSEADDR and SO_BROADCAST
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", self.discovery_port))
        sock.setblocking(False)

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: DiscoveryProtocol(
                self.node_id,
                self.comm_port,
                self.public_key,
                self._handle_discovery_packet
            ),
            sock=sock
        )
        self._is_running = True
        self._beacon_task = asyncio.create_task(self._beacon_loop())
        logger.info(f"UDP Node Discovery listening on port {self.discovery_port}")

    async def stop(self):
        """Stops discovery service and cleans up transport."""
        self._is_running = False
        if self._beacon_task:
            self._beacon_task.cancel()
            try:
                await self._beacon_task
            except asyncio.CancelledError:
                pass
        if self._transport:
            self._transport.close()
            logger.info("UDP Node Discovery stopped.")

    def _handle_discovery_packet(self, msg: Dict[str, any], sender_ip: str):
        """Processes discovered peer details."""
        node_id = msg.get("node_id")
        comm_port = msg.get("comm_port")
        public_key = msg.get("public_key")

        if node_id and comm_port:
            logger.info(f"[Discovery] Discovered active node: {node_id} at {sender_ip}:{comm_port}")
            self.on_node_discovered(node_id, sender_ip, comm_port, public_key)

    async def broadcast_announcement(self):
        """Broadcasts a single discovery beacon immediately."""
        if not self._transport:
            return
        beacon = {
            "type": "DISCOVERY",
            "node_id": self.node_id,
            "comm_port": self.comm_port,
            "public_key": self.public_key,
            "timestamp": time.time()
        }
        data = json.dumps(beacon).encode("utf-8")
        try:
            self._transport.sendto(data, (self.broadcast_ip, self.discovery_port))
        except Exception as e:
            logger.debug(f"Broadcast beacon send failed: {e}")

    async def _beacon_loop(self):
        """Periodically broadcasts node presence."""
        while self._is_running:
            await self.broadcast_announcement()
            await asyncio.sleep(8.0)
