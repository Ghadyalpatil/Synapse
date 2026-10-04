"""
SYNAPSE — Tactical Command Centre Package
Zero-cloud, independent command & control station communicating with
edge surveillance nodes across the SYNAPSE mesh grid.
"""

from .server import create_command_center_app

__all__ = ["create_command_center_app"]
