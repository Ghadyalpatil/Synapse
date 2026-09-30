"""
SYNAPSE — Local SQLite Database
Self-contained, local-first persistent storage for Raspberry Pi.
Zero cloud, zero remote dependencies.
"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class Database:
    """Thread-safe SQLite storage for a SYNAPSE surveillance node."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30.0
        )
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;

            -- Discovered and paired SYNAPSE grid nodes
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                public_key TEXT,
                status TEXT DEFAULT 'OFFLINE',
                last_seen REAL,
                latency_ms REAL,
                packet_loss REAL DEFAULT 0.0,
                total_attempts INTEGER DEFAULT 0,
                total_failures INTEGER DEFAULT 0
            );

            -- Surveillance events (Target detections, perimeter breaches, etc.)
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                source_node TEXT NOT NULL,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                sensor_type TEXT,
                confidence REAL,
                priority TEXT DEFAULT 'P1',
                details TEXT,
                created_at REAL NOT NULL
            );

            -- Raw sensor telemetry (local only)
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                raw_value TEXT NOT NULL,
                timestamp REAL NOT NULL
            );

            -- Inter-node message logs (Inbox & processed traffic)
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                event_id TEXT,
                source_node TEXT NOT NULL,
                destination_node TEXT NOT NULL,
                message_type TEXT NOT NULL,
                priority TEXT DEFAULT 'P2',
                ttl INTEGER DEFAULT 5,
                hop_count INTEGER DEFAULT 0,
                route TEXT,
                payload TEXT,
                timestamp REAL NOT NULL,
                delivered INTEGER DEFAULT 0,
                status TEXT DEFAULT 'RECEIVED'
            );

            -- Store-and-Forward Outbox queue
            CREATE TABLE IF NOT EXISTS outbox (
                outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE NOT NULL,
                destination_node TEXT NOT NULL,
                payload TEXT NOT NULL,
                priority TEXT DEFAULT 'P2',
                created_at REAL NOT NULL,
                last_attempt REAL DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                status TEXT DEFAULT 'PENDING'
            );

            -- Tactical surveillance alerts
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                event_id TEXT,
                source_node TEXT NOT NULL,
                severity TEXT DEFAULT 'WARNING',
                message TEXT NOT NULL,
                timestamp REAL NOT NULL,
                acknowledged INTEGER DEFAULT 0
            );

            -- Local operational audit logs
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp REAL NOT NULL
            );

            -- Synchronization cursors for peer state exchange
            CREATE TABLE IF NOT EXISTS sync_state (
                peer_node TEXT PRIMARY KEY,
                last_synced_event_id TEXT,
                last_synced_timestamp REAL
            );

            CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status, priority, created_at);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_messages_event ON messages(event_id);
            """)
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    # ──────────────────────────────────────────────────────────────
    # Node Management
    # ──────────────────────────────────────────────────────────────

    def upsert_node(self, node_id: str, ip: str, port: int, public_key: Optional[str] = None, status: str = "ONLINE") -> None:
        with self._lock:
            now = time.time()
            self._conn.execute("""
                INSERT INTO nodes (node_id, ip, port, public_key, status, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    ip = excluded.ip,
                    port = excluded.port,
                    public_key = COALESCE(excluded.public_key, nodes.public_key),
                    status = excluded.status,
                    last_seen = excluded.last_seen
            """, (node_id, ip, port, public_key, status, now))
            self._conn.commit()

    def update_node_status(self, node_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE nodes SET status = ? WHERE node_id = ?",
                (status, node_id)
            )
            self._conn.commit()

    def update_node_metrics(self, node_id: str, success: bool, latency_ms: Optional[float] = None) -> None:
        with self._lock:
            row = self._conn.execute("SELECT total_attempts, total_failures FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
            if not row:
                return
            attempts = (row["total_attempts"] or 0) + 1
            failures = (row["total_failures"] or 0) + (0 if success else 1)
            loss = round(failures / attempts, 3) if attempts > 0 else 0.0
            now = time.time()
            if success:
                self._conn.execute("""
                    UPDATE nodes SET
                        total_attempts = ?, total_failures = ?, packet_loss = ?,
                        latency_ms = COALESCE(?, latency_ms), last_seen = ?, status = 'ONLINE'
                    WHERE node_id = ?
                """, (attempts, failures, loss, latency_ms, now, node_id))
            else:
                self._conn.execute("""
                    UPDATE nodes SET
                        total_attempts = ?, total_failures = ?, packet_loss = ?
                    WHERE node_id = ?
                """, (attempts, failures, loss, node_id))
            self._conn.commit()

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM nodes ORDER BY node_id ASC")
            return [dict(r) for r in cur.fetchall()]

    # ──────────────────────────────────────────────────────────────
    # Surveillance Events
    # ──────────────────────────────────────────────────────────────

    def save_event(self, event_id: str, source_node: str, timestamp: float,
                   event_type: str, sensor_type: Optional[str] = None,
                   confidence: Optional[float] = None, priority: str = "P1",
                   details: Optional[Dict[str, Any]] = None) -> bool:
        """Saves an event. Returns True if inserted, False if duplicate."""
        with self._lock:
            try:
                now = time.time()
                details_json = json.dumps(details or {})
                self._conn.execute("""
                    INSERT INTO events (event_id, source_node, timestamp, event_type,
                                        sensor_type, confidence, priority, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (event_id, source_node, timestamp, event_type, sensor_type, confidence, priority, details_json, now))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def event_exists(self, event_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("SELECT 1 FROM events WHERE event_id = ?", (event_id,))
            return cur.fetchone() is not None

    def get_events(self, limit: int = 50, since: Optional[float] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if since:
                cur = self._conn.execute(
                    "SELECT * FROM events WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?",
                    (since, limit)
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("details"):
                    try:
                        d["details"] = json.loads(d["details"])
                    except Exception:
                        pass
                results.append(d)
            return results

    # ──────────────────────────────────────────────────────────────
    # Raw Sensor Telemetry
    # ──────────────────────────────────────────────────────────────

    def save_sensor_reading(self, sensor_id: str, sensor_type: str, raw_value: Any, timestamp: Optional[float] = None):
        with self._lock:
            val_str = json.dumps(raw_value) if not isinstance(raw_value, str) else raw_value
            self._conn.execute(
                "INSERT INTO sensor_data (sensor_id, sensor_type, raw_value, timestamp) VALUES (?, ?, ?, ?)",
                (sensor_id, sensor_type, val_str, timestamp or time.time())
            )
            self._conn.commit()

    # ──────────────────────────────────────────────────────────────
    # Messages & Inbox
    # ──────────────────────────────────────────────────────────────

    def save_message(self, message_id: str, source_node: str, destination_node: str,
                     message_type: str, payload: Any, event_id: Optional[str] = None,
                     priority: str = "P2", ttl: int = 5, hop_count: int = 0,
                     route: Optional[List[str]] = None, timestamp: Optional[float] = None,
                     delivered: bool = False, status: str = "RECEIVED") -> bool:
        with self._lock:
            try:
                payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
                route_str = json.dumps(route or [])
                self._conn.execute("""
                    INSERT OR REPLACE INTO messages (
                        message_id, event_id, source_node, destination_node,
                        message_type, priority, ttl, hop_count, route,
                        payload, timestamp, delivered, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id, event_id, source_node, destination_node,
                    message_type, priority, ttl, hop_count, route_str,
                    payload_str, timestamp or time.time(), 1 if delivered else 0, status
                ))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def message_exists(self, message_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("SELECT 1 FROM messages WHERE message_id = ?", (message_id,))
            return cur.fetchone() is not None

    def get_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,))
            results = []
            for r in cur.fetchall():
                d = dict(r)
                if d.get("route"):
                    try:
                        d["route"] = json.loads(d["route"])
                    except Exception:
                        pass
                if d.get("payload"):
                    try:
                        d["payload"] = json.loads(d["payload"])
                    except Exception:
                        pass
                results.append(d)
            return results

    # ──────────────────────────────────────────────────────────────
    # Store-and-Forward Outbox
    # ──────────────────────────────────────────────────────────────

    def enqueue_outbox(self, message_id: str, destination_node: str, payload: Dict[str, Any], priority: str = "P2") -> bool:
        with self._lock:
            try:
                now = time.time()
                payload_str = json.dumps(payload)
                self._conn.execute("""
                    INSERT INTO outbox (message_id, destination_node, payload, priority, created_at, status)
                    VALUES (?, ?, ?, ?, ?, 'PENDING')
                """, (message_id, destination_node, payload_str, priority, now))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_pending_outbox(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            # Sort by Priority (P0 > P1 > P2) then created_at
            cur = self._conn.execute("""
                SELECT * FROM outbox
                WHERE status = 'PENDING'
                ORDER BY
                    CASE priority
                        WHEN 'P0' THEN 0
                        WHEN 'P1' THEN 1
                        WHEN 'P2' THEN 2
                        ELSE 3
                    END,
                    created_at ASC
                LIMIT ?
            """, (limit,))
            items = []
            for r in cur.fetchall():
                d = dict(r)
                try:
                    d["payload"] = json.loads(d["payload"])
                except Exception:
                    pass
                items.append(d)
            return items

    def update_outbox_attempt(self, message_id: str, success: bool, mark_delivered: bool = False):
        with self._lock:
            now = time.time()
            if success or mark_delivered:
                self._conn.execute("""
                    UPDATE outbox SET status = 'DELIVERED', last_attempt = ? WHERE message_id = ?
                """, (now, message_id))
            else:
                self._conn.execute("""
                    UPDATE outbox SET
                        attempts = attempts + 1,
                        last_attempt = ?,
                        status = CASE WHEN attempts >= 100 THEN 'EXPIRED' ELSE 'PENDING' END
                    WHERE message_id = ?
                """, (now, message_id))
            self._conn.commit()

    def clear_outbox(self, status: Optional[str] = None) -> int:
        """
        Clears messages from the outbox queue.
        If status is provided (e.g. 'PENDING'), only deletes messages with that status.
        If status is None, clears all messages from the outbox.
        Returns the number of rows deleted.
        """
        with self._lock:
            if status:
                cur = self._conn.execute("DELETE FROM outbox WHERE status = ?", (status,))
            else:
                cur = self._conn.execute("DELETE FROM outbox")
            deleted = cur.rowcount
            self._conn.commit()
            return deleted

    def get_outbox_count(self) -> Dict[str, int]:
        with self._lock:
            cur = self._conn.execute("""
                SELECT status, COUNT(*) as cnt FROM outbox GROUP BY status
            """)
            counts = {"PENDING": 0, "DELIVERED": 0, "EXPIRED": 0}
            for row in cur.fetchall():
                counts[row["status"]] = row["cnt"]
            return counts

    # ──────────────────────────────────────────────────────────────
    # Alerts
    # ──────────────────────────────────────────────────────────────

    def save_alert(self, alert_id: str, source_node: str, severity: str,
                   message: str, event_id: Optional[str] = None,
                   timestamp: Optional[float] = None) -> bool:
        with self._lock:
            try:
                self._conn.execute("""
                    INSERT INTO alerts (alert_id, event_id, source_node, severity, message, timestamp, acknowledged)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """, (alert_id, event_id, source_node, severity, message, timestamp or time.time()))
                self._conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def acknowledge_alert(self, alert_id: str):
        with self._lock:
            self._conn.execute("UPDATE alerts SET acknowledged = 1 WHERE alert_id = ?", (alert_id,))
            self._conn.commit()

    # ──────────────────────────────────────────────────────────────
    # Audit Logging
    # ──────────────────────────────────────────────────────────────

    def log(self, level: str, message: str):
        with self._lock:
            self._conn.execute(
                "INSERT INTO system_logs (level, message, timestamp) VALUES (?, ?, ?)",
                (level.upper(), message, time.time())
            )
            self._conn.commit()

    def get_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]
