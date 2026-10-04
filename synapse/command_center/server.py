"""
SYNAPSE — Tactical Command Centre HTTP & WebSocket Server
Zero-cloud Command & Control (C2) endpoint operating as a first-class
node on the SYNAPSE tactical mesh grid. Receives cryptographically verified,
framed TCP messages from all edge modules and provides a real-time command
console and multi-sensor dashboard.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from synapse import clock as _clock
from synapse.communication.protocol import (
    TYPE_ALERT,
    TYPE_COMMAND,
    TYPE_HEARTBEAT,
    TYPE_SENSOR_DATA,
    TYPE_TARGET_DETECTED
)

logger = logging.getLogger("synapse.command_center")


class SendCommandRequest(BaseModel):
    target_node: str = "BROADCAST"
    command: str = "SAMPLE_SENSORS"
    parameters: Optional[Dict[str, Any]] = None
    priority: str = "P1"


class SendAlertRequest(BaseModel):
    destination_node: str = "BROADCAST"
    severity: str = "WARNING"
    message: str
    priority: str = "P1"


class RegisterPeerRequest(BaseModel):
    node_id: str
    ip: str = "127.0.0.1"
    port: int
    public_key: Optional[str] = None
    verify_key: Optional[str] = None


def create_command_center_app(comm_manager: Any, db: Any, static_dir: Optional[Path] = None) -> FastAPI:
    """Creates the FastAPI Command Centre application wired to the SYNAPSE mesh node."""
    app = FastAPI(title=f"SYNAPSE Tactical Command Centre [{comm_manager.node_id}]")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if static_dir is None:
        static_dir = Path(__file__).parent / "static"

    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    active_websockets: List[WebSocket] = []

    # Real-time WebSocket broadcasting callback for all incoming mesh traffic
    def broadcast_to_clients(msg_dict: Dict[str, Any]):
        wire_data = json.dumps(msg_dict)
        for ws in list(active_websockets):
            try:
                asyncio.create_task(ws.send_text(wire_data))
            except Exception:
                pass

    comm_manager.add_event_listener(broadcast_to_clients)

    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse(
            content="<html><body><h2>SYNAPSE Command Centre</h2>"
                    f"<p>Node ID: <b>{comm_manager.node_id}</b></p>"
                    "<p>Static assets missing.</p></body></html>",
            status_code=200
        )

    @app.get("/api/status")
    async def get_status():
        peers = comm_manager.node_manager.get_all_peers()
        online_peers = [nid for nid, p in peers.items() if p.get("status") == "ONLINE"]
        outbox_counts = db.get_outbox_count()
        latest_sensors = db.get_latest_sensor_readings()

        return {
            "node_id": comm_manager.node_id,
            "comm_port": comm_manager.comm_port,
            "discovery_port": comm_manager.discovery_port,
            "public_key": comm_manager.security.get_public_key_hex(),
            "verify_key": comm_manager.security.get_verify_key_hex(),
            "total_peers_count": len(peers),
            "online_peers_count": len(online_peers),
            "total_sensors_reporting": len(latest_sensors),
            "outbox_pending": outbox_counts.get("PENDING", 0),
            "outbox_delivered": outbox_counts.get("DELIVERED", 0),
            "system_time": _clock.now(),
            "mode": "AIR-GAPPED ZERO-CLOUD COMMAND & CONTROL"
        }

    @app.get("/api/nodes")
    async def get_nodes():
        peers = comm_manager.node_manager.get_all_peers()
        res = []
        for nid, p in peers.items():
            res.append({
                "node_id": nid,
                "ip": p.get("ip"),
                "port": p.get("port"),
                "public_key": p.get("public_key"),
                "verify_key": p.get("verify_key"),
                "status": p.get("status"),
                "last_seen": p.get("last_seen"),
                "latency_ms": p.get("latency_ms"),
                "packet_loss": p.get("packet_loss", 0.0),
                "route_score": comm_manager.node_manager.get_route_score(nid)
            })
        return res

    @app.get("/api/sensors/latest")
    async def get_latest_sensors(source_node: Optional[str] = None):
        return db.get_latest_sensor_readings(source_node=source_node)

    @app.get("/api/sensors/readings")
    async def get_sensor_readings(limit: int = 100, sensor_type: Optional[str] = None,
                                  source_node: Optional[str] = None, since: Optional[float] = None):
        return db.get_sensor_readings(limit=limit, sensor_type=sensor_type, source_node=source_node, since=since)

    @app.get("/api/events")
    async def get_events(limit: int = 50, since: Optional[float] = None):
        return db.get_events(limit=limit, since=since)

    @app.get("/api/alerts")
    async def get_alerts(limit: int = 50):
        return db.get_alerts(limit=limit)

    @app.post("/api/alerts/{alert_id}/ack")
    async def acknowledge_alert(alert_id: str):
        db.acknowledge_alert(alert_id)
        # Notify WebSocket clients
        broadcast_to_clients({
            "message_type": "ALERT_ACK",
            "alert_id": alert_id,
            "timestamp": _clock.now()
        })
        return {"status": "ACKNOWLEDGED", "alert_id": alert_id}

    @app.get("/api/messages")
    async def get_messages(limit: int = 50):
        return db.get_messages(limit=limit)

    @app.get("/api/outbox")
    async def get_outbox(limit: int = 50):
        return db.get_pending_outbox(limit=limit)

    @app.post("/api/command")
    async def send_command(req: SendCommandRequest):
        """Sends an operational command across the Synapse mesh to an edge module or broadcast."""
        payload = {
            "command": req.command,
            "parameters": req.parameters or {},
            "issued_by": comm_manager.node_id,
            "timestamp": _clock.now()
        }
        res = await comm_manager.send_message(
            destination_node=req.target_node,
            message_type=TYPE_COMMAND,
            payload=payload,
            priority=req.priority
        )
        return res

    @app.post("/api/send_alert")
    async def send_tactical_alert(req: SendAlertRequest):
        """Broadcasts a tactical alert across the SYNAPSE grid."""
        payload = {
            "message": req.message,
            "severity": req.severity,
            "source": comm_manager.node_id,
            "timestamp": _clock.now()
        }
        res = await comm_manager.send_message(
            destination_node=req.destination_node,
            message_type=TYPE_ALERT,
            payload=payload,
            priority=req.priority
        )
        return res

    @app.post("/api/register_peer")
    async def register_peer(req: RegisterPeerRequest):
        is_new = comm_manager.node_manager.register_peer(
            node_id=req.node_id,
            ip=req.ip,
            port=req.port,
            public_key=req.public_key,
            verify_key=req.verify_key
        )
        asyncio.create_task(comm_manager.queue_manager.retry_pending_outbox(target_node=req.node_id))
        return {
            "status": "REGISTERED",
            "node_id": req.node_id,
            "ip": req.ip,
            "port": req.port,
            "is_new": is_new
        }

    @app.post("/api/sync")
    async def force_sync(target_node: str):
        success = await comm_manager.queue_manager.sync_with_peer(target_node)
        return {"status": "SUCCESS" if success else "FAILED", "target": target_node}

    @app.get("/api/export")
    async def export_telemetry():
        readings = db.get_sensor_readings(limit=500)
        events = db.get_events(limit=200)
        messages = db.get_messages(limit=200)
        peers = comm_manager.node_manager.get_all_peers()
        return {
            "exported_at": _clock.now(),
            "command_center_id": comm_manager.node_id,
            "total_sensor_records": len(readings),
            "sensor_telemetry": readings,
            "events": events,
            "message_logs": messages,
            "grid_peers": peers
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        active_websockets.append(websocket)
        logger.info(f"[CommandCenter WS] Client connected (Total active: {len(active_websockets)})")
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                    msg_type = payload.get("type")
                    if msg_type == "PING":
                        await websocket.send_text(json.dumps({"type": "PONG", "timestamp": _clock.now()}))
                except Exception:
                    pass
        except WebSocketDisconnect:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
            logger.info(f"[CommandCenter WS] Client disconnected (Remaining: {len(active_websockets)})")
        except Exception as e:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
            logger.warning(f"[CommandCenter WS] WebSocket error: {e}")

    return app
