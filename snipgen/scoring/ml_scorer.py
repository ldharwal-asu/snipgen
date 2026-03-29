"""ML scoring hook for gRNA candidates.

Defines MLScorerProtocol (structural subtyping via Protocol) so any
ML framework (sklearn, torch, ONNX) can be plugged in without inheriting
from a base class and without modifying any other pipeline code.

Ships with two concrete implementations:
- PassthroughMLScorer: neutral 0.5 for all candidates (v1 default)
- SklearnMLScorer: loads a joblib-serialized sklearn pipeline and calls predict_proba
"""

import logging
from typing import Protocol, runtime_checkable

import numpy as np

from snipgen.models.grna_candidate import GRNACandidate

logger = logging.getLogger("snipgen.scoring.ml_scorer")

_BASES = ["A", "C", "G", "T"]


@runtime_checkable
class MLScorerProtocol(Protocol):
    """Protocol that any ML scorer must satisfy.

    Batch interface required: models benefit from vectorized inference.
    """

    def score(self, candidates: list[GRNACandidate]) -> list[float]:
        """Return a parallel list of scores in [0.0, 1.0]."""
        ...

    def is_available(self) -> bool:
        """Return True if the model artifact is loaded and ready."""
        ...


class PassthroughMLScorer:
    """Stub scorer that returns a neutral 0.5 for all candidates.

    Replace with SklearnMLScorer (or any MLScorerProtocol implementation)
    by passing --ml-model to the CLI. No other code changes required.
    """

    def score(self, candidates: list[GRNACandidate]) -> list[float]:
        return [0.5] * len(candidates)

    def is_available(self) -> bool:
        return False


class SklearnMLScorer:
    """Score candidates using a joblib-serialized sklearn pipeline.

    Expected model: a Pipeline or classifier with predict_proba() that
    accepts an (N, 84) feature matrix:
    - 80 features: one-hot encoding of each position in the 20-nt spacer
    - 4 features: gc_content, seed_gc, has_poly_t (int), has_homopolymer (int)

    Train your model on experimental gRNA efficiency data (e.g., Doench 2016,
    Hart 2015) using the same featurization provided by _featurize().
    """

    def __init__(self, model_path: str):
        import joblib
        self.model = joblib.load(model_path)
        self._available = True
        logger.info("Loaded ML scorer from %s", model_path)

    def _featurize(self, candidates: list[GRNACandidate]) -> np.ndarray:
        rows = []
        for c in candidates:
            # One-hot encode each of the 20 positions (4 features each = 80)
            onehot: list[float] = []
            for base in c.sequence.upper():
                for b in _BASES:
                    onehot.append(1.0 if base == b else 0.0)
            # Pad or truncate to exactly 80 features
            onehot = (onehot + [0.0] * 80)[:80]

            # 4 scalar features
            scalars = [
                c.gc_content,
                c.seed_gc,
                float(c.has_poly_t),
                float(c.has_homopolymer),
            ]
            rows.append(onehot + scalars)
        return np.array(rows, dtype=np.float32)

    def score(self, candidates: list[GRNACandidate]) -> list[float]:
        if not candidates:
            return []
        X = self._featurize(candidates)
        proba = self.model.predict_proba(X)
        # Assume binary classification: column 1 is the positive class
        return proba[:, 1].tolist()

    def is_available(self) -> bool:
        return self._available


def load_ml_scorer(model_path: str | None) -> MLScorerProtocol:
    """Factory: return SklearnMLScorer if a path is given, else PassthroughMLScorer."""
    if model_path:
        try:
            return SklearnMLScorer(model_path)
        except Exception as exc:
            logger.warning("Failed to load ML model from '%s': %s — using passthrough", model_path, exc)
    return PassthroughMLScorer()
