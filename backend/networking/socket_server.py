import asyncio
import json

from backend.routing.relay_engine import relay_engine
from backend.config import NODE_PORT
HOST = "0.0.0.0"
async def handle_connection(reader, writer):
    try:
        data = await reader.read(8192)
        if not data:
            return
        packet = json.loads(data.decode())
        await relay_engine.process_packet(packet)
        writer.write(b"ACK")
        await writer.drain()
        writer.close()
    except Exception as e:
        print(f"Socket Server Error: {e}")

async def start_socket_server():
    server = await asyncio.start_server(
        handle_connection, 
        HOST, 
        NODE_PORT
    )

    print(f"Socket Server Running: {NODE_PORT}")
    
    async with server:
        await server.serve_forever()