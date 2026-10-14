import argparse

import os

parser = argparse.ArgumentParser()

parser.add_argument("--node-id", default=os.getenv("NODE_ID", "A"))
parser.add_argument("--port", default=int(os.getenv("NODE_PORT", "9001")), type=int)
parser.add_argument("--frontend-port", default=int(os.getenv("FRONTEND_PORT", "3000")), type=int)

args, _ = parser.parse_known_args()

NODE_ID = args.node_id
NODE_PORT = args.port
FRONTEND_PORT = args.frontend_port

WEBSOCKET_PORT = NODE_PORT+1000
BUFFER_SIZE = 4096
DEFAULT_TTL = 5
HEARTBEAT_INTERVAL = 5