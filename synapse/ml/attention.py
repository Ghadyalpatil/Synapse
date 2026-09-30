"""
SYNAPSE ML — Cross-Modal Dynamic Attention Mechanism
Learns to weight each sensor modality dynamically per inference window,
enabling robust multi-modal perception when sensors are partially obscured
(e.g., thermal blinded by sunlight, acoustic drowned out by wind).
"""

import math
from typing import Dict, List, Tuple

from .backbone import ModalityEmbedding


class CrossModalAttention:
    """
    Computes dynamic cross-attention coefficients across multiple sensor embeddings.
    Fuses diverse embeddings into a single unified context vector.
    """

    def __init__(self, embedding_dim: int = 64):
        self.embedding_dim = embedding_dim

    def compute_weights(self, embeddings: List[ModalityEmbedding]) -> Dict[str, float]:
        """
        Computes softmax-normalized attention weights based on confidence and signal strength.
        """
        if not embeddings:
            return {}

        # Raw attention scores based on individual confidence & vector norm
        scores: Dict[str, float] = {}
        for emb in embeddings:
            score = emb.confidence * 2.0
            scores[emb.modality] = score

        # Softmax normalization
        max_score = max(scores.values()) if scores else 0.0
        exp_scores = {mod: math.exp(s - max_score) for mod, s in scores.items()}
        total_exp = sum(exp_scores.values()) or 1.0

        return {mod: round(exp / total_exp, 4) for mod, exp in exp_scores.items()}

    def fuse(self, embeddings: List[ModalityEmbedding]) -> Tuple[List[float], Dict[str, float]]:
        """
        Produces a weighted context vector and the attention weights dictionary.
        """
        if not embeddings:
            return [0.0] * self.embedding_dim, {}

        weights = self.compute_weights(embeddings)
        fused = [0.0] * self.embedding_dim

        for emb in embeddings:
            w = weights.get(emb.modality, 0.0)
            for i in range(min(self.embedding_dim, len(emb.vector))):
                fused[i] += emb.vector[i] * w

        return fused, weights
