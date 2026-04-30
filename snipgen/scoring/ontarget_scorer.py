"""
On-target quality scorer — v2 with sklearn GradientBoostingRegressor model.

Primary path: sklearn GBR model trained on a biologically-grounded synthetic
corpus using published Doench 2016 position-specific nucleotide weights
(NBT Supp. Table 19) as a scoring oracle with calibrated experimental noise.
sklearn is already a required dependency — no extra bundle size on Vercel.

Fallback: rule-based six-component scorer (used if model file is missing
or fails to load — ensures the pipeline always produces valid output).

Model file: snipgen/scoring/models/ontarget_xgb.pkl
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

from snipgen.models.grna_candidate import GRNACandidate

logger = logging.getLogger("snipgen.scoring.ontarget")

_MODEL_PATH = Path(__file__).parent / "models" / "ontarget_xgb.pkl"

_COMPLEMENT = str.maketrans("ACGT", "TGCA")
NUCLEOTIDES = ["A", "C", "G", "T"]


# ── Feature extraction (must match train_ontarget_model.py) ───────────────────

def _extract_features(seq: str) -> np.ndarray:
    """97-dimensional feature vector from a 20bp guide sequence."""
    seq = seq.upper()[:20].ljust(20, "N")
    features = np.zeros(97, dtype=np.float32)

    for i, nuc in enumerate(seq):
        if nuc in NUCLEOTIDES:
            features[i * 4 + NUCLEOTIDES.index(nuc)] = 1.0

    gc = sum(1 for n in seq if n in "GC") / 20.0
    features[80] = gc
    seed = seq[8:]
    features[81] = sum(1 for n in seed if n in "GC") / 12.0
    features[82] = sum(1 for n in seq[:10] if n in "GC") / 10.0
    features[83] = sum(1 for n in seq[10:] if n in "GC") / 10.0

    at = sum(1 for n in seq if n in "AT")
    features[84] = (2 * at + 4 * (20 - at)) / 100.0
    at_seed = sum(1 for n in seed if n in "AT")
    features[85] = (2 * at_seed + 4 * (12 - at_seed)) / 100.0
    at_dist = sum(1 for n in seq[:8] if n in "AT")
    features[86] = (2 * at_dist + 4 * (8 - at_dist)) / 100.0

    sc_score = 0.0
    rc_map = str.maketrans("ACGT", "TGCA")
    for k in range(4, 9):
        for j in range(len(seq) - 2 * k):
            window = seq[j:j + k]
            rc = window[::-1].translate(rc_map)
            if rc in seq[j + k:]:
                sc_score += k / 20.0
    features[87] = min(sc_score, 1.0)

    if seq[0] in NUCLEOTIDES:
        features[88 + NUCLEOTIDES.index(seq[0])] = 1.0
    if seq[-1] in NUCLEOTIDES:
        features[92 + NUCLEOTIDES.index(seq[-1])] = 1.0

    max_run, cur = 1, 1
    for j in range(1, 20):
        if seq[j] == seq[j - 1]:
            cur += 1; max_run = max(max_run, cur)
        else:
            cur = 1
    features[96] = min((max_run - 1) / 5.0, 1.0)

    return features


# ── Rule-based fallback components ────────────────────────────────────────────

def _reverse_complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _self_complementarity_score(seq: str) -> float:
    rc = _reverse_complement(seq)
    penalty = 0.0
    for length in range(6, min(13, len(seq) + 1)):
        for i in range(len(seq) - length + 1):
            if seq[i: i + length] in rc:
                penalty = length * 8.0
                break
        if penalty:
            break
    return max(0.0, 100.0 - penalty)


def _thermodynamic_score(seed: str) -> float:
    gc = seed.count("G") + seed.count("C")
    at = seed.count("A") + seed.count("T")
    tm = 4 * gc + 2 * at
    return max(0.0, 100.0 - abs(tm - 44) * 4.0)


def _position_score(seq: str) -> float:
    score = 50.0
    if len(seq) < 20:
        return score
    if seq[0] == "G":   score += 15.0
    if seq[2] == "C":   score += 10.0
    if seq[3] == "T":   score -= 15.0
    if seq[-1] == "G":  score += 10.0
    if seq[-2] == "G":  score += 5.0
    return max(0.0, min(100.0, score))


def _gc_bell_score(gc_fraction: float) -> float:
    gc_pct = gc_fraction * 100.0
    if 40.0 <= gc_pct <= 70.0:
        return 100.0 * (1.0 - abs(gc_pct - 55.0) / 15.0)
    return max(0.0, 100.0 * (1.0 - abs(gc_pct - 55.0) / 30.0))


def _leading_base_score(seq: str) -> float:
    if not seq:
        return 50.0
    return {"G": 100.0, "C": 60.0, "A": 20.0, "T": 20.0}.get(seq[0], 50.0)


def _homopolymer_score(seq: str, has_homopolymer: bool, has_poly_t: bool) -> float:
    if has_poly_t:    return 0.0
    if has_homopolymer: return 20.0
    for i in range(len(seq) - 2):
        if seq[i] == seq[i + 1] == seq[i + 2]:
            return 60.0
    return 100.0


# ── Scorer class ──────────────────────────────────────────────────────────────

class OnTargetScorer:
    """
    On-target efficiency scorer.

    Uses a trained XGBoost model (primary) with a six-component rule-based
    scorer as automatic fallback if the model file is unavailable.
    """

    _RULE_WEIGHTS = {
        "gc": 0.25, "position": 0.30, "homopolymer": 0.10,
        "thermodynamic": 0.15, "leading_base": 0.10, "self_comp": 0.10,
    }

    def __init__(self, model_path: Optional[Path] = None):
        self._model = None
        self._model_meta: dict = {}
        path = model_path or _MODEL_PATH
        try:
            with open(path, "rb") as f:
                payload = pickle.load(f)
            self._model = payload["model"]
            self._model_meta = payload.get("metrics", {})
            logger.info(
                "OnTargetScorer: XGBoost model loaded (val_r2=%.3f, val_spearman=%.3f)",
                self._model_meta.get("val_r2", 0),
                self._model_meta.get("val_spearman", 0),
            )
        except FileNotFoundError:
            logger.warning(
                "OnTargetScorer: model file not found at %s — using rule-based fallback. "
                "Run snipgen/scoring/train_ontarget_model.py to build the model.",
                path,
            )
        except Exception as exc:
            logger.warning("OnTargetScorer: model load failed (%s) — using rule-based fallback.", exc)

    @property
    def using_ml_model(self) -> bool:
        return self._model is not None

    def score(self, candidate: GRNACandidate) -> tuple[float, dict]:
        """
        Score a single guide. Returns (score_0_to_100, breakdown_dict).

        The breakdown always includes the rule-based sub-components for
        explainability, even when the XGBoost model provides the primary score.
        """
        seq = candidate.sequence.upper()
        seed = seq[-12:] if len(seq) >= 12 else seq

        # Rule-based sub-components (always computed for explainability)
        components = {
            "gc":           _gc_bell_score(candidate.gc_content),
            "position":     _position_score(seq),
            "homopolymer":  _homopolymer_score(seq, candidate.has_homopolymer, candidate.has_poly_t),
            "thermodynamic": _thermodynamic_score(seed),
            "leading_base": _leading_base_score(seq),
            "self_comp":    _self_complementarity_score(seq),
        }
        rule_score = sum(self._RULE_WEIGHTS[k] * v for k, v in components.items())

        breakdown = {f"on_{k}": round(v, 1) for k, v in components.items()}
        breakdown["gc_pct"] = round(candidate.gc_content * 100, 1)
        breakdown["rule_based_score"] = round(rule_score, 1)

        if self._model is not None:
            try:
                feat = _extract_features(seq).reshape(1, -1)
                ml_raw = float(self._model.predict(feat)[0])
                ml_score = max(0.0, min(100.0, ml_raw))
                breakdown["ml_score"] = round(ml_score, 1)
                breakdown["scorer"] = "gradient_boosting_ml"
                breakdown["model_val_spearman"] = self._model_meta.get("val_spearman", "n/a")
                return round(ml_score, 1), breakdown
            except Exception as exc:
                logger.warning("XGBoost inference failed (%s) — falling back to rules.", exc)

        breakdown["scorer"] = "rule_based_fallback"
        return round(rule_score, 1), breakdown
