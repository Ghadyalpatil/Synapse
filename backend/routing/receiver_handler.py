from backend.crypto.layered_encryption import (
    layered_encryption
)

from backend.websocket.event_emitter import (
    emit_event
)

from backend.node.peer_registry import (
    peer_registry
)


class ReceiverHandler:

    async def decrypt_packet(
        self,
        packet
    ):

        try:

            sender_id = packet[
                "source_id"
            ]

            encrypted_payload = packet[
                "payload"
            ]

            sender_peer = (
                peer_registry.get_peer(
                    sender_id
                )
            )

            if not sender_peer:

                raise Exception(
                    f"Sender {sender_id} "
                    f"not found in "
                    f"peer registry"
                )

            sender_public_key = (
                sender_peer[
                    "public_key"
                ]
            )

            plaintext = (
                layered_encryption
                .decrypt_for_hop(
                    sender_public_key,
                    encrypted_payload
                )
            )

            print(
                "\n===== DECRYPT DEBUG ====="
            )

            print(
                "Sender:",
                sender_id
            )

            print(
                "Encrypted:",
                encrypted_payload
            )

            print(
                "Plaintext:",
                plaintext
            )

            print(
                "Type:",
                type(plaintext)
            )

            print(
                "=========================\n"
            )

            await emit_event({

                "type":
                "MESSAGE_DECRYPTED",

                "packet_id":
                packet["packet_id"],

                "message":
                plaintext

            })

            return plaintext

        except Exception as e:

            print(
                "\n===== DECRYPT ERROR ====="
            )

            print(e)

            print(
                "=========================\n"
            )

            await emit_event({

                "type":
                "DECRYPTION_FAILED",

                "packet_id":
                packet["packet_id"],

                "error":
                str(e)

            })

            return None


receiver_handler = ReceiverHandler()