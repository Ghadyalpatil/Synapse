"""
SYNAPSE HAL — Simulated Edge Sensors
Simulation drivers for zero-hardware automated testing on Jetson & Raspberry Pi.
"""

import random
import time
from typing import Any, Dict

from .base import BaseSensor


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
