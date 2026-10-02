"""
SYNAPSE — Local HTTP & WebSocket Surveillance API
Lightweight local API providing surveillance telemetry,
topology queries, manual sensor triggers, and dashboard serving.
Zero cloud dependencies.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("synapse.api")


class SendMessageRequest(BaseModel):
    destination_node: str
    message_type: str = "ALERT"
    priority: str = "P1"
    payload: Dict[str, Any]
    event_id: Optional[str] = None


class TriggerSensorRequest(BaseModel):
    sensor_type: str = "thermal"
    confidence: float = 0.95
    details: Optional[Dict[str, Any]] = None


class RegisterPeerRequest(BaseModel):
    node_id: str
    ip: str = "127.0.0.1"
    port: int
    public_key: Optional[str] = None
    verify_key: Optional[str] = None


def create_api_app(comm_manager: Any, event_engine: Any, db: Any) -> FastAPI:
    """Creates the FastAPI application wired to SYNAPSE subsystems."""
    app = FastAPI(title=f"SYNAPSE Node API [{comm_manager.node_id}]")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    # Only mount static files if the directory exists (tolerates fresh Pi deployments)
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    active_websockets: List[WebSocket] = []

    # Wire incoming event callback to broadcast via WebSocket
    def on_event_received(evt: Dict[str, Any]):
        for ws in list(active_websockets):
            try:
                asyncio.create_task(ws.send_text(json.dumps(evt)))
            except Exception:
                pass

    comm_manager.add_event_listener(on_event_received)

    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse(
            content="<html><body><h2>SYNAPSE Node Online</h2>"
                    f"<p>Node: <b>{comm_manager.node_id}</b></p>"
                    "<p>API available at <a href='/api/status'>/api/status</a></p>"
                    "</body></html>",
            status_code=200
        )

    @app.get("/api/status")
    async def get_status():
        peers = comm_manager.node_manager.get_all_peers()
        online_peers = [nid for nid, p in peers.items() if p.get("status") == "ONLINE"]
        outbox_counts = db.get_outbox_count()

        return {
            "node_id": comm_manager.node_id,
            "comm_port": comm_manager.comm_port,
            "discovery_port": comm_manager.discovery_port,
            "public_key": comm_manager.security.get_public_key_hex(),
            "verify_key": comm_manager.security.get_verify_key_hex(),
            "total_peers_count": len(peers),
            "online_peers_count": len(online_peers),
            "outbox_pending": outbox_counts.get("PENDING", 0),
            "outbox_delivered": outbox_counts.get("DELIVERED", 0)
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
                "status": p.get("status"),
                "last_seen": p.get("last_seen"),
                "latency_ms": p.get("latency_ms"),
                "packet_loss": p.get("packet_loss", 0.0),
                "route_score": comm_manager.node_manager.get_route_score(nid)
            })
        return res

    @app.get("/api/events")
    async def get_events(limit: int = 50, since: Optional[float] = None):
        return db.get_events(limit=limit, since=since)

    @app.get("/api/alerts")
    async def get_alerts(limit: int = 50):
        return db.get_alerts(limit=limit)

    @app.post("/api/alerts/{alert_id}/ack")
    async def acknowledge_alert(alert_id: str):
        db.acknowledge_alert(alert_id)
        return {"status": "ACKNOWLEDGED", "alert_id": alert_id}

    @app.get("/api/outbox")
    async def get_outbox(limit: int = 50):
        return db.get_pending_outbox(limit=limit)

    @app.delete("/api/outbox")
    @app.post("/api/outbox/clear")
    async def clear_outbox(status: Optional[str] = None):
        deleted = db.clear_outbox(status=status)
        return {"status": "CLEARED", "deleted_count": deleted}

    @app.post("/api/send")
    async def send_message(req: SendMessageRequest):
        res = await comm_manager.send_message(
            destination_node=req.destination_node,
            message_type=req.message_type,
            payload=req.payload,
            priority=req.priority,
            event_id=req.event_id
        )
        return res

    @app.post("/api/trigger")
    async def trigger_sensor(req: TriggerSensorRequest):
        event_id = await event_engine.trigger_manual_event(
            sensor_type=req.sensor_type,
            confidence=req.confidence,
            details=req.details
        )
        return {"status": "TRIGGERED", "event_id": event_id}

    @app.post("/api/sync")
    async def force_sync(target_node: str):
        success = await comm_manager.queue_manager.sync_with_peer(target_node)
        return {"status": "SUCCESS" if success else "FAILED", "target": target_node}

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

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        active_websockets.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                # Echo / heartbeat keep-alive
                await websocket.send_text(json.dumps({"type": "PONG"}))
        except WebSocketDisconnect:
            active_websockets.remove(websocket)
        except Exception:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

    return app
