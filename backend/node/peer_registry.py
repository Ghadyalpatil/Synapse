class PeerRegistry:

    def __init__(self):

        self.peers = {}

    def add_peer(
        self,
        node_id,
        ip,
        port,
        public_key
    ):

        self.peers[node_id] = {
            "ip": ip,
            "port": port,
            "public_key": public_key,
            "online": True
        }

    def remove_peer(
        self,
        node_id
    ):

        if node_id in self.peers:
            del self.peers[node_id]

    def mark_offline(
        self,
        node_id
    ):

        if node_id in self.peers:
            self.peers[node_id][
                "online"
            ] = False

    def mark_online(
        self,
        node_id
    ):

        if node_id in self.peers:
            self.peers[node_id][
                "online"
            ] = True

    def get_peer(
        self,
        node_id
    ):

        return self.peers.get(
            node_id
        )

    def get_public_key(
        self,
        node_id
    ):

        peer = self.get_peer(
            node_id
        )

        if not peer:
            return None

        return peer.get(
            "public_key"
        )

    def get_all_peers(
        self
    ):

        return self.peers

    def peer_exists(
        self,
        node_id
    ):

        return (
            node_id
            in self.peers
        )


peer_registry = PeerRegistry()