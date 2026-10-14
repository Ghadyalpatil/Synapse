import asyncio

from backend.networking.socket_server import start_socket_server
from backend.websocket.websocket_server import start_websocket_server
from backend.networking.peer_discovery import start_peer_services
from backend.node.heartbeat import heartbeat_loop
from backend.node.node_sync import synchronization_loop
from backend.api.start_api import start_api_server


async def main():

    await asyncio.gather(
        start_socket_server(),
        start_websocket_server(),
        start_peer_services(),
        heartbeat_loop(),
        synchronization_loop(),
        start_api_server()
    )


if __name__ == "__main__":
    asyncio.run(main())