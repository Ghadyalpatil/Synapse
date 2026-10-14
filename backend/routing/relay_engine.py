from backend.routing.duplicate_filter import (
    already_seen,
    mark_seen
)

from backend.routing.ttl_manager import update_packet
from backend.routing.mesh_router import mesh_router
from backend.websocket.event_emitter import emit_event
from backend.storage.packet_store import packet_store
from backend.config import NODE_ID
from backend.routing.receiver_handler import receiver_handler

print("RELAY ENGINE VERSION 2 LOADED")


class RelayEngine:

    async def process_packet(self, packet):

        print("\n==============================")
        print("RELAY ENGINE CALLED")
        print("==============================")
        print(packet)

        packet_id = packet["packet_id"]

        print(f"Processing Packet: {packet_id}")

        if already_seen(packet_id):
            print("Packet already seen. Ignoring.")
            return

        print("Packet is new.")

        mark_seen(packet_id)

        print("Packet marked as seen.")

        packet_store.save_packet(packet)

        print("Packet saved to database.")

        await emit_event({
            "type": "PACKET_RECEIVED",
            "packet_id": packet_id,
            "current_node": NODE_ID
        })

        print("PACKET_RECEIVED event emitted.")

        # Destination reached
        if packet["destination_id"] == NODE_ID:

            print("Destination reached.")

            packet["delivered"] = True

            packet_store.mark_delivered(packet_id)

            print("Packet marked delivered.")

            print("Calling decrypt_packet()...")

            message = await receiver_handler.decrypt_packet(packet)

            print("decrypt_packet() returned.")
            print(f"Decrypted Message: {message}")

            await emit_event({
                "type": "MESSAGE_DECRYPTED",
                "message": message
            })

            await emit_event({
                "type": "MESSAGE_DELIVERED",
                "packet_id": packet_id,
                "destination": NODE_ID,
                "route": packet["route"]
            })

            print("MESSAGE_DELIVERED event emitted.")

            return

        # TTL check
        if packet["ttl"] <= 0:

            print("TTL expired. Dropping packet.")

            await emit_event({
                "type": "PACKET_DROPPED",
                "packet_id": packet_id
            })

            return

        print(f"TTL before update: {packet['ttl']}")

        packet = update_packet(packet)

        print(f"TTL after update: {packet['ttl']}")
        print(f"Hop Count: {packet['hop_count']}")
        print(f"Route: {packet['route']}")

        await emit_event({
            "type": "HOP_COMPLETED",
            "packet_id": packet_id,
            "hop_count": packet["hop_count"],
            "route": packet["route"]
        })

        print("HOP_COMPLETED event emitted.")

        print("Calling mesh_router.forward_packet()")

        await mesh_router.forward_packet(packet)

        print("mesh_router.forward_packet() completed.")


relay_engine = RelayEngine()