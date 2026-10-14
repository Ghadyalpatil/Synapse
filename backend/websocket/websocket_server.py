import asyncio
import websockets

from backend.websocket.event_emitter import (
    register_client,
    unregister_client
)

from backend.config import WEBSOCKET_PORT


async def handler(ws):

    await register_client(ws)

    try:
        async for message in ws:
            pass

    finally:
        await unregister_client(ws)


async def start_websocket_server():

    async with websockets.serve(
        handler,
        "0.0.0.0",
        WEBSOCKET_PORT
    ):

        print(
            f"WebSocket Running: {WEBSOCKET_PORT}"
        )

        await asyncio.Future()