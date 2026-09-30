"""
SYNAPSE ML — Shared Multi-Modal Feature Extraction Backbone
Extracts modality-agnostic dense embeddings from heterogeneous sensor streams
(thermal imaging, acoustic spectra, seismic motion, ambient telemetry).
Optimized for 67-TOPS envelope on NVIDIA Jetson Orin Nano.
"""

import abc
import math
from typing import Any, Dict, List, Optional


class ModalityEmbedding:
    """Represents a latent embedding vector extracted from a single modality."""

    def __init__(self, modality: str, vector: List[float], confidence: float, timestamp: float):
        self.modality = modality
        self.vector = vector
        self.confidence = confidence
        self.timestamp = timestamp

    @property
    def dimension(self) -> int:
        return len(self.vector)

    def norm(self) -> float:
        return math.sqrt(sum(x * x for x in self.vector))


class BaseBackbone(abc.ABC):
    """Abstract interface for sensor feature extraction backbones."""

    @abc.abstractmethod
    def extract(self, modality: str, raw_reading: Dict[str, Any]) -> ModalityEmbedding:
        """Transforms a raw sensor reading dictionary into a normalized embedding vector."""
        pass


class EdgeFeatureBackbone(BaseBackbone):
    """
    Lightweight, deterministic feature extraction backbone for edge nodes.
    Maps heterogeneous sensor features to a unified 64-dimensional latent space.
    """

    def __init__(self, embedding_dim: int = 64):
        self.embedding_dim = embedding_dim

    def extract(self, modality: str, raw_reading: Dict[str, Any]) -> ModalityEmbedding:
        confidence = float(raw_reading.get("confidence", 0.5))
        timestamp = float(raw_reading.get("timestamp", 0.0))

        # Project features into deterministic latent vector
        vector = [0.0] * self.embedding_dim

        if modality == "thermal":
            temp = float(raw_reading.get("temperature_celsius", 20.0))
            is_target = 1.0 if raw_reading.get("target_detected") else 0.0
            vector[0] = (temp - 20.0) / 20.0
            vector[1] = is_target
            vector[2] = confidence
        elif modality == "acoustic":
            db = float(raw_reading.get("decibels", 40.0))
            anomaly = 1.0 if raw_reading.get("anomaly_detected") else 0.0
            vector[3] = (db - 40.0) / 70.0
            vector[4] = anomaly
            vector[5] = confidence
        elif modality == "motion":
            motion = 1.0 if raw_reading.get("motion_detected") else 0.0
            intensity = float(raw_reading.get("intensity", 0.0))
            vector[6] = motion
            vector[7] = intensity
            vector[8] = confidence
        else:
            vector[9] = confidence

        # Normalize vector
        sq_sum = sum(x * x for x in vector)
        norm = math.sqrt(sq_sum) if sq_sum > 0 else 1.0
        normalized = [x / norm for x in vector]

        return ModalityEmbedding(
            modality=modality,
            vector=normalized,
            confidence=confidence,
            timestamp=timestamp
        )
