"""
SYNAPSE — Border Surveillance Raspberry Pi Node Entry Point
Runs a self-contained, local-first SYNAPSE node.
Zero cloud, zero remote dependencies.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import uvicorn

from synapse import config
from synapse.api.server import create_api_app
from synapse.communication.manager import CommunicationManager
from synapse.processing.event_engine import EventEngine
from synapse.sensors.sensor_engine import SensorManager
from synapse.storage.database import Database


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )


async def run_node(args):
    setup_logging(args.log_level)
    logger = logging.getLogger("synapse.main")

    logger.info("=" * 60)
    logger.info(f"STARTING SYNAPSE NODE: [{args.node_id}]")
    logger.info(f"Mode: LOCAL-FIRST / ZERO-CLOUD / RASPBERRY PI GRID")
    logger.info(f"TCP Comm Port: {args.comm_port} | Discovery Port: {args.discovery_port}")
    logger.info(f"Local Dashboard / API: http://127.0.0.1:{args.api_port}")
    logger.info("=" * 60)

    # 1. Local Database
    db_path = Path(args.db_path) if args.db_path else config.DATA_DIR / f"{args.node_id.lower()}_local.db"
    db = Database(db_path)

    # 2. Key / Crypto directory
    keys_dir = Path(args.keys_dir) if args.keys_dir else config.KEYS_DIR

    # 3. Communication Manager
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

    # 4. Sensor Subsystem & Event Engine
    sensor_manager = SensorManager()
    event_engine = EventEngine(
        node_id=args.node_id,
        sensor_manager=sensor_manager,
        comm_manager=comm_manager,
        db=db
    )

    # 5. Local FastAPI Application
    app = create_api_app(comm_manager, event_engine, db)

    # Start Communication & Event Subsystems
    await comm_manager.start()
    await event_engine.start(auto_poll_interval=args.auto_poll if args.auto_poll > 0 else None)

    # Start FastAPI / Uvicorn Server in background
    uvicorn_config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=args.api_port,
        log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)
    server_task = asyncio.create_task(server.serve())

    # Graceful shutdown event
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received.")
        stop_event.set()

    # Register signals on Linux/Unix (Windows handles through keyboard interrupt)
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
        logger.info(f"Shutting down node [{args.node_id}]...")
        server.should_exit = True
        await event_engine.stop()
        await comm_manager.stop()
        db.close()
        logger.info(f"Node [{args.node_id}] shutdown complete.")


def parse_args():
    parser = argparse.ArgumentParser(description="SYNAPSE — Local-Grid Surveillance Node")
    parser.add_argument("--node-id", default=os.environ.get("SYNAPSE_NODE_ID", "SYNAPSE-001"), help="Unique Node ID")
    parser.add_argument("--comm-port", type=int, default=int(os.environ.get("SYNAPSE_COMM_PORT", 5000)), help="TCP communication port")
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SYNAPSE_DISCOVERY_PORT", 5999)), help="UDP discovery port")
    parser.add_argument("--api-port", type=int, default=int(os.environ.get("SYNAPSE_API_PORT", 8080)), help="Local HTTP/WebSocket API port")
    parser.add_argument("--broadcast-ip", default=os.environ.get("SYNAPSE_BROADCAST_IP", "255.255.255.255"), help="Subnet broadcast IP")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    parser.add_argument("--keys-dir", default=None, help="Path to directory for node keypair")
    parser.add_argument("--heartbeat-interval", type=float, default=5.0, help="Heartbeat probe interval in seconds")
    parser.add_argument("--unresponsive-timeout", type=float, default=12.0, help="Seconds before node is marked UNRESPONSIVE")
    parser.add_argument("--heartbeat-timeout", type=float, default=25.0, help="Seconds before node is marked OFFLINE")
    parser.add_argument("--retry-interval", type=float, default=6.0, help="Store-and-forward outbox retry interval in seconds")
    parser.add_argument("--auto-poll", type=float, default=0.0, help="Interval in seconds for periodic sensor sampling (0 to disable)")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARN, ERROR)")
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    try:
        asyncio.run(run_node(cli_args))
    except KeyboardInterrupt:
        pass
