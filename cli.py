"""
SYNAPSE — Local Node Operator & Test CLI
Zero-cloud surveillance and grid management command-line utility.
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

DEFAULT_API_URL = "http://127.0.0.1:8080"


def make_request(url: str, method: str = "GET", data: dict = None, silent: bool = False):
    try:
        req_data = json.dumps(data).encode("utf-8") if data else None
        headers = {"Content-Type": "application/json"} if data else {}
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        if not silent:
            print(f"[ERROR] Cannot connect to local SYNAPSE node at {url}: {e.reason}")
        sys.exit(1)
    except Exception as e:
        if not silent:
            print(f"[ERROR] Request failed: {e}")
        sys.exit(1)


def cmd_status(args):
    data = make_request(f"{args.api}/api/status")
    print("\n" + "=" * 50)
    print(f"[+] SYNAPSE LOCAL NODE STATUS: {data.get('node_id')}")
    print("=" * 50)
    print(f"Communication Port : {data.get('comm_port')}")
    print(f"Discovery Port     : {data.get('discovery_port')}")
    print(f"Public Key (Hex)   : {data.get('public_key')[:32]}...")
    print(f"Total Peers Known  : {data.get('total_peers_count')}")
    print(f"Active Grid Peers  : {data.get('online_peers_count')}")
    print(f"Outbox Pending     : {data.get('outbox_pending')}")
    print(f"Outbox Delivered   : {data.get('outbox_delivered')}")
    print("=" * 50 + "\n")


def cmd_nodes(args):
    nodes = make_request(f"{args.api}/api/nodes")
    print("\n" + "=" * 70)
    print(f"{'NODE ID':<16} {'ENDPOINT':<20} {'STATUS':<12} {'LATENCY':<10} {'LOSS':<8}")
    print("=" * 70)
    if not nodes:
        print("No peers registered yet.")
    for n in nodes:
        lat = f"{n.get('latency_ms')} ms" if n.get('latency_ms') is not None else "N/A"
        loss = f"{n.get('packet_loss', 0.0) * 100:.1f}%"
        endpoint = f"{n.get('ip')}:{n.get('port')}"
        print(f"{n.get('node_id'):<16} {endpoint:<20} {n.get('status'):<12} {lat:<10} {loss:<8}")
    print("=" * 70 + "\n")


def cmd_events(args):
    events = make_request(f"{args.api}/api/events?limit={args.limit}")
    print("\n" + "=" * 75)
    print(f"{'EVENT ID':<16} {'SOURCE':<14} {'TYPE':<18} {'PRIORITY':<8} {'CONF':<6}")
    print("=" * 75)
    if not events:
        print("No surveillance events logged.")
    for e in events:
        conf = f"{e.get('confidence'):.2f}" if e.get('confidence') else "N/A"
        print(f"{e.get('event_id'):<16} {e.get('source_node'):<14} {e.get('event_type'):<18} {e.get('priority', 'P1'):<8} {conf:<6}")
    print("=" * 75 + "\n")


def cmd_alerts(args):
    alerts = make_request(f"{args.api}/api/alerts?limit={args.limit}")
    print("\n" + "=" * 70)
    print(f"{'ALERT ID':<18} {'SEVERITY':<10} {'SOURCE':<14} {'MESSAGE'}")
    print("=" * 70)
    if not alerts:
        print("No active alerts.")
    for a in alerts:
        print(f"{a.get('alert_id'):<18} {a.get('severity'):<10} {a.get('source_node'):<14} {a.get('message')}")
    print("=" * 70 + "\n")


def cmd_outbox(args):
    outbox = make_request(f"{args.api}/api/outbox")
    print("\n" + "=" * 70)
    print(f"{'MSG ID':<18} {'DESTINATION':<16} {'PRIORITY':<10} {'STATUS':<12} {'ATTEMPTS'}")
    print("=" * 70)
    if not outbox:
        print("Outbox is empty. All queued messages delivered.")
    for item in outbox:
        print(f"{item.get('message_id'):<18} {item.get('destination_node'):<16} {item.get('priority'):<10} {item.get('status'):<12} {item.get('attempts')}")
    print("=" * 70 + "\n")


def cmd_clear_outbox(args):
    try:
        url = f"{args.api}/api/outbox/clear"
        if args.status:
            url += f"?status={args.status}"
        res = make_request(url, method="POST", silent=True)
        print(f"\n[+] STORE-AND-FORWARD OUTBOX CLEARED (via API): {res.get('deleted_count', 0)} message(s) removed.\n")
        return
    except SystemExit:
        pass

    # Fallback to direct SQLite cleanup across var/data/*.db
    import glob
    import sqlite3
    total = 0
    for db_file in glob.glob("var/data/*.db"):
        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            if args.status:
                cur.execute("DELETE FROM outbox WHERE status = ?", (args.status,))
            else:
                cur.execute("DELETE FROM outbox")
            conn.commit()
            total += cur.rowcount
            conn.close()
        except Exception as e:
            print(f"[!] Warning cleaning {db_file}: {e}")
    print(f"\n[+] STORE-AND-FORWARD OUTBOX CLEARED (direct database): {total} message(s) removed.\n")


def cmd_send(args):
    payload = {"message": args.message}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except Exception:
            payload = {"raw": args.payload}

    res = make_request(f"{args.api}/api/send", method="POST", data={
        "destination_node": args.target,
        "message_type": args.type,
        "priority": args.priority,
        "payload": payload
    })
    print(f"\n[DISPATCH RESULT]: {res}\n")


def cmd_trigger(args):
    res = make_request(f"{args.api}/api/trigger", method="POST", data={
        "sensor_type": args.type,
        "confidence": args.confidence
    })
    print(f"\n[SENSOR TRIGGER RESULT]: {res}\n")


def cmd_sync(args):
    res = make_request(f"{args.api}/api/sync?target_node={args.target}", method="POST")
    print(f"\n[SYNC RESULT]: {res}\n")


def main():
    parser = argparse.ArgumentParser(description="SYNAPSE — Local Node Operator CLI")
    parser.add_argument("--api", default=DEFAULT_API_URL, help=f"Local API URL (default: {DEFAULT_API_URL})")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show local node operational status")
    p_status.set_defaults(func=cmd_status)

    # nodes
    p_nodes = subparsers.add_parser("nodes", help="List known grid nodes and link metrics")
    p_nodes.set_defaults(func=cmd_nodes)

    # events
    p_events = subparsers.add_parser("events", help="List surveillance events")
    p_events.add_argument("--limit", type=int, default=20)
    p_events.set_defaults(func=cmd_events)

    # alerts
    p_alerts = subparsers.add_parser("alerts", help="List surveillance alerts")
    p_alerts.add_argument("--limit", type=int, default=20)
    p_alerts.set_defaults(func=cmd_alerts)

    # outbox
    p_outbox = subparsers.add_parser("outbox", help="List pending store-and-forward outbox items")
    p_outbox.set_defaults(func=cmd_outbox)

    # clear-outbox
    p_clear_outbox = subparsers.add_parser("clear-outbox", help="Clear all messages in store-and-forward outbox")
    p_clear_outbox.add_argument("--status", choices=["PENDING", "DELIVERED", "EXPIRED"], default=None, help="Filter by status (default: clear all)")
    p_clear_outbox.set_defaults(func=cmd_clear_outbox)

    # send
    p_send = subparsers.add_parser("send", help="Send a message to a node or BROADCAST")
    p_send.add_argument("--target", required=True, help="Target Node ID or BROADCAST")
    p_send.add_argument("--type", default="ALERT", help="Message type (ALERT, TARGET_DETECTED, COMMAND, etc.)")
    p_send.add_argument("--priority", default="P1", choices=["P0", "P1", "P2"])
    p_send.add_argument("--message", default="Surveillance breach order", help="Message content")
    p_send.add_argument("--payload", default=None, help="Optional raw JSON payload")
    p_send.set_defaults(func=cmd_send)

    # trigger
    p_trigger = subparsers.add_parser("trigger", help="Trigger a simulated sensor event")
    p_trigger.add_argument("--type", default="thermal", choices=["thermal", "acoustic", "motion"])
    p_trigger.add_argument("--confidence", type=float, default=0.95)
    p_trigger.set_defaults(func=cmd_trigger)

    # sync
    p_sync = subparsers.add_parser("sync", help="Force state synchronization with a peer")
    p_sync.add_argument("--target", required=True, help="Target peer Node ID")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
