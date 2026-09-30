"""
SYNAPSE — Store-and-Forward Outbox & Synchronization Manager
Preserves messages when peers are offline, automatically replays upon reconnection,
and synchronizes historical state.
Adapts and enhances proven ARES Store-and-Forward.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from .node_manager import NodeManager
from .protocol import SynapseMessage, TYPE_SYNC_REQUEST
from .router import MessageRouter
from .transport import TcpTransportClient
from ..storage.database import Database

logger = logging.getLogger("synapse.queue_manager")


class QueueManager:
    """Manages the persistent store-and-forward outbox queue and event synchronization."""

    def __init__(self, local_node_id: str, db: Database,
                 router: MessageRouter, node_manager: NodeManager,
                 tcp_client: TcpTransportClient,
                 retry_interval: float = 6.0):
        self.local_node_id = local_node_id
        self.db = db
        self.router = router
        self.node_manager = node_manager
        self.tcp_client = tcp_client
        self.retry_interval = retry_interval

        self._task: Optional[asyncio.Task] = None
        self._is_running = False
        self._retry_lock = asyncio.Lock()

    async def start(self):
        """Starts the background store-and-forward retry daemon."""
        self._is_running = True
        self._task = asyncio.create_task(self._retry_loop())
        logger.info(f"Store-and-Forward engine active (retry_interval={self.retry_interval}s)")

    async def stop(self):
        """Stops the retry daemon."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Store-and-Forward engine stopped.")

    def enqueue_message(self, message: SynapseMessage):
        """Persists an outgoing message to the local SQLite outbox queue."""
        logger.info(f"[Store-and-Forward] Enqueueing {message.message_id} -> {message.destination_node} (Priority: {message.priority})")
        self.db.enqueue_outbox(
            message_id=message.message_id,
            destination_node=message.destination_node,
            payload=message.to_dict(),
            priority=message.priority
        )

    def clear_outbox(self, status: Optional[str] = None) -> int:
        """Clears messages from the persistent store-and-forward outbox."""
        deleted = self.db.clear_outbox(status=status)
        logger.info(f"[Store-and-Forward] Cleared {deleted} message(s) from outbox (filter={status})")
        return deleted

    async def retry_pending_outbox(self, target_node: Optional[str] = None):
        """
        Retries delivering queued messages.
        If target_node is specified, prioritizes messages destined for that node.
        """
        async with self._retry_lock:
            pending = self.db.get_pending_outbox(limit=30)
            if not pending:
                return

            logger.info(f"[Store-and-Forward] Checking {len(pending)} pending outbox item(s)...")

            for item in pending:
                msg_id = item["message_id"]
                dest = item["destination_node"]
                payload_dict = item["payload"]

                if target_node and dest not in (target_node, "BROADCAST", "*"):
                    continue

                msg = SynapseMessage.from_dict(payload_dict)

                # Attempt forwarding
                success, delivered, _ = await self.router.forward_or_deliver(msg)

                if success:
                    logger.info(f"[Store-and-Forward] Queued message {msg_id} delivered to {delivered}")
                    self.db.update_outbox_attempt(msg_id, success=True, mark_delivered=True)
                else:
                    self.db.update_outbox_attempt(msg_id, success=False)

    async def sync_with_peer(self, peer_id: str) -> bool:
        """
        Initiates state synchronization with a newly connected or recovered peer.
        Exchanges missing surveillance events since the last sync cursor.
        """
        peer = self.node_manager.get_peer(peer_id)
        if not peer or peer.get("status") != "ONLINE":
            return False

        # Request peer's latest events
        sync_req = SynapseMessage.create(
            source_node=self.local_node_id,
            destination_node=peer_id,
            message_type=TYPE_SYNC_REQUEST,
            payload={"since_timestamp": time.time() - 86400.0},  # last 24h
            priority="P1"
        )

        success, ack, _ = await self.tcp_client.send_message(peer["ip"], peer["port"], sync_req.to_dict())
        if success and ack and ack.get("events"):
            events = ack.get("events", [])
            logger.info(f"[Sync] Received {len(events)} events from {peer_id}")
            for evt in events:
                self.db.save_event(
                    event_id=evt["event_id"],
                    source_node=evt["source_node"],
                    timestamp=evt["timestamp"],
                    event_type=evt["event_type"],
                    sensor_type=evt.get("sensor_type"),
                    confidence=evt.get("confidence"),
                    priority=evt.get("priority", "P1"),
                    details=evt.get("details")
                )
            return True
        return False

    async def _retry_loop(self):
        """Periodic background retry."""
        while self._is_running:
            try:
                await self.retry_pending_outbox()
            except Exception as e:
                logger.error(f"[Store-and-Forward] Loop error: {e}")
            await asyncio.sleep(self.retry_interval)
