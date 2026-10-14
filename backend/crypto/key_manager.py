from pathlib import Path
from nacl.public import PrivateKey

from backend.config import NODE_ID


class KeyManager:

    def __init__(self):

        self.key_dir = Path("backend/keys")
        self.key_dir.mkdir(parents=True, exist_ok=True)

        self.private_key_path = (
            self.key_dir /
            f"{NODE_ID}_private.key"
        )

        self.public_key_path = (
            self.key_dir /
            f"{NODE_ID}_public.key"
        )

        self.private_key = self._load_or_create()

        self.public_key = (
            self.private_key.public_key
        )

    def _load_or_create(self):

        if self.private_key_path.exists():

            key_bytes = (
                self.private_key_path
                .read_bytes()
            )

            return PrivateKey(key_bytes)

        private_key = (
            PrivateKey.generate()
        )

        self.private_key_path.write_bytes(
            bytes(private_key)
        )

        self.public_key_path.write_bytes(
            bytes(private_key.public_key)
        )

        return private_key

    def get_public_key(self):

        return (
            bytes(self.public_key)
            .hex()
        )

    def get_private_key(self):

        return self.private_key


key_manager = KeyManager()