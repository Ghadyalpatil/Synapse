import asyncio
from backend.websocket.event_emitter import emit_event
from backend.node.peer_registry import peer_registry
from backend.config import HEARTBEAT_INTERVAL

async def heartbeat_loop():
    while True:
        peers = peer_registry.get_all_peers()

        await emit_event({
            "type": "HEARTBEAT", 
            "peer_count": len(peers)
        })
        
        await asyncio.sleep(HEARTBEAT_INTERVAL)