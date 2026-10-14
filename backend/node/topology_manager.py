from backend.node.peer_registry import peer_registry

class TopologyManager:
    def __init__(self):
        self.topology = {}

    def update_topology(self):
        peers = peer_registry.get_all_peers()

        self.topology = {
            "nodes": list(peers.keys()),
            "connections": [
                {
                    "source": node_id,
                    "target": node_id
                }
                for node_id in peers.keys()
            ]
        }

    def get_topology(self):
        self.update_topology()
        return self.topology

    def peer_count(self):
        return len(
            peer_registry.get_all_peers()
        )

topology_manager = TopologyManager()