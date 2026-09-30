# SYNAPSE Cryptographic Security Model

## 1. Threat Model & Constraints

SYNAPSE operates in physically insecure, contested perimeter environments:
- Nodes may be intercepted or monitored over wireless / wired mesh links.
- Attackers may replay intercepted alert messages to cause denial of service or misdirection.
- No public key infrastructure (PKI) or certificate authority is available (air-gapped zero-cloud requirement).

## 2. Cryptographic Primitives

SYNAPSE relies on modern high-speed elliptic curve cryptography (PyNaCl / libsodium):

1. **Digital Signatures (Ed25519)**:
   - Every node maintains an Ed25519 signing keypair (`ed25519.key` and `ed25519.pub`).
   - Every transmitted message payload is signed by the originating node.
   - Receiving peers verify the Ed25519 signature before routing or executing the packet.
2. **Authenticated Encryption (Curve25519 / XSalsa20-Poly1305)**:
   - Point-to-point payloads containing confidential tactical intelligence are encrypted using libsodium sealed boxes or authenticated shared boxes.
3. **Replay Defense Window**:
   - Packets include a monotonic epoch timestamp.
   - Nodes reject packets older than 60 seconds.
   - A ring buffer duplicate filter tracks message IDs to prevent duplicate replays within the active window.
