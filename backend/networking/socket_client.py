import asyncio
import json
async def send_packet(ip, port, packet):
    try:
        reader, writer = await asyncio.open_connection(ip, port)
        writer.write(json.dumps(packet).encode())
        await writer.drain()
        response = await reader.read(1024)
        print(f"Response: {response.decode()}")
        writer.close()
        await writer.wait_closed()
        
    except Exception as e:
        print(f"Socket Client Error: {e}")