from zeroconf import (
    Zeroconf,
    ServiceBrowser,
    ServiceInfo
)

import socket
import asyncio

from backend.config import (
    NODE_ID,
    NODE_PORT
)

from backend.node.peer_registry import (
    peer_registry
)

from backend.crypto.key_manager import (
    key_manager
)

SERVICE_TYPE = "_meshnode._tcp.local."

zeroconf = Zeroconf()


class DiscoveryListener:

    def add_service(
        self,
        zeroconf,
        service_type,
        name
    ):

        info = zeroconf.get_service_info(
            service_type,
            name
        )

        if not info:
            return

        try:

            node_id = (
                name.split(".")[0]
            )

            if node_id == NODE_ID:
                return

            ip = socket.inet_ntoa(
                info.addresses[0]
            )

            port = info.port

            public_key = (
                info.properties
                .get(
                    b"public_key",
                    b""
                )
                .decode()
            )

            peer_registry.add_peer(
                node_id,
                ip,
                port,
                public_key
            )

            print(
                f"Discovered Node: "
                f"{node_id} -> "
                f"{ip}:{port}"
            )

            print(
                f"Public Key: "
                f"{public_key[:30]}..."
            )

        except Exception as e:

            print(
                f"Discovery Error: {e}"
            )

    def remove_service(
        self,
        zeroconf,
        service_type,
        name
    ):
        pass

    def update_service(
        self,
        zeroconf,
        service_type,
        name
    ):
        pass


async def start_peer_services():

    hostname = socket.gethostname()

    ip = socket.gethostbyname(
        hostname
    )

    service_info = ServiceInfo(
        SERVICE_TYPE,
        f"{NODE_ID}.{SERVICE_TYPE}",
        addresses=[
            socket.inet_aton(ip)
        ],
        port=NODE_PORT,
        properties={
            b"public_key":
            key_manager
            .get_public_key()
            .encode()
        },
        server=f"{hostname}.local."
    )

    zeroconf.register_service(
        service_info
    )

    print(
        f"Advertising Node {NODE_ID}"
    )

    print(
        f"Public Key: "
        f"{key_manager.get_public_key()[:30]}..."
    )

    listener = DiscoveryListener()

    ServiceBrowser(
        zeroconf,
        SERVICE_TYPE,
        listener
    )

    while True:
        await asyncio.sleep(1)