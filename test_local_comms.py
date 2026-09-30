"""
SYNAPSE — Local Two-Node Message Transmission Test
======================================================
Demonstrates direct TCP message passing between SYNAPSE-001 and SYNAPSE-002
running locally on two separate ports.

Usage (run AFTER both nodes are started):
    python test_local_comms.py

Requirements:
    - SYNAPSE-001 running: python -m synapse --node-id SYNAPSE-001 --comm-port 5000 --api-port 8080 ...
    - SYNAPSE-002 running: python -m synapse --node-id SYNAPSE-002 --comm-port 5001 --api-port 8081 ...
"""

import asyncio
import json
import sys
import urllib.request
import urllib.error

NODE1_API = "http://127.0.0.1:8080"
NODE2_API = "http://127.0.0.1:8081"
NODE1_ID  = "SYNAPSE-001"
NODE2_ID  = "SYNAPSE-002"
NODE1_IP  = "127.0.0.1"
NODE1_COMM_PORT = 5000
NODE2_COMM_PORT = 5001


def api_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        print(f"  [ERROR] GET {url} -> {e.reason}")
        return None


def api_post(url, data):
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        print(f"  [ERROR] POST {url} -> {e.reason}")
        return None


def section(title):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print("=" * 65)


def check_node(api_url, node_id):
    section(f"Checking {node_id} @ {api_url}")
    status = api_get(f"{api_url}/api/status")
    if not status:
        print(f"  [FAIL] {node_id} is NOT responding. Start it first.")
        return None
    print(f"  Node ID      : {status['node_id']}")
    print(f"  Comm Port    : {status['comm_port']}")
    print(f"  Discovery    : {status['discovery_port']}")
    print(f"  Peers Known  : {status['total_peers_count']}")
    print(f"  Peers Online : {status['online_peers_count']}")
    print(f"  Outbox Pend  : {status['outbox_pending']}")
    print(f"  Public Key   : {status['public_key'][:32]}...")
    return status


def register_peer_via_discovery(register_on_api, target_node_id, target_ip, target_port, target_pubkey):
    section(f"Registering peer {target_node_id} -> direct TCP ping")
    result = api_post(f"{register_on_api}/api/register_peer", {
        "node_id": target_node_id,
        "ip": target_ip,
        "port": target_port,
        "public_key": target_pubkey
    })
    print(f"  Result: {result}")
    return result


def send_alert(from_api, from_node, to_node, message, priority="P1"):
    section(f"Sending ALERT: {from_node} -> {to_node}")
    result = api_post(f"{from_api}/api/send", {
        "destination_node": to_node,
        "message_type": "ALERT",
        "priority": priority,
        "payload": {
            "message": message,
            "source": from_node,
            "zone": "Sector-4B",
            "threat_level": "HIGH"
        }
    })
    if result:
        print(f"  Status       : {result.get('status')}")
        print(f"  Message ID   : {result.get('message_id')}")
        print(f"  Destination  : {to_node}")
        if result.get("status") == "DELIVERED":
            print(f"  [SUCCESS] Message instantly transmitted via TCP socket to {to_node}!")
        elif result.get("status") == "QUEUED_STORE_AND_FORWARD":
            print(f"  [STORE-AND-FORWARD] Target not yet connected, queued for retry.")
    return result


def send_target_detection(from_api, from_node, to_node):
    section(f"Sending TARGET_DETECTED: {from_node} -> {to_node}")
    result = api_post(f"{from_api}/api/send", {
        "destination_node": to_node,
        "message_type": "TARGET_DETECTED",
        "priority": "P0",
        "payload": {
            "sensor_type": "thermal",
            "confidence": 0.97,
            "temperature_celsius": 38.2,
            "zone": "Northern Perimeter",
            "direction": "North-East"
        }
    })
    if result:
        print(f"  Status       : {result.get('status')}")
        print(f"  Message ID   : {result.get('message_id')}")
        print(f"  Priority     : P0 (Critical)")
    return result


def trigger_sensor(from_api, sensor_type, confidence):
    section(f"Triggering simulated {sensor_type} sensor event")
    result = api_post(f"{from_api}/api/trigger", {
        "sensor_type": sensor_type,
        "confidence": confidence
    })
    if result:
        print(f"  Status       : {result.get('status')}")
        print(f"  Event ID     : {result.get('event_id')}")
    return result


def show_events(api_url, node_id):
    section(f"Events log on {node_id}")
    events = api_get(f"{api_url}/api/events?limit=10")
    if not events:
        print("  No events recorded.")
        return
    for e in events:
        conf = f"{e.get('confidence'):.2f}" if e.get('confidence') else "N/A"
        print(f"  [{e.get('priority','P?')}] {e.get('event_type','?'):<20} "
              f"src={e.get('source_node','?'):<14} conf={conf}")


def show_alerts(api_url, node_id):
    section(f"Alerts on {node_id}")
    alerts = api_get(f"{api_url}/api/alerts?limit=10")
    if not alerts:
        print("  No alerts.")
        return
    for a in alerts:
        ack = "ACK" if a.get("acknowledged") else "ACTIVE"
        print(f"  [{a.get('severity','?'):<8}] [{ack}] {a.get('message','')}")


