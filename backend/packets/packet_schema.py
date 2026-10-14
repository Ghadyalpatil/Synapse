from dataclasses import dataclass,asdict
from datetime import datetime, timezone
import uuid
@dataclass
class Packet:
    packet_id:str
    source_id:str
    destination_id:str
    payload:str
    ttl:int
    hop_count:int
    route:list
    delivered:bool
    timestamp:str

    @staticmethod
    def create(source_id, destination_id, payload):
        return Packet(
            packet_id=str(uuid.uuid4()),
            source_id=source_id,
            destination_id=destination_id,
            payload=payload,
            ttl=5,
            hop_count=0,
            route=[],
            delivered=False,
            timestamp=str(datetime.now(timezone.utc))
        )

    def to_dict(self):
        return asdict(self)