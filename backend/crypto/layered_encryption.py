from nacl.public import (
    PublicKey,
    Box
)

from backend.crypto.key_manager import (
    key_manager
)


class LayeredEncryption:

    def encrypt_for_hop(
        self,
        destination_public_key_hex,
        message
    ):

        recipient_public_key = PublicKey(
            bytes.fromhex(
                destination_public_key_hex
            )
        )

        sender_private_key = (
            key_manager.get_private_key()
        )

        box = Box(
            sender_private_key,
            recipient_public_key
        )

        encrypted = box.encrypt(
            message.encode()
        )

        return encrypted.hex()

    def decrypt_for_hop(
        self,
        sender_public_key_hex,
        encrypted_message
    ):

        sender_public_key = PublicKey(
            bytes.fromhex(
                sender_public_key_hex
            )
        )

        receiver_private_key = (
            key_manager.get_private_key()
        )

        box = Box(
            receiver_private_key,
            sender_public_key
        )

        decrypted = box.decrypt(
            bytes.fromhex(
                encrypted_message
            )
        )

        return decrypted.decode()


layered_encryption = (
    LayeredEncryption()
)