def show_outbox(api_url, node_id):
    section(f"Outbox on {node_id}")
    outbox = api_get(f"{api_url}/api/outbox")
    if not outbox:
        print("  Outbox empty — all messages delivered.")
        return
    for o in outbox:
        print(f"  {o.get('message_id','?'):<20} -> {o.get('destination_node','?'):<16} "
              f"status={o.get('status','?')} attempts={o.get('attempts',0)}")


def show_nodes(api_url, node_id):
    section(f"Known peers on {node_id}")
    nodes = api_get(f"{api_url}/api/nodes")
    if not nodes:
        print("  No peers registered yet.")
        return
    for n in nodes:
        lat = f"{n.get('latency_ms')} ms" if n.get('latency_ms') else "N/A"
        print(f"  {n.get('node_id','?'):<16} {n.get('ip','?')}:{n.get('port','?'):<6} "
              f"status={n.get('status','?'):<14} latency={lat}")


def main():
    print("\n")
    print("=" * 65)
    print("         SYNAPSE TACTICAL MESH COMMUNICATION")
    print("         LOCAL TWO-NODE MESSAGE TRANSMISSION TEST")
    print("         Zero-Cloud | Zero-WiFi | Air-Gapped Mesh")
    print("=" * 65)

    # 1. Verify both nodes are alive
    ok1 = check_node(NODE1_API, NODE1_ID)
    ok2 = check_node(NODE2_API, NODE2_ID)

    if not ok1 or not ok2:
        print("\n[ABORT] One or both nodes are offline. Start them first:")
        print(f"  Window 1: python -m synapse --node-id {NODE1_ID} --comm-port 5000 --api-port 8080 --discovery-port 5999 --broadcast-ip 127.0.0.255 --db-path var/data/node001.db --keys-dir var/keys/node001")
        print(f"  Window 2: python -m synapse --node-id {NODE2_ID} --comm-port 5001 --api-port 8081 --discovery-port 5998 --broadcast-ip 127.0.0.255 --db-path var/data/node002.db --keys-dir var/keys/node002")
        sys.exit(1)

    # 2. Register Node2 as peer of Node1 via direct TCP
    # Since loopback UDP discovery uses different ports, we bootstrap the peer
    # table via a send (will hit store-and-forward if Node2 isn't registered yet).
    # We directly seed Node1's peer table by calling the register endpoint.
    section(f"Bootstrapping peer topology via direct TCP")
    print(f"  Registering {NODE2_ID} (127.0.0.1:{NODE2_COMM_PORT}) in {NODE1_ID} peer table...")
    reg1 = api_post(f"{NODE1_API}/api/register_peer", {
        "node_id": NODE2_ID,
        "ip": "127.0.0.1",
        "port": NODE2_COMM_PORT,
        "public_key": ok2.get("public_key")
    })
    print(f"  Node1 registration result: {reg1}")

    print(f"\n  Registering {NODE1_ID} (127.0.0.1:{NODE1_COMM_PORT}) in {NODE2_ID} peer table...")
    reg2 = api_post(f"{NODE2_API}/api/register_peer", {
        "node_id": NODE1_ID,
        "ip": "127.0.0.1",
        "port": NODE1_COMM_PORT,
        "public_key": ok1.get("public_key")
    })
    print(f"  Node2 registration result: {reg2}")

    # 3. Show initial peer tables
    show_nodes(NODE1_API, NODE1_ID)
    show_nodes(NODE2_API, NODE2_ID)

    # 4. Send ALERT from Node1 -> Node2
    alert_res = send_alert(NODE1_API, NODE1_ID, NODE2_ID,
                           "Perimeter breach detected in Sector 4B — immediate response required",
                           priority="P0")

    # 5. Send TARGET_DETECTED from Node1 -> Node2
    send_target_detection(NODE1_API, NODE1_ID, NODE2_ID)

    # Verify receipt on Node 2
    import time
    time.sleep(1)
    node2_alerts = api_get(f"{NODE2_API}/api/alerts?limit=5")
    if node2_alerts:
        for a in node2_alerts:
            if a.get("source_node") == NODE1_ID:
                print(f"\n  >>> [VERIFIED] SYNAPSE-002 successfully received message from SYNAPSE-001! <<<")
                print(f"      Message : '{a.get('message')}'")
                print(f"      Severity: {a.get('severity')}")
                break

    # 6. Send ALERT back from Node2 -> Node1
    send_alert(NODE2_API, NODE2_ID, NODE1_ID,
               "Acknowledged. Flanking unit en route — hold position",
               priority="P1")

    # 7. Trigger simulated sensor event on Node1 (broadcasts to BROADCAST)
    trigger_sensor(NODE1_API, "thermal", 0.96)

    # 8. Trigger acoustic on Node2
    trigger_sensor(NODE2_API, "acoustic", 0.88)

    import time
    print("\n  Waiting 2s for messages to propagate...")
    time.sleep(2)

    # 9. Show final state on both nodes
    show_events(NODE1_API, NODE1_ID)
    show_alerts(NODE1_API, NODE1_ID)
    show_events(NODE2_API, NODE2_ID)
    show_alerts(NODE2_API, NODE2_ID)
    show_outbox(NODE1_API, NODE1_ID)
    show_outbox(NODE2_API, NODE2_ID)

    section("TEST COMPLETE")
    print(f"  Dashboard Node1: http://127.0.0.1:8080")
    print(f"  Dashboard Node2: http://127.0.0.1:8081")
    print()


if __name__ == "__main__":
    main()
