"""
SYNAPSE ML — Surveillance Domain Classification Head
Interprets fused multi-modal context vectors to assess border perimeter threats.
"""

from typing import Any, Dict, List


class SurveillanceHead:
    """Classifies fused multi-modal representations for security and surveillance."""

    def __init__(self, threat_threshold: float = 0.70):
        self.threat_threshold = threat_threshold

    def evaluate(self, fused_vector: List[float], attention_weights: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluates threat likelihood from fused multi-modal vector.
        """
        # Sum active feature components (indices 0, 1, 4, 6 represent target indicators)
        score = sum(abs(fused_vector[i]) for i in [0, 1, 4, 6] if i < len(fused_vector))
        normalized_score = min(round(score, 3), 1.0)
        is_threat = normalized_score >= self.threat_threshold

        classification = "BENIGN"
        if normalized_score > 0.85:
            classification = "CONFIRMED_INTRUSION"
        elif normalized_score >= self.threat_threshold:
            classification = "SUSPICIOUS_ACTIVITY"

        return {
            "is_threat": is_threat,
            "threat_score": normalized_score,
            "classification": classification,
            "attention_weights": attention_weights,
            "recommended_priority": "P0" if classification == "CONFIRMED_INTRUSION" else ("P1" if is_threat else "P2")
        }
