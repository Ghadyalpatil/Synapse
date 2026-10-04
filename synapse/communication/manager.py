"""
SYNAPSE — Master Communication Manager
High-level orchestrator unifying TCP transport, UDP discovery,
heartbeat watchdog, store-and-forward outbox, cryptographic security,
and local grid routing.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .discovery import NodeDiscoveryService
from .heartbeat import HeartbeatWatchdog
from .node_manager import NodeManager, STATUS_ONLINE
from .protocol import (
    SynapseMessage,
    TYPE_ALERT,
    TYPE_COMMAND,
    TYPE_HEARTBEAT,
    TYPE_SENSOR_DATA,
    TYPE_SYNC_REQUEST,
    TYPE_TARGET_DETECTED
)
from synapse import clock as _clock
from .queue_manager import QueueManager
from .router import MessageRouter
from .security import SecurityManager
from .transport import TcpTransportClient, TcpTransportServer
from ..storage.database import Database

logger = logging.getLogger("synapse.comm_manager")


class CommunicationManager:
    """Master communication controller for a SYNAPSE Raspberry Pi surveillance node."""

    def __init__(self, node_id: str, comm_port: int, discovery_port: int,
                 broadcast_ip: str, db: Database, keys_dir: Any,
                 heartbeat_interval: float = 5.0,
                 unresponsive_timeout: float = 12.0,
                 heartbeat_timeout: float = 25.0,
                 retry_interval: float = 6.0):
        self.node_id = node_id
        self.comm_port = comm_port
        self.discovery_port = discovery_port
        self.broadcast_ip = broadcast_ip
        self.db = db

        # 1. Security Subsystem
        self.security = SecurityManager(self.node_id, keys_dir)

        # 2. Node Manager (Grid Topology)
        self.node_manager = NodeManager(self.node_id, self.db)

        # 3. Transport Subsystem
        self.tcp_client = TcpTransportClient(timeout=4.0)
        self.tcp_server = TcpTransportServer(
            host="0.0.0.0",
            port=self.comm_port,
            message_handler=self.handle_incoming_message
        )

        # 4. Message Router
        self.router = MessageRouter(
            local_node_id=self.node_id,
            node_manager=self.node_manager,
            tcp_client=self.tcp_client,
            db=self.db
        )

        # 5. Store-and-Forward Queue Manager
        self.queue_manager = QueueManager(
            local_node_id=self.node_id,
            db=self.db,
            router=self.router,
            node_manager=self.node_manager,
            tcp_client=self.tcp_client,
            retry_interval=retry_interval
        )

        # 6. UDP Discovery Service
        self.discovery = NodeDiscoveryService(
            node_id=self.node_id,
            comm_port=self.comm_port,
            discovery_port=self.discovery_port,
            public_key=self.security.get_public_key_hex(),
            broadcast_ip=self.broadcast_ip,
            on_node_discovered=self._on_node_discovered,
            verify_key=self.security.get_verify_key_hex()
        )

        # 7. Heartbeat Watchdog
        self.heartbeat = HeartbeatWatchdog(
            node_manager=self.node_manager,
            tcp_client=self.tcp_client,
            interval=heartbeat_interval,
            unresponsive_timeout=unresponsive_timeout,
            heartbeat_timeout=heartbeat_timeout,
            on_node_recovered=self._on_node_recovered
        )

        # Event notification listeners (for API dashboard or local processing)
        self.event_listeners: List[Callable[[Dict[str, Any]], None]] = []

    async def start(self):
        """Initializes and starts all communication services."""
        logger.info(f"Initializing SYNAPSE Communication Subsystem for [{self.node_id}]...")

        # Start TCP server
        await self.tcp_server.start()

        # Start UDP discovery
        await self.discovery.start()

        # Start Heartbeat watchdog
        await self.heartbeat.start()

        # Start Store-and-Forward retry loop
        await self.queue_manager.start()

        # Announce presence to grid
        await self.discovery.broadcast_announcement()

        logger.info(f"SYNAPSE Communication Subsystem ONLINE for [{self.node_id}]")

    async def stop(self):
        """Stops all communication services gracefully."""
        logger.info(f"Stopping SYNAPSE Communication Subsystem for [{self.node_id}]...")
        await self.discovery.stop()
        await self.heartbeat.stop()
        await self.queue_manager.stop()
        await self.tcp_server.stop()
        logger.info("SYNAPSE Communication Subsystem halted.")

    def add_event_listener(self, listener: Callable[[Dict[str, Any]], None]):
        """Registers a callback for incoming surveillance events."""
        self.event_listeners.append(listener)

    async def send_message(self, destination_node: str, message_type: str,
                           payload: Any, priority: str = "P2",
                           event_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates, signs, and dispatches a SYNAPSE message.
        If immediate delivery fails, automatically buffers into the persistent SQLite Outbox.
        """
        msg = SynapseMessage.create(
            source_node=self.node_id,
            destination_node=destination_node,
            message_type=message_type,
            payload=payload,
            event_id=event_id,
            priority=priority
        )

        # Attach sender verify key for transparent peer verification
        msg.verify_key = self.security.get_verify_key_hex()

        # Cryptographically sign canonical fields
        msg.signature = self.security.sign_message(msg.to_dict())

        # Attempt immediate delivery
        success, delivered_nodes, failed_nodes = await self.router.forward_or_deliver(msg)

        # Record in local messages table for audit trail
        self.db.save_message(
            message_id=msg.message_id,
            source_node=self.node_id,
            destination_node=destination_node,
            message_type=message_type,
            payload=payload,
            event_id=event_id,
            priority=priority,
            ttl=msg.ttl,
            hop_count=msg.hop_count,
            route=msg.route,
            timestamp=msg.timestamp,
            delivered=success,
            status="DELIVERED" if success else "OUTBOX_PENDING"
        )

        if success:
            logger.info(f"[CommManager] Sent {msg.message_id} ({message_type}) -> {destination_node} (Delivered: {delivered_nodes})")
            return {
                "success": True,
                "message_id": msg.message_id,
                "status": "DELIVERED",
                "delivered_nodes": delivered_nodes
            }
        else:
            # Buffer in local SQLite outbox queue for autonomous recovery
            logger.info(f"[CommManager] Immediate delivery failed. Enqueuing {msg.message_id} for store-and-forward.")
            self.queue_manager.enqueue_message(msg)
            return {
                "success": True,
                "message_id": msg.message_id,
                "status": "QUEUED_STORE_AND_FORWARD",
                "destination": destination_node
            }

    async def handle_incoming_message(self, msg_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles an incoming TCP message:
        1. Validates replay protection (timestamp skew and message ID uniqueness).
        2. Verifies cryptographic signature.
        3. Updates sender in peer registry.
        4. Processes or stores event/alert.
        5. Forwards if destination is not this node.
        """
        msg_id = msg_dict.get("message_id", "UNKNOWN")
        source = msg_dict.get("source_node", "UNKNOWN")
        dest = msg_dict.get("destination_node", self.node_id)
        msg_type = msg_dict.get("message_type")
        timestamp = float(msg_dict.get("timestamp", time.time()))

        # Replay Attack Protection
        valid, reason = self.security.check_replay_protection(msg_id, timestamp)
        if not valid:
            logger.warning(f"[Security] Rejected message {msg_id} from {source}: {reason}")
            return {"status": "REJECTED", "reason": reason}

        # Cryptographic Signature Verification
        signature = msg_dict.get("signature")
        peer = self.node_manager.get_peer(source)
        verify_key = peer.get("verify_key") if peer else None

        if signature:
            sender_vk = msg_dict.get("verify_key")
            if not verify_key:
                # If verify_key not stored yet, check if message carries sender's verify_key (Trust On First Use)
                if sender_vk and self.security.verify_signature(msg_dict, signature, sender_vk):
                    verify_key = sender_vk
                    if peer:
                        self.node_manager.register_peer(
                            source, peer["ip"], peer["port"],
                            public_key=peer.get("public_key"),
                            verify_key=sender_vk
                        )
                else:
                    # Signature present but no verify key on file — reject to prevent key-stripping attacks
                    logger.warning(f"[Security] Rejected message {msg_id} from {source}: Signature present but no verify key for peer")
                    return {"status": "REJECTED", "reason": "UNKNOWN_PEER_KEY"}
            else:
                if not self.security.verify_signature(msg_dict, signature, verify_key):
                    logger.warning(f"[Security] Rejected message {msg_id} from {source}: Invalid cryptographic signature")
                    return {"status": "REJECTED", "reason": "INVALID_SIGNATURE"}

        # Update peer last seen if known
        if peer:
            self.node_manager.set_status(source, STATUS_ONLINE)

        # If packet is meant for another node, forward it through the router
        if dest != self.node_id and dest not in ("BROADCAST", "*", "ALL"):
            msg_obj = SynapseMessage.from_dict(msg_dict)
            success, delivered, _ = await self.router.forward_or_deliver(msg_obj)
            return {"status": "FORWARDED" if success else "FORWARD_FAILED", "delivered": delivered}

        # Handle messages destined for this node (or broadcast)
        logger.info(f"[CommManager] Ingested message {msg_id} [{msg_type}] from {source}")

        # Save to local messages table
        self.db.save_message(
            message_id=msg_id,
            source_node=source,
            destination_node=dest,
            message_type=msg_type,
            payload=msg_dict.get("payload", {}),
            event_id=msg_dict.get("event_id"),
            priority=msg_dict.get("priority", "P2"),
            ttl=msg_dict.get("ttl", 5),
            hop_count=msg_dict.get("hop_count", 0),
            route=msg_dict.get("route", []),
            timestamp=timestamp,
            delivered=True,
            status="DELIVERED"
        )

        # Dispatch by message type
        if msg_type == TYPE_HEARTBEAT:
            # Lightweight two-way heartbeat: update peer presence and ACK immediately
            if peer:
                self.node_manager.set_status(source, STATUS_ONLINE)
            logger.debug(f"[CommManager] Heartbeat from {source} — peer last_seen updated")
            return {"status": "ACK", "message_id": msg_id, "timestamp": _clock.now()}

        if msg_type == TYPE_SENSOR_DATA:
            payload = msg_dict.get("payload", {})
            readings = []
            if isinstance(payload, dict):
                if "readings" in payload and isinstance(payload["readings"], list):
                    readings = payload["readings"]
                else:
                    readings = [payload]
            elif isinstance(payload, list):
                readings = payload

            for r in readings:
                if isinstance(r, dict):
                    s_id = r.get("sensor_id", f"{source}-SENSOR")
                    s_type = r.get("sensor_type", "unknown")
                    s_ts = float(r.get("timestamp", timestamp))
                    if "source_node" not in r:
                        r["source_node"] = source
                    self.db.save_sensor_reading(
                        sensor_id=s_id,
                        sensor_type=s_type,
                        raw_value=r,
                        timestamp=s_ts,
                        source_node=source
                    )

            # Notify listeners (e.g. Command Centre dashboard, WebSockets)
            for listener in self.event_listeners:
                try:
                    listener(msg_dict)
                except Exception as e:
                    logger.error(f"Error in sensor event listener: {e}")

            return {
                "status": "ACK",
                "message_id": msg_id,
                "timestamp": _clock.now(),
                "sensor_readings_ingested": len(readings)
            }

        if msg_type == TYPE_COMMAND:
            payload = msg_dict.get("payload", {})
            cmd = payload.get("command", "") if isinstance(payload, dict) else str(payload)
            logger.info(f"[CommManager] Received COMMAND: {cmd} from {source}")
            for listener in self.event_listeners:
                try:
                    listener(msg_dict)
                except Exception as e:
                    logger.error(f"Error in command listener: {e}")

            return {
                "status": "ACK",
                "message_id": msg_id,
                "command": cmd,
                "timestamp": _clock.now()
            }

        if msg_type in (TYPE_TARGET_DETECTED, TYPE_ALERT):
            payload = msg_dict.get("payload", {})
            event_id = msg_dict.get("event_id") or msg_id
            self.db.save_event(
                event_id=event_id,
                source_node=source,
                timestamp=timestamp,
                event_type=msg_type,
                sensor_type=payload.get("sensor_type") if isinstance(payload, dict) else None,
                confidence=payload.get("confidence") if isinstance(payload, dict) else None,
                priority=msg_dict.get("priority", "P1"),
                details=payload if isinstance(payload, dict) else {"raw": payload}
            )

            if msg_type == TYPE_ALERT:
                alert_text = payload.get("message", "Tactical surveillance alert") if isinstance(payload, dict) else str(payload)
                self.db.save_alert(
                    alert_id=f"ALT-{msg_id}",
                    event_id=event_id,
                    source_node=source,
                    severity="CRITICAL" if msg_dict.get("priority") == "P0" else "WARNING",
                    message=alert_text,
                    timestamp=timestamp
                )

            # Notify listeners
            for listener in self.event_listeners:
                try:
                    listener(msg_dict)
                except Exception as e:
                    logger.error(f"Error in event listener: {e}")

        elif msg_type == TYPE_SYNC_REQUEST:
            since = float(msg_dict.get("payload", {}).get("since_timestamp", 0))
            events = self.db.get_events(limit=50, since=since)
            return {
                "status": "ACK",
                "message_id": msg_id,
                "timestamp": _clock.now(),
                "events": events
            }

        return {
            "status": "ACK",
            "message_id": msg_id,
            "timestamp": _clock.now()
        }

    def _on_node_discovered(self, node_id: str, ip: str, port: int, public_key: Optional[str], verify_key: Optional[str] = None):
        """Callback when a peer is discovered via UDP."""
        is_new = self.node_manager.register_peer(node_id, ip, port, public_key, verify_key=verify_key)
        if is_new:
            # Trigger state sync and flush any pending outbox items for this peer
            asyncio.create_task(self.queue_manager.retry_pending_outbox(target_node=node_id))
            asyncio.create_task(self.queue_manager.sync_with_peer(node_id))

    def _on_node_recovered(self, node_id: str):
        """Callback when a peer transitions from OFFLINE/UNRESPONSIVE to ONLINE."""
        logger.info(f"[CommManager] Re-evaluating pending outbox for recovered node: {node_id}")
        asyncio.create_task(self.queue_manager.retry_pending_outbox(target_node=node_id))
        asyncio.create_task(self.queue_manager.sync_with_peer(node_id))
