from nacl.secret import SecretBox

class DecryptionManager:
    def decrypt(self, encrypted_text: str, key_hex: str) -> str:
        try:
            key = bytes.fromhex(key_hex)

            box = SecretBox(key)

            decrypted = box.decrypt(
                bytes.fromhex(encrypted_text)
            )

            return decrypted.decode("utf-8")

        except Exception as e:
            print(
                f"Decryption Error: {e}"
            )

            return ""

decryption_manager = DecryptionManager()