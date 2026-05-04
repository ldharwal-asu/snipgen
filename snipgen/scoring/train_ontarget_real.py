"""
SnipGen on-target model trainer — Real Azimuth screen data edition.

Uses 5,310 experimentally measured guides from the Azimuth CRISPR screen
(Doench et al. 2016, Nature Biotechnology). This replaces the Doench-oracle
synthetic corpus with real measured cutting efficiency scores.

Data format (FC_plus_RES_withPredictions.csv):
  Column "30mer"              — 30-nt context sequence (4nt + 20-mer guide + 3nt PAM + 3nt)
  Column "score_drug_gene_rank" — rank-normalised cutting efficiency (0–1, higher = better)

Feature extraction is identical to train_ontarget_model.py so the trained
model is a drop-in replacement for ontarget_xgb.pkl.

Usage:
    python snipgen/scoring/train_ontarget_real.py

Output:
    snipgen/scoring/models/ontarget_xgb.pkl          (overwrites if present)
    snipgen/scoring/models/ontarget_xgb_metrics.json
"""

from __future__ import annotations

import csv
import json
import pathlib
import pickle
import time
import urllib.request
from io import StringIO
from typing import Optional

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

# ── Azimuth data source ───────────────────────────────────────────────────────
# Original data from Doench 2016 Supplementary Table 18 (publicly available)
# Mirrored at the Azimuth GitHub repository.
_AZIMUTH_URL = (
    "https://raw.githubusercontent.com/MicrosoftResearch/Azimuth/master/"
    "azimuth/data/FC_plus_RES_withPredictions.csv"
)
_LOCAL_CACHE = pathlib.Path("/tmp/azimuth_data.csv")

NUCLEOTIDES = ["A", "C", "G", "T"]


# ── Feature extraction (must stay in sync with train_ontarget_model.py) ───────

def extract_features(seq: str) -> np.ndarray:
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
    at_s = sum(1 for n in seed if n in "AT")
    features[85] = (2 * at_s + 4 * (12 - at_s)) / 100.0
    at_d = sum(1 for n in seq[:8] if n in "AT")
    features[86] = (2 * at_d + 4 * (8 - at_d)) / 100.0

    sc = 0.0
    rc_map = str.maketrans("ACGT", "TGCA")
    for k in range(4, 9):
        for j in range(len(seq) - 2 * k):
            rc = seq[j:j + k][::-1].translate(rc_map)
            if rc in seq[j + k:]:
                sc += k / 20.0
    features[87] = min(sc, 1.0)

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


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_azimuth(path: pathlib.Path) -> tuple[list[str], list[float]]:
    """
    Load Azimuth data. Returns (guide_seqs, scores_0_to_100).

    The 30-mer format is:  [4nt context] [20-mer guide] [3nt PAM] [3nt context]
    We extract positions 4–24 (0-indexed) to get the 20-mer guide sequence.
    score_drug_gene_rank is in [0,1] → multiply by 100 for our scale.
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    sequences: list[str] = []
    scores: list[float] = []

    for row in rows:
        seq_30 = row.get("30mer", "").strip().upper()
        score_raw = row.get("score_drug_gene_rank", "").strip()

        if not seq_30 or not score_raw:
            continue
        if len(seq_30) < 23:
            continue  # malformed row

        try:
            score = float(score_raw)
        except ValueError:
            continue

        # Extract 20-mer: skip 4nt context prefix, take next 20nt
        guide_20 = seq_30[4:24]
        if len(guide_20) != 20:
            continue
        if any(n not in "ACGT" for n in guide_20):
            continue

        sequences.append(guide_20)
        scores.append(score * 100.0)   # scale to 0–100

    return sequences, scores


def _download_azimuth(cache_path: pathlib.Path) -> None:
    print(f"Downloading Azimuth data from {_AZIMUTH_URL} ...")
    try:
        with urllib.request.urlopen(_AZIMUTH_URL, timeout=30) as resp:
            data = resp.read()
        cache_path.write_bytes(data)
        print(f"  Saved {len(data):,} bytes → {cache_path}")
    except Exception as exc:
        raise RuntimeError(f"Failed to download Azimuth data: {exc}") from exc


# ── Training ──────────────────────────────────────────────────────────────────

def train(
    seed: int = 42,
    output_dir: Optional[pathlib.Path] = None,
) -> dict:
    if output_dir is None:
        output_dir = pathlib.Path(__file__).parent / "models"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    if not _LOCAL_CACHE.exists():
        _download_azimuth(_LOCAL_CACHE)
    else:
        print(f"Using cached Azimuth data at {_LOCAL_CACHE}")

    sequences, scores = _load_azimuth(_LOCAL_CACHE)
    n = len(sequences)
    print(f"Loaded {n:,} valid guides from Azimuth screen data")

    if n < 100:
        raise RuntimeError(
            f"Only {n} valid rows loaded — check the Azimuth CSV format. "
            f"Expected columns: '30mer', 'score_drug_gene_rank'"
        )

    t0 = time.time()

    print("Extracting 97-dimensional feature vectors...")
    X = np.vstack([extract_features(s) for s in sequences])
    y = np.array(scores, dtype=np.float32)

    rng = np.random.default_rng(seed)
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=seed
    )

    print(
        f"Training GradientBoostingRegressor on {len(X_train):,} guides "
        f"(val={len(X_val):,})..."
    )
    model = GradientBoostingRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.07,
        subsample=0.80,
        min_samples_leaf=5,
        random_state=seed,
        verbose=0,
    )
    model.fit(X_train, y_train)

    y_pred_val   = model.predict(X_val)
    y_pred_train = model.predict(X_train)

    def r2(a, b):
        return float(r2_score(a, b))

    def spearman(a: np.ndarray, b: np.ndarray) -> float:
        n_ = len(a)
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        d2 = ((ra - rb) ** 2).sum()
        return float(1.0 - 6 * d2 / (n_ * (n_ * n_ - 1)))

    elapsed = time.time() - t0

    metrics = {
        "n_samples":        n,
        "n_train":          len(X_train),
        "n_val":            len(X_val),
        "n_features":       int(X.shape[1]),
        "train_r2":         round(r2(y_train, y_pred_train), 4),
        "val_r2":           round(r2(y_val,   y_pred_val),   4),
        "val_spearman":     round(spearman(y_val, y_pred_val), 4),
        "training_time_s":  round(elapsed, 1),
        "model_type":       "GradientBoostingRegressor (sklearn)",
        "data_source": (
            "Azimuth CRISPR screen — Doench et al. 2016, Nat Biotechnol 34:184-191. "
            "5,310 experimentally measured guides, score_drug_gene_rank column (0-1), "
            "rescaled to 0-100. 20-mer extracted from 30-mer context sequence."
        ),
        "seed": seed,
    }

    print(f"\n{'─'*60}")
    print(f"  Guides used         : {n:,} (real measured cutting efficiency)")
    print(f"  Train R²            : {metrics['train_r2']:.4f}")
    print(f"  Validation R²       : {metrics['val_r2']:.4f}")
    print(f"  Validation Spearman : {metrics['val_spearman']:.4f}")
    print(f"  Training time       : {elapsed:.1f}s")
    print(f"{'─'*60}\n")

    model_path = output_dir / "ontarget_xgb.pkl"
    with open(model_path, "wb") as f:
        pickle.dump({"model": model, "metrics": metrics, "feature_dim": X.shape[1]}, f)
    print(f"✅ Model saved → {model_path}")

    metrics_path = output_dir / "ontarget_xgb_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ Metrics saved → {metrics_path}")

    return metrics


if __name__ == "__main__":
    train()
