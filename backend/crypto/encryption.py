from nacl.secret import SecretBox
from nacl.utils import random

class EncryptionManager:
    def __init__(self):
        self.key = random(SecretBox.KEY_SIZE)
        self.box = SecretBox(self.key)

    def encrypt(self, plaintext: str) -> str:
        encrypted = self.box.encrypt(
            plaintext.encode("utf-8")
        )

        return encrypted.hex()

    def get_key(self):
        return self.key.hex()

encryption_manager = EncryptionManager()