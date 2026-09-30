"""
SYNAPSE — Communication Protocol & Message Framing
Standardized binary framing ([4-byte big-endian length][JSON payload]) and
message model for zero-cloud local-grid Raspberry Pi communication.
"""

import asyncio
import json
import struct
import uuid
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

from synapse import clock

# Priority Tiers
PRIORITY_P0 = "P0"  # Critical alerts, SOS, urgent commands
PRIORITY_P1 = "P1"  # Target detections, intrusion events, status changes
PRIORITY_P2 = "P2"  # Routine sensor telemetry, heartbeats, sync
PRIORITY_LEVELS = (PRIORITY_P0, PRIORITY_P1, PRIORITY_P2)
DEFAULT_PRIORITY = PRIORITY_P2

# Message Types
TYPE_DISCOVERY = "DISCOVERY"
TYPE_DISCOVERY_RESPONSE = "DISCOVERY_RESPONSE"
TYPE_HEARTBEAT = "HEARTBEAT"
TYPE_NODE_STATUS = "NODE_STATUS"
TYPE_SENSOR_DATA = "SENSOR_DATA"
TYPE_TARGET_DETECTED = "TARGET_DETECTED"
TYPE_ALERT = "ALERT"
TYPE_COMMAND = "COMMAND"
TYPE_COMMAND_ACK = "COMMAND_ACK"
TYPE_SYNC_REQUEST = "SYNC_REQUEST"
TYPE_SYNC_RESPONSE = "SYNC_RESPONSE"
TYPE_ROUTE_UPDATE = "ROUTE_UPDATE"
TYPE_ERROR = "ERROR"

MESSAGE_TYPES = (
    TYPE_DISCOVERY,
    TYPE_DISCOVERY_RESPONSE,
    TYPE_HEARTBEAT,
    TYPE_NODE_STATUS,
    TYPE_SENSOR_DATA,
    TYPE_TARGET_DETECTED,
    TYPE_ALERT,
    TYPE_COMMAND,
    TYPE_COMMAND_ACK,
    TYPE_SYNC_REQUEST,
    TYPE_SYNC_RESPONSE,
    TYPE_ROUTE_UPDATE,
    TYPE_ERROR
)

# Header format: 4-byte big-endian integer
HEADER_FORMAT = "!I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_MESSAGE_SIZE = 16 * 1024 * 1024  # 16 MB limit


def normalize_priority(priority: Optional[str]) -> str:
    """Normalizes priority to P0, P1, or P2."""
    if priority and priority.upper() in PRIORITY_LEVELS:
        return priority.upper()
    return DEFAULT_PRIORITY


def normalize_type(msg_type: Optional[str]) -> str:
    """Validates message type or falls back to SENSOR_DATA."""
    if msg_type and msg_type.upper() in MESSAGE_TYPES:
        return msg_type.upper()
    return TYPE_SENSOR_DATA


@dataclass
class SynapseMessage:
    """Standard SYNAPSE Message Model."""
    message_id: str
    source_node: str
    destination_node: str
    message_type: str
    payload: Any
    event_id: Optional[str] = None
    priority: str = DEFAULT_PRIORITY
    ttl: int = 5
    hop_count: int = 0
    route: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=clock.now)
    signature: Optional[str] = None

    @classmethod
    def create(cls, source_node: str, destination_node: str,
               message_type: str, payload: Any,
               event_id: Optional[str] = None, priority: str = DEFAULT_PRIORITY,
               ttl: int = 5) -> "SynapseMessage":
        """Factory for generating a new message."""
        return cls(
            message_id=f"MSG-{uuid.uuid4().hex[:12].upper()}",
            event_id=event_id,
            source_node=source_node,
            destination_node=destination_node,
            message_type=normalize_type(message_type),
            payload=payload,
            priority=normalize_priority(priority),
            ttl=ttl,
            hop_count=0,
            route=[source_node],
            timestamp=clock.now()
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SynapseMessage":
        return cls(
            message_id=data.get("message_id", f"MSG-{uuid.uuid4().hex[:12].upper()}"),
            event_id=data.get("event_id"),
            source_node=data.get("source_node", "UNKNOWN"),
            destination_node=data.get("destination_node", "BROADCAST"),
            message_type=normalize_type(data.get("message_type")),
            payload=data.get("payload", {}),
            priority=normalize_priority(data.get("priority")),
            ttl=int(data.get("ttl", 5)),
            hop_count=int(data.get("hop_count", 0)),
            route=list(data.get("route", [])),
            timestamp=float(data.get("timestamp", clock.now())),
            signature=data.get("signature")
        )


def frame_message(data: Dict[str, Any]) -> bytes:
    """
    Serializes a dictionary into JSON and frames it with a 4-byte big-endian length prefix:
    [Length (4 bytes)][UTF-8 JSON Payload]
    """
    payload_bytes = json.dumps(data, separators=(',', ':')).encode("utf-8")
    length = len(payload_bytes)
    header = struct.pack(HEADER_FORMAT, length)
    return header + payload_bytes


async def read_framed_message(reader: asyncio.StreamReader, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """
    Reads a length-prefixed framed message from an asyncio StreamReader.
    Handles TCP stream fragmentation cleanly.
    """
    try:
        # Read exact 4-byte header
        if timeout:
            header_bytes = await asyncio.wait_for(reader.readexactly(HEADER_SIZE), timeout=timeout)
        else:
            header_bytes = await reader.readexactly(HEADER_SIZE)

        (length,) = struct.unpack(HEADER_FORMAT, header_bytes)

        if length > MAX_MESSAGE_SIZE:
            raise ValueError(f"Framed message size {length} exceeds maximum {MAX_MESSAGE_SIZE} bytes")

        # Read exact payload bytes
        if timeout:
            payload_bytes = await asyncio.wait_for(reader.readexactly(length), timeout=timeout)
        else:
            payload_bytes = await reader.readexactly(length)

        return json.loads(payload_bytes.decode("utf-8"))

    except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
        return None
    except Exception as e:
        raise ValueError(f"Error parsing framed message: {e}")
