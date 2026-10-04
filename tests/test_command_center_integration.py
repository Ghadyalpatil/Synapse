"""
SYNAPSE — Integration Tests: Edge Module -> Command Centre Telemetry Pipeline
Verifies that:
1. Edge module transmits raw sensor data (thermal, acoustic, motion) using
   the independent binary TCP framed protocol with Ed25519 signatures.
2. Command Centre receives, cryptographically verifies, and ingests all sensor readings.
3. Command Centre REST API and topology queries expose the live sensor inputs.
4. Command Centre can dispatch operational commands (e.g. SAMPLE_SENSORS) over the mesh.
"""

import asyncio
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport

from synapse.command_center.server import create_command_center_app
from synapse.communication.manager import CommunicationManager
from synapse.communication.node_manager import STATUS_ONLINE
from synapse.communication.protocol import (
    TYPE_ALERT,
    TYPE_COMMAND,
    TYPE_SENSOR_DATA,
    TYPE_TARGET_DETECTED
)
from synapse.processing.event_engine import EventEngine
from synapse.sensors.sensor_engine import SensorManager
from synapse.storage.database import Database


@pytest.fixture
def test_setup(tmp_path: Path):
    db_node = Database(tmp_path / "node1.db")
    db_cc = Database(tmp_path / "command_center.db")

    keys_node = tmp_path / "keys_node1"
    keys_cc = tmp_path / "keys_cc"

    # Communication managers on free loopback ports
    comm_node = CommunicationManager(
        node_id="SYNAPSE-001",
        comm_port=6101,
        discovery_port=6102,
        broadcast_ip="127.0.0.255",
        db=db_node,
        keys_dir=keys_node
    )

    comm_cc = CommunicationManager(
        node_id="COMMAND-CENTER",
        comm_port=6103,
        discovery_port=6104,
        broadcast_ip="127.0.0.255",
        db=db_cc,
        keys_dir=keys_cc
    )

    sensor_mgr = SensorManager()
    event_engine = EventEngine(
        node_id="SYNAPSE-001",
        sensor_manager=sensor_mgr,
        comm_manager=comm_node,
        db=db_node,
        stream_telemetry=True,
        telemetry_target="COMMAND-CENTER"
    )

    cc_app = create_command_center_app(comm_cc, db_cc)

    return {
        "comm_node": comm_node,
        "comm_cc": comm_cc,
        "event_engine": event_engine,
        "sensor_mgr": sensor_mgr,
        "db_node": db_node,
        "db_cc": db_cc,
        "cc_app": cc_app
    }


@pytest.mark.asyncio
async def test_sensor_telemetry_transmission_to_command_center(test_setup):
    comm_node = test_setup["comm_node"]
    comm_cc = test_setup["comm_cc"]
    event_engine = test_setup["event_engine"]
    db_cc = test_setup["db_cc"]
    cc_app = test_setup["cc_app"]

    # Start communication layers
    await comm_cc.start()
    await comm_node.start()
    await event_engine.start()

    try:
        # Register Command Centre as a peer in Edge Node
        comm_node.node_manager.register_peer(
            node_id="COMMAND-CENTER",
            ip="127.0.0.1",
            port=6103,
            public_key=comm_cc.security.get_public_key_hex(),
            verify_key=comm_cc.security.get_verify_key_hex()
        )

        # Register Edge Node in Command Centre
        comm_cc.node_manager.register_peer(
            node_id="SYNAPSE-001",
            ip="127.0.0.1",
            port=6101,
            public_key=comm_node.security.get_public_key_hex(),
            verify_key=comm_node.security.get_verify_key_hex()
        )

        # 1. Edge Node broadcasts multi-sensor telemetry across the independent mesh
        result = await event_engine.broadcast_sensor_telemetry()
        assert result is not None
        assert result.get("success") is True
        assert result.get("status") == "DELIVERED"

        # Wait briefly for async ingestion
        await asyncio.sleep(0.3)

        # 2. Verify Command Centre SQLite received and persisted all sensor readings
        readings = db_cc.get_sensor_readings(limit=10)
        assert len(readings) >= 3  # Thermal, Acoustic, Motion

        sensor_types = {r["sensor_type"] for r in readings}
        assert "thermal" in sensor_types
        assert "acoustic" in sensor_types
        assert "motion" in sensor_types

        # Verify source_node was preserved across the wire
        for r in readings:
            assert r["source_node"] == "SYNAPSE-001"

        # 3. Test Command Centre REST API
        transport = ASGITransport(app=cc_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["node_id"] == "COMMAND-CENTER"
            assert data["total_sensors_reporting"] >= 3

            latest_resp = await client.get("/api/sensors/latest")
            assert latest_resp.status_code == 200
            latest_data = latest_resp.json()
            assert len(latest_data) >= 3

            # 4. Command Centre issues operational command back to Edge Node over mesh
            cmd_resp = await client.post("/api/command", json={
                "target_node": "SYNAPSE-001",
                "command": "SAMPLE_SENSORS",
                "priority": "P1"
            })
            assert cmd_resp.status_code == 200
            cmd_data = cmd_resp.json()
            assert cmd_data.get("status") == "DELIVERED"

    finally:
        await event_engine.stop()
        await comm_node.stop()
        await comm_cc.stop()
