"""
SYNAPSE HAL — Hardware Abstraction Layer Base Interfaces
Provides standard abstract contracts for physical and simulated sensors.
"""

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SensorReading:
    """Standardized multi-modal sensor sample emitted by HAL drivers."""
    sensor_id: str
    sensor_type: str
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.0
    target_detected: bool = False
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "target_detected": self.target_detected,
        }
        d.update(self.raw_data)
        return d


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
