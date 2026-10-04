"""
SYNAPSE — Node CLI & Executable Entrypoint
Runs a self-contained, local-first SYNAPSE edge surveillance node.
Usage:
    python -m synapse [options]
    synapse-node [options]
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
from synapse import clock as _clock
from synapse.context import NodeConfig, NodeContext


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="SYNAPSE — Local-Grid Surveillance Node")
    parser.add_argument("--node-id", default=os.environ.get("SYNAPSE_NODE_ID", config.NODE_ID), help="Unique Node ID")
    parser.add_argument("--comm-port", type=int, default=int(os.environ.get("SYNAPSE_COMM_PORT", config.COMMUNICATION_PORT)), help="TCP communication port")
    parser.add_argument("--discovery-port", type=int, default=int(os.environ.get("SYNAPSE_DISCOVERY_PORT", config.DISCOVERY_PORT)), help="UDP discovery port")
    parser.add_argument("--api-port", type=int, default=int(os.environ.get("SYNAPSE_API_PORT", config.API_PORT)), help="Local HTTP/WebSocket API port")
    parser.add_argument("--broadcast-ip", default=os.environ.get("SYNAPSE_BROADCAST_IP", config.BROADCAST_IP), help="Subnet broadcast IP")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    parser.add_argument("--keys-dir", default=None, help="Path to directory for node keypair")
    parser.add_argument("--heartbeat-interval", type=float, default=config.HEARTBEAT_INTERVAL, help="Heartbeat probe interval in seconds")
    parser.add_argument("--unresponsive-timeout", type=float, default=config.UNRESPONSIVE_TIMEOUT, help="Seconds before node is marked UNRESPONSIVE")
    parser.add_argument("--heartbeat-timeout", type=float, default=config.HEARTBEAT_TIMEOUT, help="Seconds before node is marked OFFLINE")
    parser.add_argument("--retry-interval", type=float, default=config.STORE_FORWARD_RETRY_INTERVAL, help="Store-and-forward outbox retry interval in seconds")
    parser.add_argument("--auto-poll", type=float, default=0.0, help="Interval in seconds for periodic sensor sampling (0 to disable)")
    parser.add_argument("--stream-telemetry", action="store_true", help="Stream sensor telemetry across the mesh during polling")
    parser.add_argument("--telemetry-target", default="BROADCAST", help="Destination node for sensor telemetry (e.g. COMMAND-CENTER or BROADCAST)")
    parser.add_argument("--peer", action="append", default=[], help="Static seed peer in format NODE_ID@IP:PORT (e.g. SYNAPSE-002@127.0.0.1:5001)")
    parser.add_argument("--log-level", default=config.LOG_LEVEL, help="Logging level (DEBUG, INFO, WARN, ERROR)")
    return parser.parse_args()


async def run_node_async(args):
    setup_logging(args.log_level)
    logger = logging.getLogger("synapse.main")

    logger.info("=" * 60)
    logger.info(f"STARTING SYNAPSE NODE: [{args.node_id}]")
    logger.info("Mode: LOCAL-FIRST / ZERO-CLOUD / TACTICAL MESH GRID")
    logger.info(f"TCP Comm Port: {args.comm_port} | Discovery Port: {args.discovery_port}")
    logger.info(f"Local Dashboard / API: http://127.0.0.1:{args.api_port}")
    logger.info("=" * 60)

    # Bootstrap the offline clock anchor before anything else.
    # This ensures timestamps are monotonically consistent across reboots
    # even when the Raspberry Pi has no NTP access and no RTC battery.
    run_dir = config.VAR_DIR / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    _clock.apply_anchor_correction(run_dir)

    node_cfg = NodeConfig(
        node_id=args.node_id,
        comm_port=args.comm_port,
        discovery_port=args.discovery_port,
        api_port=args.api_port,
        broadcast_ip=args.broadcast_ip,
        db_path=Path(args.db_path) if args.db_path else None,
        keys_dir=Path(args.keys_dir) if args.keys_dir else None,
        heartbeat_interval=args.heartbeat_interval,
        unresponsive_timeout=args.unresponsive_timeout,
        heartbeat_timeout=args.heartbeat_timeout,
        retry_interval=args.retry_interval,
        auto_poll=args.auto_poll,
        stream_telemetry=args.stream_telemetry,
        telemetry_target=args.telemetry_target,
        log_level=args.log_level
    )

    ctx = NodeContext(node_cfg)
    await ctx.start()

    # Register any statically configured seed peers
    for peer_str in args.peer:
        try:
            if "@" in peer_str:
                p_id, p_addr = peer_str.split("@", 1)
            else:
                p_addr = peer_str
                p_id = f"PEER-{p_addr.replace('.', '-').replace(':', '-')}"
            p_ip, p_port = p_addr.split(":")
            ctx.comm_manager.node_manager.register_peer(p_id, p_ip, int(p_port))
            logger.info(f"[Seed] Statically registered peer: {p_id} at {p_ip}:{p_port}")
        except Exception as e:
            logger.warning(f"[Seed] Failed to parse peer '{peer_str}': {e}")

    # Start FastAPI / Uvicorn Server
    uvicorn_config = uvicorn.Config(
        app=ctx.api_app,
        host="0.0.0.0",
        port=args.api_port,
        log_level="warning"
    )
    server = uvicorn.Server(uvicorn_config)
    server_task = asyncio.create_task(server.serve())

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
        logger.info(f"Shutting down node [{args.node_id}]...")
        server.should_exit = True
        await ctx.stop()
        ctx.db.close()
        logger.info(f"Node [{args.node_id}] shutdown complete.")


def main():
    cli_args = parse_args()
    try:
        asyncio.run(run_node_async(cli_args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
