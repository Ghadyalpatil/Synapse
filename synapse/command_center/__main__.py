"""
SYNAPSE — Command Centre Executable Entrypoint
Runs the central Command & Control workstation node for the tactical mesh grid.

Usage:
    python -m synapse.command_center [options]
    python command_center.py [options]
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
import webbrowser
from pathlib import Path

import uvicorn

from synapse import clock as _clock
from synapse import config
from synapse.command_center.server import create_command_center_app
from synapse.communication.manager import CommunicationManager
from synapse.storage.database import Database


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] [COMMAND-CENTER] %(message)s",
        datefmt="%H:%M:%S"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="SYNAPSE — Tactical Command Centre Console")
    parser.add_argument("--node-id", default=os.environ.get("SYNAPSE_NODE_ID", "COMMAND-CENTER"), help="Command Centre Node ID")
    parser.add_argument("--comm-port", type=int, default=int(os.environ.get("SYNAPSE_COMM_PORT", 5050)), help="TCP communication port for mesh reception")
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SYNAPSE_DISCOVERY_PORT", 5051)), help="UDP discovery port")
    parser.add_argument("--port", "--api-port", dest="api_port", type=int, default=int(os.environ.get("SYNAPSE_API_PORT", 9000)), help="Web dashboard port")
    parser.add_argument("--broadcast-ip", default=os.environ.get("SYNAPSE_BROADCAST_IP", config.BROADCAST_IP), help="Subnet broadcast IP")
    parser.add_argument("--db-path", default="var/data/command_center.db", help="Path to SQLite database file")
    parser.add_argument("--keys-dir", default="var/keys/command_center", help="Path to cryptographic key directory")
    parser.add_argument("--heartbeat-interval", type=float, default=config.HEARTBEAT_INTERVAL, help="Heartbeat probe interval in seconds")
    parser.add_argument("--unresponsive-timeout", type=float, default=config.UNRESPONSIVE_TIMEOUT, help="Seconds before node is marked UNRESPONSIVE")
    parser.add_argument("--heartbeat-timeout", type=float, default=config.HEARTBEAT_TIMEOUT, help="Seconds before node is marked OFFLINE")
    parser.add_argument("--retry-interval", type=float, default=config.STORE_FORWARD_RETRY_INTERVAL, help="Store-and-forward outbox retry interval")
    parser.add_argument("--peer", action="append", default=[], help="Static seed peer in format NODE_ID@IP:PORT (e.g. SYNAPSE-001@127.0.0.1:5000)")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open Command Centre dashboard in browser on start")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARN, ERROR)")
    return parser.parse_args()


async def run_command_center(args):
    setup_logging(args.log_level)
    logger = logging.getLogger("synapse.command_center.main")

    logger.info("=" * 65)
    logger.info("  SYNAPSE TACTICAL COMMAND & CONTROL CENTRE (C2)")
    logger.info(f"  Station Node ID : [{args.node_id}]")
    logger.info(f"  TCP Mesh Port   : {args.comm_port} (Independent Binary Framing)")
    logger.info(f"  UDP Discovery   : {args.discovery_port}")
    logger.info(f"  Web C2 Console  : http://127.0.0.1:{args.api_port}")
    logger.info("  Mode            : ZERO-CLOUD / TACTICAL AIR-GAPPED C2")
    logger.info("=" * 65)

    run_dir = config.VAR_DIR / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    _clock.apply_anchor_correction(run_dir)

    db_path = Path(args.db_path)
    db = Database(db_path)

    keys_dir = Path(args.keys_dir)

    comm_manager = CommunicationManager(
        node_id=args.node_id,
        comm_port=args.comm_port,
        discovery_port=args.discovery_port,
        broadcast_ip=args.broadcast_ip,
        db=db,
        keys_dir=keys_dir,
        heartbeat_interval=args.heartbeat_interval,
        unresponsive_timeout=args.unresponsive_timeout,
        heartbeat_timeout=args.heartbeat_timeout,
        retry_interval=args.retry_interval
    )

    await comm_manager.start()

    # Register static seed peers if provided
    for peer_str in args.peer:
        try:
            if "@" in peer_str:
                p_id, p_addr = peer_str.split("@", 1)
            else:
                p_addr = peer_str
                p_id = f"PEER-{p_addr.replace('.', '-').replace(':', '-')}"
            p_ip, p_port = p_addr.split(":")
            comm_manager.node_manager.register_peer(p_id, p_ip, int(p_port))
            logger.info(f"[Seed] Statically registered peer: {p_id} at {p_ip}:{p_port}")
        except Exception as e:
            logger.warning(f"[Seed] Failed to parse peer '{peer_str}': {e}")

    app = create_command_center_app(comm_manager, db)

    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=args.api_port,
        log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)
    server_task = asyncio.create_task(server.serve())

    if args.open_browser:
        async def _open():
            await asyncio.sleep(1.2)
            webbrowser.open(f"http://127.0.0.1:{args.api_port}")
        asyncio.create_task(_open())

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        else:
            await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Keyboard interrupt received.")
    finally:
        logger.info("Shutting down SYNAPSE Command Centre...")
        server.should_exit = True
        await comm_manager.stop()
        db.close()
        logger.info("SYNAPSE Command Centre stopped.")


def main():
    cli_args = parse_args()
    try:
        asyncio.run(run_command_center(cli_args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
