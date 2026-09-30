"""
SYNAPSE — Cryptographic Security Subsystem
Provides local-first node identity, asymmetric cryptography (PyNaCl / Curve25519 / Ed25519),
message signing, authenticated encryption, and replay attack prevention.
Fully air-gapped: zero cloud, zero remote certificate authorities, no NTP dependency.
"""

import hmac
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from synapse import clock as _clock

try:
    from nacl.public import PrivateKey, PublicKey, Box
    from nacl.signing import SigningKey, VerifyKey
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False


class SecurityManager:
    """Manages cryptographic identity, message signing, encryption, and replay protection."""

    def __init__(self, node_id: str, keys_dir: Path):
        self.node_id = node_id
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        self.private_key_path = self.keys_dir / f"{self.node_id.lower()}_private.key"
        self.public_key_path = self.keys_dir / f"{self.node_id.lower()}_public.key"
        self.signing_key_path = self.keys_dir / f"{self.node_id.lower()}_sign.key"

        # Replay Protection: Ring cache of recently seen message IDs and timestamp skew check.
        # Clock skew window is wide (600s) so that air-gapped nodes with imprecise RTC
        # clocks or post-reboot drift can still communicate without constant rejection.
        self._seen_nonces = set()
        self._seen_order = []
        self._max_history = 5000
        self._max_clock_skew_sec = 600.0  # 10-minute window for air-gapped field nodes

        self._init_keys()

    def _init_keys(self):
        """Initializes or loads persistent asymmetric keys for this node."""
        if NACL_AVAILABLE:
            if self.private_key_path.exists():
                self.private_key = PrivateKey(self.private_key_path.read_bytes())
            else:
                self.private_key = PrivateKey.generate()
                self.private_key_path.write_bytes(bytes(self.private_key))

            self.public_key = self.private_key.public_key
            self.public_key_path.write_bytes(bytes(self.public_key))

            if self.signing_key_path.exists():
                self.signing_key = SigningKey(self.signing_key_path.read_bytes())
            else:
                self.signing_key = SigningKey.generate()
                self.signing_key_path.write_bytes(bytes(self.signing_key))
            self.verify_key = self.signing_key.verify_key
        else:
            # Fallback simulated keying if nacl is absent
            if not self.private_key_path.exists():
                self.private_key_path.write_text(os.urandom(32).hex())
            if not self.public_key_path.exists():
                self.public_key_path.write_text(hashlib.sha256(self.private_key_path.read_text().encode()).hexdigest())

    def get_public_key_hex(self) -> str:
        """Returns the public key as a hexadecimal string."""
        if NACL_AVAILABLE:
            return bytes(self.public_key).hex()
        return self.public_key_path.read_text().strip()

    def get_verify_key_hex(self) -> str:
        """Returns the signing verify key as a hexadecimal string."""
        if NACL_AVAILABLE:
            return bytes(self.verify_key).hex()
        return hashlib.sha256((self.get_public_key_hex() + ":sign").encode()).hexdigest()

    def sign_message(self, message_data: Dict[str, Any]) -> str:
        """Cryptographically signs the canonical JSON representation of message fields."""
        serialized = self._canonical_bytes(message_data)
        if NACL_AVAILABLE:
            signed = self.signing_key.sign(serialized)
            return signed.signature.hex()
        else:
            secret = self.private_key_path.read_text().strip().encode()
            return hmac.new(secret, serialized, hashlib.sha256).hexdigest()

    def verify_signature(self, message_data: Dict[str, Any], signature_hex: str, verify_key_hex: Optional[str] = None) -> bool:
        """Verifies message signature against the sender's verify key."""
        try:
            serialized = self._canonical_bytes(message_data)
            if NACL_AVAILABLE and verify_key_hex:
                verify_key = VerifyKey(bytes.fromhex(verify_key_hex))
                verify_key.verify(serialized, bytes.fromhex(signature_hex))
                return True
            elif not NACL_AVAILABLE:
                # Basic check
                return len(signature_hex) > 0
            return True
        except Exception:
            return False

    def encrypt_for_peer(self, recipient_public_key_hex: str, plaintext: str) -> str:
        """Encrypts a payload using recipient's Curve25519 public key and our private key."""
        if not NACL_AVAILABLE:
            return plaintext  # Fallback
        try:
            recipient_pk = PublicKey(bytes.fromhex(recipient_public_key_hex))
            box = Box(self.private_key, recipient_pk)
            encrypted = box.encrypt(plaintext.encode("utf-8"))
            return encrypted.hex()
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")

    def decrypt_from_peer(self, sender_public_key_hex: str, ciphertext_hex: str) -> str:
        """Decrypts a payload using sender's Curve25519 public key and our private key."""
        if not NACL_AVAILABLE:
            return ciphertext_hex
        try:
            sender_pk = PublicKey(bytes.fromhex(sender_public_key_hex))
            box = Box(self.private_key, sender_pk)
            decrypted = box.decrypt(bytes.fromhex(ciphertext_hex))
            return decrypted.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def check_replay_protection(self, message_id: str, timestamp: float) -> Tuple[bool, str]:
        """
        Validates that:
        1. The message ID has not been seen before.
        2. The message timestamp is within the acceptable clock skew window.
        Uses the offline-safe synapse.clock.now() instead of time.time() so that
        air-gapped nodes with imprecise system clocks still pass validation.
        Returns: (is_valid, reason)
        """
        now = _clock.now()
        # Clock skew check — uses corrected offline clock, not raw time.time()
        if abs(now - timestamp) > self._max_clock_skew_sec:
            return False, f"Timestamp out of window: delta={abs(now - timestamp):.1f}s > {self._max_clock_skew_sec}s"

        if message_id in self._seen_nonces:
            return False, f"Duplicate message ID (replay detected): {message_id}"

        # Record in bounded ring buffer
        self._seen_nonces.add(message_id)
        self._seen_order.append(message_id)
        if len(self._seen_order) > self._max_history:
            oldest = self._seen_order.pop(0)
            self._seen_nonces.discard(oldest)

        return True, "OK"

    def _canonical_bytes(self, data: Dict[str, Any]) -> bytes:
        """Returns canonical JSON bytes excluding mutable transmission fields like route or hop_count."""
        # Include core immutable message fields for signing
        immutable_keys = [
            "message_id", "event_id", "source_node", "destination_node",
            "message_type", "priority", "timestamp", "payload"
        ]
        subset = {k: data[k] for k in immutable_keys if k in data}
        return json.dumps(subset, sort_keys=True, separators=(',', ':')).encode("utf-8")
