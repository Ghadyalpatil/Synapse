from backend.node.peer_registry import peer_registry
from backend.networking.socket_client import send_packet

class MeshRouter:

    async def forward_packet(self, packet, exclude=None):

        peers = peer_registry.get_all_peers()

        print("\n===== FORWARD PACKET =====")
        print("Peers Found:")
        print(peers)

        for node_id, peer in peers.items():

            print(f"Trying Peer: {node_id}")

            if exclude and node_id == exclude:
                continue

            if not peer["online"]:
                continue

            print(f"Sending To {peer['ip']}:{peer['port']}")

            await send_packet(
                peer["ip"],
                peer["port"],
                packet
            )

mesh_router = MeshRouter()