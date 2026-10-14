import asyncio
from backend.websocket.event_emitter import emit_event
from backend.node.peer_registry import peer_registry

async def synchronization_loop():
    while True:
        await emit_event({
            "type": "TOPOLOGY_UPDATE",
            "peers": peer_registry.get_all_peers()
        })
        await asyncio.sleep(3)