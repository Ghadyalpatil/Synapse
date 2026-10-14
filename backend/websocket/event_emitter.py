import json

connected_clients=set()

async def register_client(websocket):
    connected_clients.add(websocket)

async def unregister_client(websocket):
    connected_clients.discard(websocket)

async def emit_event(event):
    if not connected_clients:
        return
    
    message = json.dumps(event)
    
    dead_clients = []
    for client in connected_clients:
        try:
            await client.send(message)
        except:
            dead_clients.append(client)
            
    for client in dead_clients:
        connected_clients.remove(client)