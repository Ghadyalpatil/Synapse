"""
Unit tests for SYNAPSE Protocol & Framing
"""

import asyncio
import io
import pytest

from synapse.communication.protocol import (
    SynapseMessage,
    frame_message,
    read_framed_message,
    normalize_priority,
    normalize_type,
    HEADER_SIZE,
    PRIORITY_P0,
    PRIORITY_P1,
    PRIORITY_P2,
    TYPE_ALERT,
    TYPE_TARGET_DETECTED
)
from synapse.communication.router import DuplicateFilter


def test_message_creation():
    msg = SynapseMessage.create(
        source_node="SYNAPSE-001",
        destination_node="SYNAPSE-002",
        message_type="TARGET_DETECTED",
        payload={"sensor": "thermal", "confidence": 0.94},
        priority="P1",
        ttl=5
    )

    assert msg.message_id.startswith("MSG-")
    assert msg.source_node == "SYNAPSE-001"
    assert msg.destination_node == "SYNAPSE-002"
    assert msg.message_type == TYPE_TARGET_DETECTED
    assert msg.priority == PRIORITY_P1
    assert msg.ttl == 5
    assert msg.hop_count == 0
    assert msg.route == ["SYNAPSE-001"]


def test_priority_and_type_normalization():
    assert normalize_priority("p0") == "P0"
    assert normalize_priority("INVALID") == "P2"
    assert normalize_type("target_detected") == "TARGET_DETECTED"
    assert normalize_type("NON_EXISTENT") == "SENSOR_DATA"


def test_dict_serialization_cycle():
    msg = SynapseMessage.create(
        source_node="SYNAPSE-003",
        destination_node="BROADCAST",
        message_type="ALERT",
        payload={"alert": "Breach Sector 4"},
        priority="P0"
    )
    d = msg.to_dict()
    reconstructed = SynapseMessage.from_dict(d)

    assert reconstructed.message_id == msg.message_id
    assert reconstructed.source_node == msg.source_node
    assert reconstructed.destination_node == msg.destination_node
    assert reconstructed.message_type == msg.message_type
    assert reconstructed.priority == msg.priority
    assert reconstructed.payload == msg.payload


@pytest.mark.asyncio
async def test_length_prefixed_framing():
    data = {
        "message_id": "MSG-TEST12345",
        "source": "SYNAPSE-001",
        "content": "Tactical Order 101"
    }

    framed_bytes = frame_message(data)
    assert len(framed_bytes) > HEADER_SIZE

    # Simulate reading from asyncio StreamReader
    reader = asyncio.StreamReader()
    reader.feed_data(framed_bytes)
    reader.feed_eof()

    decoded = await read_framed_message(reader)
    assert decoded is not None
    assert decoded["message_id"] == "MSG-TEST12345"
    assert decoded["content"] == "Tactical Order 101"


@pytest.mark.asyncio
async def test_fragmented_tcp_stream():
    """Simulates TCP packets arriving in fragmented chunks."""
    data = {"packet": "FRAG_TEST", "value": 42}
    framed = frame_message(data)

    reader = asyncio.StreamReader()
    # Feed header first
    reader.feed_data(framed[:HEADER_SIZE])
    # Then feed half payload
    reader.feed_data(framed[HEADER_SIZE:HEADER_SIZE + 5])
    # Then feed remainder
    reader.feed_data(framed[HEADER_SIZE + 5:])
    reader.feed_eof()

    decoded = await read_framed_message(reader)
    assert decoded is not None
    assert decoded["packet"] == "FRAG_TEST"
    assert decoded["value"] == 42


def test_duplicate_filter():
    df = DuplicateFilter(max_history=5)
    assert not df.is_duplicate("MSG-01")
    df.mark_seen("MSG-01")
    assert df.is_duplicate("MSG-01")

    # Add more to test ring buffer
    for i in range(2, 7):
        df.mark_seen(f"MSG-0{i}")

    # Oldest (MSG-01) should have rotated out
    assert not df.is_duplicate("MSG-01")
    assert df.is_duplicate("MSG-06")
