from backend.config import NODE_ID

def update_packet(packet):
    packet["ttl"] -= 1
    packet["hop_count"] += 1
    packet["route"].append(NODE_ID)
    return packet