"""
SYNAPSE — Routing & Forwarding Engine
Handles unicast direct delivery, broadcast flood propagation,
hop routing, TTL management, and duplicate suppression.
Adapts and enhances proven ARES RelayEngine and MeshRouter.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from .node_manager import NodeManager
from .protocol import SynapseMessage
from .transport import TcpTransportClient
from ..storage.database import Database

logger = logging.getLogger("synapse.router")


class DuplicateFilter:
    """In-memory bounded duplicate suppression filter."""

    def __init__(self, max_history: int = 5000):
        self.seen_ids = set()
        self.history = []
        self.max_history = max_history

    def is_duplicate(self, message_id: str) -> bool:
        return message_id in self.seen_ids

    def mark_seen(self, message_id: str):
        if message_id in self.seen_ids:
            return
        self.seen_ids.add(message_id)
        self.history.append(message_id)
        if len(self.history) > self.max_history:
            oldest = self.history.pop(0)
            self.seen_ids.discard(oldest)


class MessageRouter:
    """Routes messages across the local SYNAPSE grid."""

    def __init__(self, local_node_id: str, node_manager: NodeManager,
                 tcp_client: TcpTransportClient, db: Database):
        self.local_node_id = local_node_id
        self.node_manager = node_manager
        self.tcp_client = tcp_client
        self.db = db
        self.duplicate_filter = DuplicateFilter()

    async def forward_or_deliver(self, message: SynapseMessage) -> Tuple[bool, List[str], List[str]]:
        """
        Processes or forwards an incoming or newly created message.
        Returns: (success: bool, delivered_nodes: list[str], failed_nodes: list[str])
        """
        msg_id = message.message_id
        dest = message.destination_node

        # Check duplicate
        if self.duplicate_filter.is_duplicate(msg_id):
            logger.debug(f"[Router] Duplicate message {msg_id} dropped.")
            return False, [], []

        self.duplicate_filter.mark_seen(msg_id)

        # Case 1: Destined for THIS node
        if dest == self.local_node_id:
            logger.info(f"[Router] Message {msg_id} reached final destination: {self.local_node_id}")
            self.db.save_message(
                message_id=msg_id,
                source_node=message.source_node,
                destination_node=dest,
                message_type=message.message_type,
                payload=message.payload,
                event_id=message.event_id,
                priority=message.priority,
                ttl=message.ttl,
                hop_count=message.hop_count,
                route=message.route,
                timestamp=message.timestamp,
                delivered=True,
                status="DELIVERED"
            )
            return True, [self.local_node_id], []

        # Case 2: BROADCAST (Flood to all active peers)
        if dest.upper() in ("BROADCAST", "*", "ALL"):
            peers = self.node_manager.get_all_peers()
            delivered = []
            failed = []

            # Prioritize peers by route score
            sorted_peers = sorted(
                peers.items(),
                key=lambda item: self.node_manager.get_route_score(item[0]),
                reverse=True
            )

            msg_dict = message.to_dict()

            for peer_id, peer in sorted_peers:
                if peer_id in message.route:
                    continue  # Loop prevention
                if peer.get("status") != "ONLINE":
                    continue

                success, _, _ = await self.tcp_client.send_message(peer["ip"], peer["port"], msg_dict)
                self.node_manager.record_attempt(peer_id, success)
                if success:
                    delivered.append(peer_id)
                else:
                    failed.append(peer_id)

            logger.info(f"[Router] Broadcast {msg_id} -> Delivered: {len(delivered)}, Failed: {len(failed)}")
            return len(delivered) > 0, delivered, failed

        # Case 3: Unicast forwarding (direct peer or multi-hop)
        # Check TTL
        if message.ttl <= 0:
            logger.warning(f"[Router] Packet {msg_id} TTL expired ({message.ttl}). Dropping.")
            return False, [], [dest]

        # Update hop telemetry
        message.ttl -= 1
        message.hop_count += 1
        if self.local_node_id not in message.route:
            message.route.append(self.local_node_id)

        # Check if direct peer is online
        direct_peer = self.node_manager.get_peer(dest)
        if direct_peer and direct_peer.get("status") == "ONLINE":
            success, _, err = await self.tcp_client.send_message(
                direct_peer["ip"],
                direct_peer["port"],
                message.to_dict()
            )
            self.node_manager.record_attempt(dest, success)
            if success:
                logger.info(f"[Router] Direct delivery {msg_id} -> {dest} SUCCESS")
                return True, [dest], []
            else:
                logger.warning(f"[Router] Direct send to {dest} failed ({err}).")

        # Fallback Multi-hop: try forwarding to best online intermediate peer
        online_peers = [
            (nid, p) for nid, p in self.node_manager.get_all_peers().items()
            if p.get("status") == "ONLINE" and nid not in message.route and nid != message.source_node
        ]
        sorted_relays = sorted(
            online_peers,
            key=lambda item: self.node_manager.get_route_score(item[0]),
            reverse=True
        )

        for relay_id, relay in sorted_relays:
            success, _, _ = await self.tcp_client.send_message(
                relay["ip"],
                relay["port"],
                message.to_dict()
            )
            self.node_manager.record_attempt(relay_id, success)
            if success:
                logger.info(f"[Router] Multi-hop relay {msg_id} forwarded via {relay_id} towards {dest}")
                return True, [relay_id], []

        # If no peer reachable right now
        logger.info(f"[Router] No reachable path for {dest}. Packet requires local Store-and-Forward.")
        return False, [], [dest]
