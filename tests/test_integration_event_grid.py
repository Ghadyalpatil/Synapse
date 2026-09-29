"""
SYNAPSE — Integration Tests: EventEngine → Communication → Grid Node Flow

Tests the complete surveillance pipeline:
  Sensor reading → EventEngine threat assessment → SQLite persistence
  → CommunicationManager → TCP transport → Peer grid reception

All tests run in-process with two simulated SYNAPSE nodes on loopback.
No cloud, no external infrastructure.
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from synapse.communication.protocol import (
    SynapseMessage,
    TYPE_ALERT,
    TYPE_TARGET_DETECTED,
    TYPE_COMMAND,
    TYPE_SYNC_REQUEST,
    PRIORITY_P0,
    PRIORITY_P1,
)
from synapse.communication.router import MessageRouter, DuplicateFilter
from synapse.communication.node_manager import NodeManager, STATUS_ONLINE, STATUS_OFFLINE
from synapse.communication.security import SecurityManager
from synapse.communication.transport import TcpTransportClient, TcpTransportServer
from synapse.processing.event_engine import EventEngine
from synapse.sensors.sensor_engine import SensorManager
from synapse.storage.database import Database


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_db(tmp_path: Path, name: str = "test.db") -> Database:
    return Database(tmp_path / name)


def make_sensor_manager() -> SensorManager:
    return SensorManager()


class MockCommManager:
    """Lightweight comm-manager stand-in for EventEngine unit tests."""

    def __init__(self):
        self.sent: List[Dict] = []

    async def send_message(self, destination_node, message_type, payload,
                           priority="P2", event_id=None):
        self.sent.append({
            "destination_node": destination_node,
            "message_type": message_type,
            "payload": payload,
            "priority": priority,
            "event_id": event_id,
        })
        return {"success": True, "status": "MOCK_DELIVERED"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. DuplicateFilter
# ─────────────────────────────────────────────────────────────────────────────

class TestDuplicateFilter:
    def test_fresh_id_not_duplicate(self):
        f = DuplicateFilter()
        assert f.is_duplicate("MSG-001") is False

    def test_after_mark_is_duplicate(self):
        f = DuplicateFilter()
        f.mark_seen("MSG-001")
        assert f.is_duplicate("MSG-001") is True

    def test_different_ids_independent(self):
        f = DuplicateFilter()
        f.mark_seen("MSG-001")
        assert f.is_duplicate("MSG-002") is False

    def test_ring_buffer_evicts_oldest(self):
        f = DuplicateFilter(max_history=5)
        for i in range(5):
            f.mark_seen(f"MSG-{i:04d}")
        f.mark_seen("MSG-0005")          # triggers eviction of MSG-0000
        assert f.is_duplicate("MSG-0000") is False
        assert f.is_duplicate("MSG-0005") is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. SynapseMessage
# ─────────────────────────────────────────────────────────────────────────────

class TestSynapseMessage:
    def test_factory_generates_unique_ids(self):
        m1 = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_ALERT, {})
        m2 = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_ALERT, {})
        assert m1.message_id != m2.message_id

    def test_dict_roundtrip(self):
        m = SynapseMessage.create(
            source_node="SYNAPSE-001",
            destination_node="BROADCAST",
            message_type=TYPE_TARGET_DETECTED,
            payload={"confidence": 0.95},
            event_id="EVT-ABCD1234",
            priority=PRIORITY_P0,
        )
        m2 = SynapseMessage.from_dict(m.to_dict())
        assert m2.message_id == m.message_id
        assert m2.event_id == m.event_id
        assert m2.priority == "P0"
        assert m2.source_node == "SYNAPSE-001"

    def test_route_includes_source(self):
        m = SynapseMessage.create("SYNAPSE-003", "SYNAPSE-005", TYPE_COMMAND, {})
        assert "SYNAPSE-003" in m.route

    def test_invalid_priority_normalised(self):
        m = SynapseMessage.from_dict({"priority": "P9", "message_type": TYPE_ALERT})
        assert m.priority == "P2"

    def test_invalid_type_normalised(self):
        m = SynapseMessage.from_dict({"message_type": "TOTALLY_UNKNOWN_TYPE"})
        assert m.message_type == "SENSOR_DATA"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Database
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabase:
    def test_save_and_retrieve_event(self, tmp_path):
        db = make_db(tmp_path)
        assert db.save_event("EVT-001", "SYNAPSE-001", time.time(),
                             TYPE_TARGET_DETECTED, "thermal", 0.92, "P0",
                             {"zone": "Sector-7"}) is True
        events = db.get_events(limit=5)
        assert events[0]["event_id"] == "EVT-001"
        assert isinstance(events[0]["details"], dict)
        assert events[0]["details"]["zone"] == "Sector-7"

    def test_duplicate_event_rejected(self, tmp_path):
        db = make_db(tmp_path)
        db.save_event("EVT-DUP", "S1", time.time(), TYPE_ALERT)
        assert db.save_event("EVT-DUP", "S1", time.time(), TYPE_ALERT) is False

    def test_event_exists(self, tmp_path):
        db = make_db(tmp_path)
        assert db.event_exists("EVT-NEW") is False
        db.save_event("EVT-NEW", "S1", time.time(), TYPE_ALERT)
        assert db.event_exists("EVT-NEW") is True

    def test_alert_save_and_acknowledge(self, tmp_path):
        db = make_db(tmp_path)
        db.save_alert("ALT-001", source_node="SYNAPSE-001", severity="CRITICAL",
                      message="Thermal breach Sector-4", event_id="EVT-001")
        alerts = db.get_alerts()
        assert alerts[0]["acknowledged"] == 0
        db.acknowledge_alert("ALT-001")
        assert db.get_alerts()[0]["acknowledged"] == 1

    def test_outbox_lifecycle(self, tmp_path):
        db = make_db(tmp_path)
        db.enqueue_outbox("MSG-OBX", "SYNAPSE-002", {"text": "delayed"}, "P1")
        assert len(db.get_pending_outbox()) == 1
        db.update_outbox_attempt("MSG-OBX", success=True)
        assert len(db.get_pending_outbox()) == 0
        assert db.get_outbox_count()["DELIVERED"] == 1

    def test_outbox_priority_ordering(self, tmp_path):
        db = make_db(tmp_path)
        db.enqueue_outbox("MSG-P2", "DEST", {}, "P2")
        db.enqueue_outbox("MSG-P0", "DEST", {}, "P0")
        db.enqueue_outbox("MSG-P1", "DEST", {}, "P1")
        priorities = [p["priority"] for p in db.get_pending_outbox()]
        assert priorities == ["P0", "P1", "P2"]

    def test_node_upsert_and_status(self, tmp_path):
        db = make_db(tmp_path)
        db.upsert_node("SYNAPSE-002", "192.168.1.102", 9001, status="ONLINE")
        assert db.get_node("SYNAPSE-002")["status"] == "ONLINE"
        db.update_node_status("SYNAPSE-002", "OFFLINE")
        assert db.get_node("SYNAPSE-002")["status"] == "OFFLINE"

    def test_events_since_filter(self, tmp_path):
        db = make_db(tmp_path)
        t0 = time.time()
        db.save_event("EVT-OLD", "S1", t0 - 100, TYPE_ALERT)
        db.save_event("EVT-NEW", "S1", t0 + 1, TYPE_ALERT)
        recent = db.get_events(since=t0)
        ids = [e["event_id"] for e in recent]
        assert "EVT-NEW" in ids
        assert "EVT-OLD" not in ids


# ─────────────────────────────────────────────────────────────────────────────
# 4. NodeManager
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeManager:
    def test_register_and_retrieve_peer(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        assert nm.register_peer("SYNAPSE-002", "192.168.1.102", 9002) is True
        peer = nm.get_peer("SYNAPSE-002")
        assert peer["ip"] == "192.168.1.102"
        assert peer["status"] == STATUS_ONLINE

    def test_self_not_registered(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        assert nm.register_peer("SYNAPSE-001", "127.0.0.1", 9001) is False
        assert nm.get_peer("SYNAPSE-001") is None

    def test_status_transition(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        nm.register_peer("SYNAPSE-002", "192.168.1.102", 9002)
        nm.set_status("SYNAPSE-002", STATUS_OFFLINE)
        assert nm.get_peer("SYNAPSE-002")["status"] == STATUS_OFFLINE

    def test_online_peers_filter(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        nm.register_peer("SYNAPSE-002", "192.168.1.102", 9002)
        nm.register_peer("SYNAPSE-003", "192.168.1.103", 9003)
        nm.set_status("SYNAPSE-003", STATUS_OFFLINE)
        online = nm.get_online_peers()
        assert "SYNAPSE-002" in online
        assert "SYNAPSE-003" not in online

    def test_route_score_online_beats_offline(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        nm.register_peer("SYNAPSE-002", "192.168.1.102", 9002)
        nm.register_peer("SYNAPSE-003", "192.168.1.103", 9003)
        nm.set_status("SYNAPSE-003", STATUS_OFFLINE)
        assert nm.get_route_score("SYNAPSE-002") > nm.get_route_score("SYNAPSE-003")

    def test_packet_loss_tracking(self, tmp_path):
        db = make_db(tmp_path)
        nm = NodeManager("SYNAPSE-001", db)
        nm.register_peer("SYNAPSE-002", "192.168.1.102", 9002)
        nm.record_attempt("SYNAPSE-002", success=True)
        nm.record_attempt("SYNAPSE-002", success=False)
        nm.record_attempt("SYNAPSE-002", success=False)
        peer = nm.get_peer("SYNAPSE-002")
        assert peer["total_attempts"] == 3
        assert peer["total_failures"] == 2
        assert abs(peer["packet_loss"] - 0.667) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# 5. SecurityManager
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityManager:
    def test_sign_produces_nonempty_hex(self, tmp_path):
        sm = SecurityManager("SYNAPSE-001", tmp_path / "keys")
        sig = sm.sign_message({
            "message_id": "MSG-001", "source_node": "SYNAPSE-001",
            "destination_node": "SYNAPSE-002", "message_type": TYPE_ALERT,
            "priority": "P0", "timestamp": time.time(), "payload": {}
        })
        assert isinstance(sig, str) and len(sig) > 0

    def test_key_persistence_across_instances(self, tmp_path):
        keys_dir = tmp_path / "keys"
        pk1 = SecurityManager("SYNAPSE-001", keys_dir).get_public_key_hex()
        pk2 = SecurityManager("SYNAPSE-001", keys_dir).get_public_key_hex()
        assert pk1 == pk2

    def test_replay_protection_blocks_second_occurrence(self, tmp_path):
        sm = SecurityManager("SYNAPSE-001", tmp_path / "keys")
        ts = time.time()
        ok, _ = sm.check_replay_protection("MSG-REPLAY", ts)
        assert ok is True
        ok2, reason2 = sm.check_replay_protection("MSG-REPLAY", ts)
        assert ok2 is False
        assert "replay" in reason2.lower() or "duplicate" in reason2.lower()

    def test_stale_timestamp_rejected(self, tmp_path):
        sm = SecurityManager("SYNAPSE-001", tmp_path / "keys")
        stale = time.time() - 700   # > 300s window
        ok, reason = sm.check_replay_protection("MSG-STALE", stale)
        assert ok is False
        assert "window" in reason.lower() or "timestamp" in reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 6. EventEngine Threat Assessment
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_thermal_detection_persists_and_broadcasts(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    event_id = await engine.process_sensor_reading({
        "sensor_id": "TH-01", "sensor_type": "thermal",
        "temperature_celsius": 37.4, "target_detected": True,
        "confidence": 0.95, "timestamp": time.time(),
    })

    assert event_id and event_id.startswith("EVT-")
    assert any(e["event_id"] == event_id for e in db.get_events())
    assert any(a["event_id"] == event_id for a in db.get_alerts())
    assert len(mock.sent) == 1
    assert mock.sent[0]["destination_node"] == "BROADCAST"
    assert mock.sent[0]["message_type"] == TYPE_TARGET_DETECTED
    await engine.stop()


@pytest.mark.asyncio
async def test_thermal_high_confidence_is_p0(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    event_id = await engine.process_sensor_reading({
        "sensor_id": "TH-01", "sensor_type": "thermal",
        "temperature_celsius": 38.1, "target_detected": True,
        "confidence": 0.96, "timestamp": time.time(),
    })
    assert mock.sent[0]["priority"] == "P0"
    evt = next(e for e in db.get_events() if e["event_id"] == event_id)
    assert evt["priority"] == "P0"
    await engine.stop()


@pytest.mark.asyncio
async def test_acoustic_over_95db_is_critical(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    await engine.process_sensor_reading({
        "sensor_id": "AC-01", "sensor_type": "acoustic",
        "decibels": 102.0, "signature": "VEHICLE_ENGINE",
        "anomaly_detected": True, "confidence": 0.88, "timestamp": time.time(),
    })
    assert mock.sent[0]["priority"] == "P0"
    await engine.stop()


@pytest.mark.asyncio
async def test_motion_detection_generates_event(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    event_id = await engine.process_sensor_reading({
        "sensor_id": "MO-01", "sensor_type": "motion",
        "motion_detected": True, "confidence": 0.83, "timestamp": time.time(),
    })
    assert event_id is not None
    assert any(e["sensor_type"] == "motion" for e in db.get_events())
    await engine.stop()


@pytest.mark.asyncio
async def test_no_threat_produces_no_event_no_broadcast(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    result = await engine.process_sensor_reading({
        "sensor_id": "TH-01", "sensor_type": "thermal",
        "temperature_celsius": 21.0, "target_detected": False,
        "confidence": 0.15, "timestamp": time.time(),
    })
    assert result is None
    assert len(mock.sent) == 0
    assert len(db.get_events()) == 0
    await engine.stop()


@pytest.mark.asyncio
async def test_manual_event_trigger(tmp_path):
    db = make_db(tmp_path)
    mock = MockCommManager()
    engine = EventEngine("SYNAPSE-001", make_sensor_manager(), mock, db)
    await engine.start()

    event_id = await engine.trigger_manual_event(sensor_type="thermal", confidence=0.97)
    assert event_id.startswith("EVT-")
    assert len(mock.sent) == 1
    await engine.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 7. MessageRouter (live TCP)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_router_unicast_direct_delivery(tmp_path):
    received: List[Dict] = []

    async def handler_b(msg):
        received.append(msg)
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port = 19101
    server = TcpTransportServer("127.0.0.1", port, handler_b)
    await server.start()
    try:
        db_a = make_db(tmp_path)
        nm_a = NodeManager("SYNAPSE-001", db_a)
        router = MessageRouter("SYNAPSE-001", nm_a, TcpTransportClient(timeout=3.0), db_a)
        nm_a.register_peer("SYNAPSE-002", "127.0.0.1", port)

        msg = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_ALERT,
                                    {"text": "Border breach"}, priority=PRIORITY_P0)
        ok, delivered, failed = await router.forward_or_deliver(msg)

        assert ok is True
        assert "SYNAPSE-002" in delivered
        assert failed == []
        await asyncio.sleep(0.1)
        assert len(received) == 1
        assert received[0]["message_id"] == msg.message_id
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_router_broadcast_reaches_all_online_peers(tmp_path):
    recv_b: List[Dict] = []
    recv_c: List[Dict] = []

    async def hb(msg): recv_b.append(msg); return {"status": "ACK", "message_id": msg.get("message_id")}
    async def hc(msg): recv_c.append(msg); return {"status": "ACK", "message_id": msg.get("message_id")}

    port_b, port_c = 19102, 19103
    sb = TcpTransportServer("127.0.0.1", port_b, hb)
    sc = TcpTransportServer("127.0.0.1", port_c, hc)
    await sb.start(); await sc.start()

    try:
        db_a = make_db(tmp_path)
        nm_a = NodeManager("SYNAPSE-001", db_a)
        router = MessageRouter("SYNAPSE-001", nm_a, TcpTransportClient(timeout=3.0), db_a)
        nm_a.register_peer("SYNAPSE-002", "127.0.0.1", port_b)
        nm_a.register_peer("SYNAPSE-003", "127.0.0.1", port_c)

        msg = SynapseMessage.create("SYNAPSE-001", "BROADCAST", TYPE_TARGET_DETECTED,
                                    {"confidence": 0.96}, priority=PRIORITY_P0)
        ok, delivered, _ = await router.forward_or_deliver(msg)

        assert ok is True
        assert set(delivered) == {"SYNAPSE-002", "SYNAPSE-003"}
        await asyncio.sleep(0.1)
        assert len(recv_b) == 1
        assert len(recv_c) == 1
    finally:
        await sb.stop(); await sc.stop()


@pytest.mark.asyncio
async def test_router_skips_offline_peer_in_broadcast(tmp_path):
    received: List[Dict] = []

    async def handler(msg):
        received.append(msg)
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port = 19104
    server = TcpTransportServer("127.0.0.1", port, handler)
    await server.start()

    try:
        db_a = make_db(tmp_path)
        nm_a = NodeManager("SYNAPSE-001", db_a)
        router = MessageRouter("SYNAPSE-001", nm_a, TcpTransportClient(timeout=3.0), db_a)
        nm_a.register_peer("SYNAPSE-002", "127.0.0.1", port)
        nm_a.register_peer("SYNAPSE-003", "127.0.0.1", 19199)   # no server
        nm_a.set_status("SYNAPSE-003", STATUS_OFFLINE)           # explicitly offline

        msg = SynapseMessage.create("SYNAPSE-001", "BROADCAST", TYPE_ALERT, {})
        ok, delivered, _ = await router.forward_or_deliver(msg)

        assert ok is True
        assert "SYNAPSE-002" in delivered
        assert "SYNAPSE-003" not in delivered
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_router_ttl_zero_drops_packet(tmp_path):
    db_a = make_db(tmp_path)
    nm_a = NodeManager("SYNAPSE-001", db_a)
    router = MessageRouter("SYNAPSE-001", nm_a, TcpTransportClient(timeout=2.0), db_a)
    nm_a.register_peer("SYNAPSE-002", "127.0.0.1", 19105)

    msg = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_COMMAND, {})
    msg.ttl = 0

    ok, _, failed = await router.forward_or_deliver(msg)
    assert ok is False
    assert "SYNAPSE-002" in failed


@pytest.mark.asyncio
async def test_router_duplicate_suppression(tmp_path):
    received: List[Dict] = []

    async def handler(msg):
        received.append(msg)
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port = 19106
    server = TcpTransportServer("127.0.0.1", port, handler)
    await server.start()

    try:
        db_a = make_db(tmp_path)
        nm_a = NodeManager("SYNAPSE-001", db_a)
        router = MessageRouter("SYNAPSE-001", nm_a, TcpTransportClient(timeout=3.0), db_a)
        nm_a.register_peer("SYNAPSE-002", "127.0.0.1", port)

        msg = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_ALERT, {})
        ok1, _, _ = await router.forward_or_deliver(msg)
        ok2, d2, _ = await router.forward_or_deliver(msg)   # same message_id

        assert ok1 is True
        assert ok2 is False    # duplicate suppressed
        assert d2 == []
    finally:
        await server.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 8. End-to-End: Sensor → EventEngine → DB → Router → TCP → Grid Peer
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_sensor_to_grid_delivery(tmp_path):
    """
    Full pipeline: thermal detection on SYNAPSE-001 must arrive at SYNAPSE-002
    via real TCP transport with correct message type, priority, and source.
    """
    received_by_node_b: List[Dict] = []

    async def node_b_ingest(msg: Dict) -> Dict:
        received_by_node_b.append(msg)
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port_b = 19201
    server_b = TcpTransportServer("127.0.0.1", port_b, node_b_ingest)
    await server_b.start()

    try:
        db_a = make_db(tmp_path, "node_a.db")
        nm_a = NodeManager("SYNAPSE-001", db_a)
        tcp_client = TcpTransportClient(timeout=4.0)
        router_a = MessageRouter("SYNAPSE-001", nm_a, tcp_client, db_a)
        nm_a.register_peer("SYNAPSE-002", "127.0.0.1", port_b)

        # Thin real comm façade wired to actual router + transport
        class RealComm:
            async def send_message(self, destination_node, message_type, payload,
                                   priority="P2", event_id=None):
                msg = SynapseMessage.create(
                    "SYNAPSE-001", destination_node, message_type,
                    payload, priority=priority, event_id=event_id
                )
                ok, delivered, _ = await router_a.forward_or_deliver(msg)
                return {"success": ok, "delivered": delivered}

        engine = EventEngine("SYNAPSE-001", make_sensor_manager(), RealComm(), db_a)
        await engine.start()

        event_id = await engine.process_sensor_reading({
            "sensor_id": "TH-01", "sensor_type": "thermal",
            "temperature_celsius": 38.7, "target_detected": True,
            "confidence": 0.97, "timestamp": time.time(),
        })
        assert event_id is not None

        await asyncio.sleep(0.15)   # flush async TCP

        # ── Node B received the broadcast ───────────────────────────────────
        assert len(received_by_node_b) >= 1
        rx = received_by_node_b[0]
        assert rx["message_type"] == TYPE_TARGET_DETECTED
        assert rx["source_node"] == "SYNAPSE-001"
        assert rx["priority"] == "P0"           # confidence 0.97 > 0.90

        # ── Node A DB contains event + alert ───────────────────────────────
        assert any(e["event_id"] == event_id for e in db_a.get_events())
        assert any(a["event_id"] == event_id for a in db_a.get_alerts())

        await engine.stop()
    finally:
        await server_b.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 9. SYNC_REQUEST / SYNC_RESPONSE State Handshake
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_request_returns_recent_events(tmp_path):
    """
    Node B requests recent events from Node A via SYNC_REQUEST.
    Node A's handler returns the 5 pre-populated events.
    """
    db_a = make_db(tmp_path, "sync_a.db")
    for i in range(5):
        db_a.save_event(
            event_id=f"EVT-SYNC-{i:04d}",
            source_node="SYNAPSE-001",
            timestamp=time.time() - (5 - i),
            event_type=TYPE_TARGET_DETECTED,
            sensor_type="thermal",
            confidence=0.90 + i * 0.01,
            priority="P1"
        )

    async def sync_handler(msg: Dict) -> Dict:
        if msg.get("message_type") == TYPE_SYNC_REQUEST:
            since = float((msg.get("payload") or {}).get("since_timestamp", 0))
            events = db_a.get_events(limit=50, since=since if since else None)
            return {"status": "ACK", "message_id": msg.get("message_id"), "events": events}
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port_a = 19202
    server_a = TcpTransportServer("127.0.0.1", port_a, sync_handler)
    await server_a.start()

    try:
        client = TcpTransportClient(timeout=4.0)
        sync_msg = SynapseMessage.create(
            "SYNAPSE-002", "SYNAPSE-001",
            TYPE_SYNC_REQUEST, {"since_timestamp": 0}
        )
        ok, ack, err = await client.send_message("127.0.0.1", port_a, sync_msg.to_dict())
        assert ok is True
        assert ack["status"] == "ACK"
        assert len(ack["events"]) == 5
    finally:
        await server_a.stop()


# ─────────────────────────────────────────────────────────────────────────────
# 10. Store-and-Forward Queue: Offline → Recovered → Delivery
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_and_forward_enqueue_and_requeue(tmp_path):
    """
    When a peer is offline, messages are enqueued to the outbox.
    When the peer comes back online, the outbox should flush them.
    """
    db_a = make_db(tmp_path)
    nm_a = NodeManager("SYNAPSE-001", db_a)

    # Peer starts OFFLINE (no server)
    nm_a.register_peer("SYNAPSE-002", "127.0.0.1", 19301)
    nm_a.set_status("SYNAPSE-002", STATUS_OFFLINE)

    # Manually enqueue 3 messages (simulates what QueueManager does on failed send)
    for i in range(3):
        msg = SynapseMessage.create("SYNAPSE-001", "SYNAPSE-002", TYPE_ALERT,
                                    {"seq": i}, priority=PRIORITY_P1)
        db_a.enqueue_outbox(msg.message_id, "SYNAPSE-002", msg.to_dict(), "P1")

    assert db_a.get_outbox_count()["PENDING"] == 3

    # Simulate peer recovery: start server, mark ONLINE, flush outbox
    delivered_msgs: List[Dict] = []

    async def peer_handler(msg):
        delivered_msgs.append(msg)
        return {"status": "ACK", "message_id": msg.get("message_id")}

    port = 19301
    server = TcpTransportServer("127.0.0.1", port, peer_handler)
    await server.start()

    try:
        nm_a.set_status("SYNAPSE-002", STATUS_ONLINE)
        tcp_client = TcpTransportClient(timeout=3.0)
        router = MessageRouter("SYNAPSE-001", nm_a, tcp_client, db_a)

        # Flush outbox manually (what QueueManager.retry_pending_outbox does)
        pending = db_a.get_pending_outbox()
        for item in pending:
            ok, _, _ = await router.forward_or_deliver(
                SynapseMessage.from_dict(item["payload"])
            )
            db_a.update_outbox_attempt(item["message_id"], success=ok)

        await asyncio.sleep(0.1)
        assert len(delivered_msgs) == 3
        assert db_a.get_outbox_count()["DELIVERED"] == 3
        assert db_a.get_outbox_count()["PENDING"] == 0
    finally:
        await server.stop()
