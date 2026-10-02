"""
SYNAPSE — Node Manager & Peer Registry
Maintains grid topology, node lifecycle states, link metrics, and route scores.
Adapts and enhances the proven ARES PeerRegistry.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from synapse import clock as _clock
from ..storage.database import Database

logger = logging.getLogger("synapse.node_manager")

STATUS_ONLINE = "ONLINE"
STATUS_UNRESPONSIVE = "UNRESPONSIVE"
STATUS_OFFLINE = "OFFLINE"
STATUS_DISCOVERED = "DISCOVERED"
STATUS_RECONNECTING = "RECONNECTING"


class NodeManager:
    """Manages local grid topology, node health, and status transitions."""

    def __init__(self, local_node_id: str, db: Database):
        self.local_node_id = local_node_id
        self.db = db
        self.peers: Dict[str, Dict[str, Any]] = {}
        self._load_from_db()

    def _load_from_db(self):
        """Loads known nodes from the persistent local database into memory."""
        rows = self.db.get_all_nodes()
        for r in rows:
            node_id = r["node_id"]
            if node_id == self.local_node_id:
                continue
            self.peers[node_id] = {
                "ip": r["ip"],
                "port": r["port"],
                "public_key": r.get("public_key"),
                "verify_key": r.get("verify_key"),
                "status": r.get("status", STATUS_OFFLINE),
                "last_seen": r.get("last_seen"),
                "latency_ms": r.get("latency_ms"),
                "packet_loss": r.get("packet_loss", 0.0),
                "total_attempts": r.get("total_attempts", 0),
                "total_failures": r.get("total_failures", 0)
            }

    def register_peer(self, node_id: str, ip: str, port: int, public_key: Optional[str] = None,
                      verify_key: Optional[str] = None) -> bool:
        """
        Adds or updates a peer in the registry and database.
        Returns True if this is a newly discovered node.
        """
        if node_id == self.local_node_id:
            return False

        is_new = node_id not in self.peers
        existing = self.peers.get(node_id, {})

        # Preserve stats or update IP/port if peer changed address
        self.peers[node_id] = {
            "ip": ip,
            "port": port,
            "public_key": public_key or existing.get("public_key"),
            "verify_key": verify_key or existing.get("verify_key"),
            "status": STATUS_ONLINE,
            "last_seen": _clock.now(),
            "latency_ms": existing.get("latency_ms"),
            "packet_loss": existing.get("packet_loss", 0.0),
            "total_attempts": existing.get("total_attempts", 0),
            "total_failures": existing.get("total_failures", 0)
        }

        # Persist to local SQLite
        self.db.upsert_node(
            node_id=node_id,
            ip=ip,
            port=port,
            public_key=public_key or existing.get("public_key"),
            status=STATUS_ONLINE,
            verify_key=verify_key or existing.get("verify_key")
        )

        if is_new:
            logger.info(f"[NodeManager] New node added to grid: {node_id} at {ip}:{port}")
        return is_new

    def get_peer(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.peers.get(node_id)

    def get_all_peers(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.peers)

    def get_online_peers(self) -> List[str]:
        return [nid for nid, p in self.peers.items() if p.get("status") == STATUS_ONLINE]

    def set_status(self, node_id: str, status: str) -> bool:
        """Sets node status. Returns True if status changed."""
        peer = self.peers.get(node_id)
        if not peer:
            return False
        prev = peer.get("status")
        if prev != status:
            peer["status"] = status
            self.db.update_node_status(node_id, status)
            logger.info(f"[NodeManager] Node {node_id} state transition: {prev} -> {status}")
            return True
        return False

    def record_attempt(self, node_id: str, success: bool, latency_ms: Optional[float] = None):
        """Records connection/probe attempt result and updates statistics."""
        peer = self.peers.get(node_id)
        if not peer:
            return

        peer["total_attempts"] = peer.get("total_attempts", 0) + 1
        if success:
            peer["last_seen"] = _clock.now()
            if latency_ms is not None:
                peer["latency_ms"] = latency_ms
        else:
            peer["total_failures"] = peer.get("total_failures", 0) + 1

        attempts = peer["total_attempts"]
        failures = peer["total_failures"]
        peer["packet_loss"] = round(failures / attempts, 3) if attempts > 0 else 0.0

        # Sync to DB
        self.db.update_node_metrics(node_id, success, latency_ms)

    def get_route_score(self, node_id: str) -> float:
        """
        Calculates route score based on connectivity, reliability, and latency.
        Higher score = higher transmission priority.
        """
        peer = self.peers.get(node_id)
        if not peer:
            return 0.0

        status = peer.get("status")
        if status == STATUS_ONLINE:
            conn_score = 10.0
        elif status == STATUS_UNRESPONSIVE:
            conn_score = 3.0
        else:
            conn_score = 0.0

        packet_loss = peer.get("packet_loss", 0.0)
        rel_score = (1.0 - packet_loss) * 10.0

        latency = peer.get("latency_ms") or 0.0
        lat_penalty = min(latency / 50.0, 10.0)

        score = round(conn_score + rel_score - lat_penalty, 2)
        return max(score, 0.0)
