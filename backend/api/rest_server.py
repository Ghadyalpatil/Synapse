from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.packets.packet_schema import Packet
from backend.node.node_identity import get_node_id
from backend.node.peer_registry import peer_registry

from backend.routing.relay_engine import relay_engine
from backend.websocket.event_emitter import emit_event
from backend.crypto.layered_encryption import (
    layered_encryption
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessageRequest(BaseModel):
    destination: str
    payload: str


@app.get("/")
async def root():
    return {
        "status": "mesh node online"
    }


@app.post("/send")
async def send_message(
    request: MessageRequest
):

    print(
        "\n========== API MESSAGE RECEIVED =========="
    )

    print(
        f"Destination : "
        f"{request.destination}"
    )

    print(
        f"Payload     : "
        f"{request.payload}"
    )

    destination_peer = (
        peer_registry.get_peer(
            request.destination
        )
    )

    if not destination_peer:

        print(
            f"ERROR: Node "
            f"{request.destination} "
            f"not found."
        )

        return {
            "status": "error",
            "message":
            f"Node "
            f"{request.destination} "
            f"not discovered"
        }

    destination_public_key = (
        destination_peer[
            "public_key"
        ]
    )

    print(
        "Destination Public Key Found"
    )

    encrypted_payload = (
        layered_encryption
        .encrypt_for_hop(
            destination_public_key,
            request.payload
        )
    )

    print(
        "Encryption Complete"
    )

    packet = Packet.create(
        source_id=get_node_id(),
        destination_id=request.destination,
        payload=encrypted_payload
    )

    print(
        f"Packet Created : "
        f"{packet.packet_id}"
    )

    await emit_event({
        "type":
        "MESSAGE_CREATED",

        "packet_id":
        packet.packet_id
    })

    await emit_event({
        "type":
        "LAYERED_ENCRYPTION_COMPLETE",

        "packet_id":
        packet.packet_id
    })

    print(
        "Calling Relay Engine..."
    )

    try:

        await relay_engine.process_packet(
            packet.to_dict()
        )

        print(
            "Relay Engine Returned Successfully"
        )

    except Exception as e:

        print(
            f"RELAY ENGINE ERROR: "
            f"{e}"
        )

        raise

    print(
        "========== API MESSAGE FINISHED ==========\n"
    )

    return {
        "status":
        "packet sent",

        "packet_id":
        packet.packet_id
    }