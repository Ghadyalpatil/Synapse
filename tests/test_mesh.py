import os
import sys
import json
import pytest
import sqlite3
import asyncio
from unittest.mock import AsyncMock, patch

from backend.packets.packet_schema import Packet
from backend.crypto.key_manager import KeyManager
from backend.crypto.layered_encryption import LayeredEncryption
from backend.routing.duplicate_filter import already_seen, mark_seen, seen_packets
from backend.routing.ttl_manager import update_packet
from backend.node.peer_registry import PeerRegistry
from backend.storage.packet_store import PacketStore
from backend.websocket import event_emitter


class TestPacketSchema:
    def test_packet_creation(self):
        pkt = Packet.create("NodeA", "NodeB", "Hello World")
        assert pkt.source_id == "NodeA"
        assert pkt.destination_id == "NodeB"
        assert pkt.payload == "Hello World"
        assert pkt.ttl == 5
        assert pkt.hop_count == 0
        assert pkt.route == []
        assert pkt.delivered is False
        assert pkt.packet_id is not None
        assert pkt.timestamp is not None

    def test_packet_to_dict(self):
        pkt = Packet.create("NodeA", "NodeB", "Test Data")
        d = pkt.to_dict()
        assert isinstance(d, dict)
        assert d["source_id"] == "NodeA"
        assert d["destination_id"] == "NodeB"
        assert d["payload"] == "Test Data"
        assert d["delivered"] is False
        assert d["ttl"] == 5


class TestCrypto:
    def test_key_manager_load_or_create(self, tmp_path, monkeypatch):
        # Test KeyManager with a temporary directory
        monkeypatch.chdir(tmp_path)
        km = KeyManager()
        pub_hex = km.get_public_key()
        assert isinstance(pub_hex, str)
        assert len(pub_hex) == 64  # Curve25519 public key is 32 bytes = 64 hex characters
        assert km.get_private_key() is not None

        # Re-instantiating KeyManager should load existing keys
        km2 = KeyManager()
        assert km2.get_public_key() == pub_hex

    def test_encryption_and_decryption_flow(self):
        from nacl.public import PrivateKey
        alice_priv = PrivateKey.generate()
        bob_priv = PrivateKey.generate()

        alice_pub_hex = bytes(alice_priv.public_key).hex()
        bob_pub_hex = bytes(bob_priv.public_key).hex()

        message = "Secret mesh network message 12345!@#$"

        # Alice encrypts message for Bob
        with patch("backend.crypto.layered_encryption.key_manager.get_private_key", return_value=alice_priv):
            le = LayeredEncryption()
            ciphertext = le.encrypt_for_hop(bob_pub_hex, message)

        assert isinstance(ciphertext, str)
        assert ciphertext != message

        # Bob decrypts message from Alice
        with patch("backend.crypto.layered_encryption.key_manager.get_private_key", return_value=bob_priv):
            le_bob = LayeredEncryption()
            decrypted = le_bob.decrypt_for_hop(alice_pub_hex, ciphertext)

        assert decrypted == message

    def test_tampered_ciphertext_fails(self):
        from nacl.public import PrivateKey
        from nacl.exceptions import CryptoError

        alice_priv = PrivateKey.generate()
        bob_priv = PrivateKey.generate()
        bob_pub_hex = bytes(bob_priv.public_key).hex()
        alice_pub_hex = bytes(alice_priv.public_key).hex()

        with patch("backend.crypto.layered_encryption.key_manager.get_private_key", return_value=alice_priv):
            le = LayeredEncryption()
            ciphertext = le.encrypt_for_hop(bob_pub_hex, "Secure payload")

        # Corrupt ciphertext
        tampered = ciphertext[:-4] + "0000"

        with patch("backend.crypto.layered_encryption.key_manager.get_private_key", return_value=bob_priv):
            le_bob = LayeredEncryption()
            with pytest.raises(Exception):
                le_bob.decrypt_for_hop(alice_pub_hex, tampered)


class TestRouting:
    def test_duplicate_filter(self):
        pkt_id = "test-packet-uuid-123"
        seen_packets.discard(pkt_id)

        assert not already_seen(pkt_id)
        mark_seen(pkt_id)
        assert already_seen(pkt_id)

    def test_ttl_manager(self):
        pkt = {
            "packet_id": "test-1",
            "ttl": 5,
            "hop_count": 0,
            "route": []
        }
        updated = update_packet(pkt)
        assert updated["ttl"] == 4
        assert updated["hop_count"] == 1
        assert len(updated["route"]) == 1
        assert updated["route"][0] == "TEST_NODE"


class TestPeerRegistry:
    def test_peer_lifecycle(self):
        registry = PeerRegistry()
        registry.add_peer("NodeB", "127.0.0.1", 9002, "abcdef123456")

        assert registry.peer_exists("NodeB")
        peer = registry.get_peer("NodeB")
        assert peer["ip"] == "127.0.0.1"
        assert peer["port"] == 9002
        assert peer["public_key"] == "abcdef123456"
        assert peer["online"] is True
        assert registry.get_public_key("NodeB") == "abcdef123456"

        registry.mark_offline("NodeB")
        assert registry.get_peer("NodeB")["online"] is False

        registry.mark_online("NodeB")
        assert registry.get_peer("NodeB")["online"] is True

        registry.remove_peer("NodeB")
        assert not registry.peer_exists("NodeB")
        assert registry.get_peer("NodeB") is None


class TestStorage:
    def test_packet_save_and_mark_delivered(self, tmp_path, monkeypatch):
        db_path = str(tmp_path / "test_mesh.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS packets (
                packet_id TEXT PRIMARY KEY,
                source_id TEXT,
                destination_id TEXT,
                payload TEXT,
                delivered INTEGER,
                route TEXT
            )
            '''
        )
        conn.commit()

        monkeypatch.setattr("backend.storage.packet_store.connection", conn)
        monkeypatch.setattr("backend.storage.packet_store.cursor", cur)

        store = PacketStore()
        pkt = {
            "packet_id": "pkt-999",
            "source_id": "NodeA",
            "destination_id": "NodeD",
            "payload": "encrypted_hex_payload",
            "delivered": False,
            "route": ["NodeA", "NodeB"]
        }

        store.save_packet(pkt)

        # Verify saved in SQLite
        cur.execute("SELECT packet_id, source_id, delivered, route FROM packets WHERE packet_id=?", ("pkt-999",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "pkt-999"
        assert row[1] == "NodeA"
        assert row[2] == 0
        assert json.loads(row[3]) == ["NodeA", "NodeB"]

        # Mark delivered
        store.mark_delivered("pkt-999")
        cur.execute("SELECT delivered FROM packets WHERE packet_id=?", ("pkt-999",))
        assert cur.fetchone()[0] == 1
        conn.close()


@pytest.mark.asyncio
class TestWebsocketEventEmitter:
    async def test_event_emitter_broadcast(self):
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await event_emitter.register_client(mock_ws1)
        await event_emitter.register_client(mock_ws2)

        test_event = {"type": "TEST_EVENT", "value": 42}
        await event_emitter.emit_event(test_event)

        expected_json = json.dumps(test_event)
        mock_ws1.send.assert_awaited_with(expected_json)
        mock_ws2.send.assert_awaited_with(expected_json)

        # Cleanup
        if mock_ws1 in event_emitter.connected_clients:
            event_emitter.connected_clients.remove(mock_ws1)
        if mock_ws2 in event_emitter.connected_clients:
            event_emitter.connected_clients.remove(mock_ws2)
