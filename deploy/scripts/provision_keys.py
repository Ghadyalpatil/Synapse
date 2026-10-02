#!/usr/bin/env python3
"""
SYNAPSE Key Provisioning Utility
Pre-generates Ed25519 signing keys and Curve25519 encryption keys for a grid node.
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from synapse.communication.security import SecurityManager


def main():
    parser = argparse.ArgumentParser(description="Generate cryptographic keys for a SYNAPSE node")
    parser.add_argument("--node-id", required=True, help="Node ID (e.g. SYNAPSE-001)")
    parser.add_argument("--keys-dir", default="var/keys", help="Target keys directory")
    args = parser.parse_args()

    target_dir = Path(args.keys_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    sec = SecurityManager(args.node_id, target_dir)
    print(f"[+] Cryptographic identity generated for [{args.node_id}]")
    print(f"    Public Key (Curve25519, hex) : {sec.get_public_key_hex()}")
    print(f"    Verify Key (Ed25519, hex)   : {sec.get_verify_key_hex()}")
    print(f"[+] Key files stored in: {target_dir.resolve()}")
    print("")
    print("[!] Share the Verify Key with all peer nodes so they can verify your signatures.")


if __name__ == "__main__":
    main()
