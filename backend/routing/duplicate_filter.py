seen_packets=set()

def already_seen(packet_id):
    return packet_id in seen_packets

def mark_seen(packet_id):
    seen_packets.add(packet_id)