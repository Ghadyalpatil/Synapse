"""
SYNAPSE Hardware Abstraction Layer (HAL)
"""

from .base import BaseSensor, SensorReading
from .simulated import (
    SimulatedThermalSensor,
    SimulatedAcousticSensor,
    SimulatedMotionSensor,
)

__all__ = [
    "BaseSensor",
    "SensorReading",
    "SimulatedThermalSensor",
    "SimulatedAcousticSensor",
    "SimulatedMotionSensor",
]
