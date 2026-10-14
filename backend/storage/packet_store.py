import json
from backend.storage.database import cursor, connection

class PacketStore:
    def save_packet(self, packet):
        cursor.execute(
            """
            INSERT OR REPLACE INTO packets VALUES (?, ?, ?, ?, ?, ?)
            """, 
            (
                packet["packet_id"], 
                packet["source_id"], 
                packet["destination_id"], 
                packet["payload"], 
                int(packet["delivered"]), 
                json.dumps(packet["route"])
            )
        )
        connection.commit()

    def mark_delivered(self, packet_id):
        cursor.execute(
            "UPDATE packets SET delivered=1 WHERE packet_id=?", 
            (packet_id,)
        )
        connection.commit()

packet_store = PacketStore()