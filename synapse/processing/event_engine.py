"""
SYNAPSE — Surveillance Event Processing Engine
Implements the core data pipeline:
Sensor -> Processing -> Event -> Local DB -> Comm Manager -> Local IP Grid
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from synapse import clock
from ..communication.manager import CommunicationManager
from ..communication.protocol import TYPE_ALERT, TYPE_COMMAND, TYPE_SENSOR_DATA, TYPE_TARGET_DETECTED
from ..sensors.sensor_engine import SensorManager
from ..storage.database import Database

logger = logging.getLogger("synapse.event_engine")


class EventEngine:
    """Evaluates sensor readings, detects security threats, and initiates grid alerts."""

    def __init__(self, node_id: str, sensor_manager: SensorManager,
                 comm_manager: CommunicationManager, db: Database,
                 stream_telemetry: bool = False,
                 telemetry_target: str = "BROADCAST"):
        self.node_id = node_id
        self.sensor_manager = sensor_manager
        self.comm_manager = comm_manager
        self.db = db
        self.stream_telemetry = stream_telemetry
        self.telemetry_target = telemetry_target

        self._poll_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self, auto_poll_interval: Optional[float] = None):
        """Starts the event engine and optional sensor polling loop."""
        self._is_running = True
        # Listen for remote grid commands from Command Centre
        try:
            self.comm_manager.add_event_listener(self._handle_grid_command)
        except Exception:
            pass
        if auto_poll_interval:
            self._poll_task = asyncio.create_task(self._poll_loop(auto_poll_interval))
        logger.info(f"Event Processing Engine active on [{self.node_id}]")

    async def stop(self):
        """Stops the event engine."""
        self._is_running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Event Processing Engine stopped.")

    async def process_sensor_reading(self, reading: Dict[str, Any]) -> Optional[str]:
        """
        Evaluates a raw sensor reading against detection thresholds.
        If a target or threat is detected, persists event and broadcasts to grid.
        Returns: event_id if detected, else None.
        """
        sensor_type = reading.get("sensor_type", "unknown")
        confidence = reading.get("confidence", 0.0)

        # Save raw telemetry to local SQLite (never transmitted to network)
        self.db.save_sensor_reading(
            sensor_id=reading.get("sensor_id", "SENSOR-01"),
            sensor_type=sensor_type,
            raw_value=reading,
            timestamp=reading.get("timestamp", clock.now())
        )

        # Threat Assessment Rules
        is_threat = False
        event_type = TYPE_TARGET_DETECTED
        priority = "P1"
        severity = "WARNING"
        summary = "Surveillance anomaly detected"

        if sensor_type == "thermal" and reading.get("target_detected"):
            is_threat = True
            temp = reading.get("temperature_celsius", 37.0)
            summary = f"Thermal Target Detected ({temp}°C, conf: {confidence:.2f})"
            if confidence > 0.90:
                priority = "P0"
                severity = "CRITICAL"

        elif sensor_type == "acoustic" and reading.get("anomaly_detected"):
            is_threat = True
            sig = reading.get("signature", "ACOUSTIC_ANOMALY")
            db_level = reading.get("decibels", 80.0)
            summary = f"Acoustic Breach Signature: {sig} ({db_level} dB)"
            if db_level > 95:
                priority = "P0"
                severity = "CRITICAL"

        elif sensor_type == "motion" and reading.get("motion_detected"):
            is_threat = True
            summary = f"Perimeter Motion Breach (confidence: {confidence:.2f})"

        if not is_threat:
            return None

        # Generate unique Event ID
        event_id = f"EVT-{uuid.uuid4().hex[:10].upper()}"
        now = clock.now()

        logger.info(f"[EventEngine] Threat confirmed! Generated {event_id}: {summary}")

        # 1. Local Database Persistence
        self.db.save_event(
            event_id=event_id,
            source_node=self.node_id,
            timestamp=now,
            event_type=event_type,
            sensor_type=sensor_type,
            confidence=confidence,
            priority=priority,
            details=reading
        )

        self.db.save_alert(
            alert_id=f"ALT-{event_id}",
            event_id=event_id,
            source_node=self.node_id,
            severity=severity,
            message=summary,
            timestamp=now
        )

        # 2. Transmit across SYNAPSE Local Grid via Communication Manager
        payload = {
            "summary": summary,
            "sensor_type": sensor_type,
            "confidence": confidence,
            "reading": reading,
            "detected_at": now
        }

        await self.comm_manager.send_message(
            destination_node="BROADCAST",
            message_type=event_type,
            payload=payload,
            priority=priority,
            event_id=event_id
        )

        return event_id

    async def trigger_manual_event(self, sensor_type: str = "thermal",
                                   confidence: float = 0.95,
                                   details: Optional[Dict[str, Any]] = None) -> str:
        """Manually injects an event for testing or simulation."""
        reading = self.sensor_manager.trigger_mock_detection(sensor_type, confidence, details)
        event_id = await self.process_sensor_reading(reading)
        return event_id or "EVT-MANUAL-DISCARDED"

    async def broadcast_sensor_telemetry(self, readings: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """
        Samples attached sensors (or accepts readings) and transmits full multi-sensor
        telemetry (TYPE_SENSOR_DATA) across the independent SYNAPSE mesh grid.
        """
        if readings is None:
            readings = self.sensor_manager.sample_all()

        now = clock.now()
        for r in readings:
            if isinstance(r, dict):
                r.setdefault("source_node", self.node_id)
                r.setdefault("timestamp", now)
                self.db.save_sensor_reading(
                    sensor_id=r.get("sensor_id", f"{self.node_id}-SENSOR"),
                    sensor_type=r.get("sensor_type", "unknown"),
                    raw_value=r,
                    timestamp=r.get("timestamp", now),
                    source_node=self.node_id
                )

        payload = {
            "node_id": self.node_id,
            "readings": readings,
            "timestamp": now,
            "sample_count": len(readings)
        }

        return await self.comm_manager.send_message(
            destination_node=self.telemetry_target,
            message_type=TYPE_SENSOR_DATA,
            payload=payload,
            priority="P2"
        )

    async def _poll_loop(self, interval: float):
        """Periodically samples sensors, evaluates threats, and optionally streams telemetry."""
        while self._is_running:
            try:
                readings = self.sensor_manager.sample_all()
                for r in readings:
                    r.setdefault("source_node", self.node_id)
                    await self.process_sensor_reading(r)
                if self.stream_telemetry:
                    try:
                        await self.broadcast_sensor_telemetry(readings)
                    except Exception as te:
                        logger.debug(f"[EventEngine] Sensor telemetry broadcast skipped: {te}")
            except Exception as e:
                logger.error(f"[EventEngine] Error in poll loop: {e}")
            await asyncio.sleep(interval)

    def _handle_grid_command(self, msg_dict: Dict[str, Any]):
        """Executes operational commands dispatched across the Synapse mesh."""
        if msg_dict.get("message_type") != TYPE_COMMAND:
            return

        payload = msg_dict.get("payload", {})
        cmd = payload.get("command") if isinstance(payload, dict) else str(payload)
        logger.info(f"[EventEngine] Executing grid command: {cmd}")

        if cmd in ("SAMPLE_SENSORS", "POLL_NOW"):
            asyncio.create_task(self.broadcast_sensor_telemetry())
        elif cmd == "TRIGGER_DETECTION":
            s_type = payload.get("sensor_type", "thermal") if isinstance(payload, dict) else "thermal"
            conf = float(payload.get("confidence", 0.95)) if isinstance(payload, dict) else 0.95
            details = payload.get("details") if isinstance(payload, dict) else None
            asyncio.create_task(self.trigger_manual_event(sensor_type=s_type, confidence=conf, details=details))
