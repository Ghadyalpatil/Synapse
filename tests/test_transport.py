"""
Unit tests for SYNAPSE TCP Transport
"""

import asyncio
import pytest

from synapse.communication.transport import TcpTransportClient, TcpTransportServer


@pytest.mark.asyncio
async def test_tcp_server_client_roundtrip():
    received_messages = []

    async def mock_handler(msg):
        received_messages.append(msg)
        return {
            "status": "ACK",
            "message_id": msg.get("message_id"),
            "reply": "CONFIRMED"
        }

    port = 15881
    server = TcpTransportServer(host="127.0.0.1", port=port, message_handler=mock_handler)
    await server.start()

    try:
        client = TcpTransportClient(timeout=3.0)

        # Test liveness ping probe
        alive, latency = await client.ping_probe("127.0.0.1", port)
        assert alive is True
        assert latency is not None and latency >= 0

        # Send framed payload
        test_msg = {
            "message_id": "MSG-TCP-01",
            "source_node": "SYNAPSE-001",
            "destination_node": "SYNAPSE-002",
            "message_type": "ALERT",
            "payload": {"text": "Perimeter intrusion alert"}
        }

        success, ack, err = await client.send_message("127.0.0.1", port, test_msg)
        assert success is True
        assert ack is not None
        assert ack["status"] == "ACK"
        assert ack["message_id"] == "MSG-TCP-01"
        assert ack["reply"] == "CONFIRMED"
        assert len(received_messages) == 1
        assert received_messages[0]["message_id"] == "MSG-TCP-01"

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_tcp_connection_refused():
    client = TcpTransportClient(timeout=1.0)
    # Port 15882 should be closed
    success, ack, err = await client.send_message("127.0.0.1", 15882, {"test": 1})
    assert success is False
    assert ack is None
    assert any(kw in err.lower() for kw in ("refused", "error", "timed out", "timeout"))
