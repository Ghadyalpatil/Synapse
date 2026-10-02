"""
SYNAPSE — Surveillance Sensors Subsystem
Hardware abstraction for thermal, acoustic, motion, and optical sensors.
Includes simulation drivers for zero-hardware testing on Raspberry Pi.
"""

import abc
import random
import time
from typing import Any, Dict, List, Optional

from synapse import clock


class BaseSensor(abc.ABC):
    """Abstract interface for SYNAPSE surveillance sensors."""

    def __init__(self, sensor_id: str, sensor_type: str):
        self.sensor_id = sensor_id
        self.sensor_type = sensor_type
        self.enabled = True

    @abc.abstractmethod
    def sample(self) -> Dict[str, Any]:
        """Samples the sensor and returns a dictionary of readings."""
        pass


class SimulatedThermalSensor(BaseSensor):
    """Simulated thermal surveillance sensor (FLIR/Lepton thermal imaging)."""

    def __init__(self, sensor_id: str = "THERMAL-01"):
        super().__init__(sensor_id, "thermal")

    def sample(self) -> Dict[str, Any]:
        # Background ambient 18-24°C, target detection 34-40°C
        is_target = random.random() < 0.15
        temp = round(random.uniform(34.0, 39.5), 1) if is_target else round(random.uniform(18.0, 24.0), 1)
        confidence = round(random.uniform(0.82, 0.98), 2) if is_target else round(random.uniform(0.1, 0.4), 2)

        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "temperature_celsius": temp,
            "target_detected": is_target,
            "confidence": confidence,
            "timestamp": time.time()
        }


class SimulatedAcousticSensor(BaseSensor):
    """Simulated acoustic border surveillance sensor (footsteps, vehicle engine, gunshots)."""

    def __init__(self, sensor_id: str = "ACOUSTIC-01"):
        super().__init__(sensor_id, "acoustic")

    def sample(self) -> Dict[str, Any]:
        is_spike = random.random() < 0.12
        decibels = round(random.uniform(75.0, 110.0), 1) if is_spike else round(random.uniform(30.0, 50.0), 1)
        sig = "VEHICLE_ENGINE" if decibels > 90 else ("FOOTSTEPS" if is_spike else "AMBIENT_WIND")

        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "decibels": decibels,
            "signature": sig,
            "anomaly_detected": is_spike,
            "confidence": round(random.uniform(0.75, 0.95), 2) if is_spike else 0.2,
            "timestamp": time.time()
        }


class SimulatedMotionSensor(BaseSensor):
    """Simulated seismic / PIR perimeter motion sensor."""

    def __init__(self, sensor_id: str = "MOTION-01"):
        super().__init__(sensor_id, "motion")

    def sample(self) -> Dict[str, Any]:
        detected = random.random() < 0.10
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "motion_detected": detected,
            "intensity": round(random.uniform(0.6, 1.0), 2) if detected else 0.0,
            "confidence": round(random.uniform(0.8, 0.95), 2) if detected else 0.0,
            "timestamp": time.time()
        }


class SensorManager:
    """Manages local sensors attached to this Raspberry Pi."""

    def __init__(self):
        self.sensors: Dict[str, BaseSensor] = {}
        # Register default simulated surveillance sensors
        self.register_sensor(SimulatedThermalSensor("TH-01"))
        self.register_sensor(SimulatedAcousticSensor("AC-01"))
        self.register_sensor(SimulatedMotionSensor("MO-01"))

    def register_sensor(self, sensor: BaseSensor):
        self.sensors[sensor.sensor_id] = sensor

    def sample_all(self) -> List[Dict[str, Any]]:
        readings = []
        for s in self.sensors.values():
            if s.enabled:
                readings.append(s.sample())
        return readings

    def trigger_mock_detection(self, sensor_type: str = "thermal", confidence: float = 0.95, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manually triggers a simulated surveillance detection event for testing."""
        s_type = sensor_type.lower()
        is_thermal = s_type == "thermal"
        is_acoustic = s_type == "acoustic"
        is_motion = s_type == "motion"

        reading: Dict[str, Any] = {
            "sensor_id": f"TEST-{sensor_type.upper()}-01",
            "sensor_type": s_type,
            "confidence": confidence,
            "details": details or {"zone": "Sector-4B", "direction": "Northbound"},
            "timestamp": clock.now()
        }

        if is_thermal:
            reading["target_detected"] = True
            reading["temperature_celsius"] = 38.5
        elif is_acoustic:
            reading["anomaly_detected"] = True
            reading["decibels"] = 98.0
            reading["signature"] = "VEHICLE_ENGINE"
        elif is_motion:
            reading["motion_detected"] = True
            reading["intensity"] = 0.92
        else:
            reading["target_detected"] = True

        return reading
