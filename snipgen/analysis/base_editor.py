"""
Base editing analysis module for SnipGen.

Base editors (BEs) are Cas9-derived tools that make precise single-nucleotide
changes without double-strand breaks. Two main classes:

  CBE (Cytosine Base Editor):  C → T  (or G → A on opposite strand)
  ABE (Adenine Base Editor):   A → G  (or T → C on opposite strand)

Edit window
───────────
All SpCas9-based BEs act within a defined window of the protospacer,
counted from the PAM-distal (5') end, positions 1–20:

  CBE3/BE3:    positions 4–8   (Komor et al. 2016, Nature)
  CBE4/BE4:    positions 4–8   (Komor et al. 2017, Science)
  BE4max:      positions 4–8   (Koblan et al. 2018, Nature Biotechnology)
  ABE7.10:     positions 4–7   (Gaudelli et al. 2017, Nature)
  ABE8e:       positions 4–8   (Richter et al. 2020, Nature Biotechnology)
  ABE8.20:     positions 4–8
  Target-AID:  positions 2–4   (Nishida et al. 2016, Science)

This module analyzes whether a given 20-mer guide is suitable for base
editing, identifies which bases fall in the active window, and flags
bystander edits.

Returned per-guide dict
───────────────────────
{
  "cbe_targets":      list[dict],  # C's in CBE window 4-8
  "abe_targets":      list[dict],  # A's in ABE window 4-8
  "cbe_bystanders":   list[dict],  # C's OUTSIDE window (positions 1-3 and 9-20)
  "abe_bystanders":   list[dict],  # A's outside window
  "cbe_suitable":     bool,        # ≥1 C in window, no disruptive bystanders
  "abe_suitable":     bool,        # ≥1 A in window
  "cbe_efficiency_est": str,       # "HIGH" | "MODERATE" | "LOW" based on window position
  "abe_efficiency_est": str,
  "cbe_flag":         str,
  "abe_flag":         str,
  "edit_window_seq":  str,         # subsequence at positions 4-8 (guide[3:8])
  "cbe_product_seq":  str,         # guide with all window Cs → T
  "abe_product_seq":  str,         # guide with all window As → G
}
"""

from __future__ import annotations

# Position numbering: 1-based from PAM-distal (5') end of protospacer
# Guide sequence index: position N → guide[N-1]

# Active windows (inclusive, 1-based)
CBE_WINDOW    = (4, 8)   # BE3 / BE4 / BE4max
ABE_WINDOW    = (4, 8)   # ABE8e / ABE8.20
TARGET_AID_W  = (2, 4)   # Target-AID (narrower, higher precision)

# Bystander risk drops off sharply outside ±1 position from window edge
_BYSTANDER_RISK: dict[str, float] = {
    "HIGH":     1.0,   # adjacent to window (±1)
    "MODERATE": 0.5,   # two positions from window
    "LOW":      0.2,   # further out
}


def _is_in_window(pos_1based: int, window: tuple[int, int]) -> bool:
    return window[0] <= pos_1based <= window[1]


def _bystander_risk(pos_1based: int, window: tuple[int, int]) -> str:
    dist = min(abs(pos_1based - window[0]), abs(pos_1based - window[1]))
    if dist == 1:
        return "MODERATE"
    elif dist == 2:
        return "LOW"
    elif dist <= 3:
        return "MINIMAL"
    return "NONE"


def _efficiency_estimate(positions: list[int], window: tuple[int, int]) -> str:
    """
    Estimate editing efficiency based on the position of targetable bases
    within the window. Positions closer to the center of the window (pos 5-6)
    have the highest editing rates.

    Empirical note: Rees & Liu 2018 (Nature Reviews Genetics) show a
    peak at positions 5-6 for BE3 and ABE7.10 datasets.
    """
    if not positions:
        return "NONE"
    best = min(positions, key=lambda p: abs(p - 5.5))  # closest to window center
    dist_from_center = abs(best - 5.5)
    if dist_from_center <= 1.0:
        return "HIGH"
    elif dist_from_center <= 2.0:
        return "MODERATE"
    else:
        return "LOW"


def analyze_base_editing(guide_seq: str, strand: str = "+") -> dict:
    """
    Analyze a 20-mer guide for base editing suitability.

    Args:
        guide_seq: 20-mer guide (5'→3', no PAM)
        strand:    "+" or "-" — used to report genomic context correctly

    Returns comprehensive base editing annotation dict.
    """
    guide = guide_seq.upper().strip()[:20].ljust(20, "N")
    cbe_w, abe_w = CBE_WINDOW, ABE_WINDOW

    cbe_targets:    list[dict] = []
    abe_targets:    list[dict] = []
    cbe_bystanders: list[dict] = []
    abe_bystanders: list[dict] = []

    for i, nuc in enumerate(guide):
        pos = i + 1  # 1-based

        if nuc == "C":
            if _is_in_window(pos, cbe_w):
                cbe_targets.append({
                    "pos": pos,
                    "guide_idx": i,
                    "base": "C",
                    "product": "T",
                    "in_window": True,
                    "genomic_change": "C→T" if strand == "+" else "G→A",
                })
            else:
                risk = _bystander_risk(pos, cbe_w)
                if risk not in ("NONE",):
                    cbe_bystanders.append({
                        "pos": pos,
                        "guide_idx": i,
                        "base": "C",
                        "bystander_risk": risk,
                    })

        elif nuc == "A":
            if _is_in_window(pos, abe_w):
                abe_targets.append({
                    "pos": pos,
                    "guide_idx": i,
                    "base": "A",
                    "product": "G",
                    "in_window": True,
                    "genomic_change": "A→G" if strand == "+" else "T→C",
                })
            else:
                risk = _bystander_risk(pos, abe_w)
                if risk not in ("NONE",):
                    abe_bystanders.append({
                        "pos": pos,
                        "guide_idx": i,
                        "base": "A",
                        "bystander_risk": risk,
                    })

    # Compute product sequences (all window targets converted)
    cbe_product = list(guide)
    for t in cbe_targets:
        cbe_product[t["guide_idx"]] = "T"
    cbe_product_seq = "".join(cbe_product)

    abe_product = list(guide)
    for t in abe_targets:
        abe_product[t["guide_idx"]] = "G"
    abe_product_seq = "".join(abe_product)

    # Suitability
    cbe_suitable = len(cbe_targets) >= 1
    abe_suitable = len(abe_targets) >= 1

    # Efficiency estimates
    cbe_positions = [t["pos"] for t in cbe_targets]
    abe_positions = [t["pos"] for t in abe_targets]
    cbe_eff = _efficiency_estimate(cbe_positions, cbe_w)
    abe_eff = _efficiency_estimate(abe_positions, abe_w)

    # Human-readable flags
    def _cbe_flag() -> str:
        if not cbe_targets:
            return "No cytosines in CBE edit window (positions 4–8) — not a CBE candidate"
        parts = [f"CBE: {len(cbe_targets)} targetable C(s) at position(s) {', '.join(str(t['pos']) for t in cbe_targets)}"]
        if cbe_bystanders:
            parts.append(
                f"⚠ {len(cbe_bystanders)} bystander C(s) near window "
                f"(pos {', '.join(str(b['pos']) for b in cbe_bystanders)}) — "
                "may be co-edited at lower efficiency"
            )
        if cbe_eff == "HIGH":
            parts.append("✅ Target position is in high-efficiency zone (pos 5–6)")
        return " · ".join(parts)

    def _abe_flag() -> str:
        if not abe_targets:
            return "No adenines in ABE edit window (positions 4–8) — not an ABE candidate"
        parts = [f"ABE: {len(abe_targets)} targetable A(s) at position(s) {', '.join(str(t['pos']) for t in abe_targets)}"]
        if abe_bystanders:
            parts.append(
                f"⚠ {len(abe_bystanders)} bystander A(s) near window — may co-edit"
            )
        if abe_eff == "HIGH":
            parts.append("✅ Target in high-efficiency zone")
        return " · ".join(parts)

    return {
        "cbe_targets":        cbe_targets,
        "abe_targets":        abe_targets,
        "cbe_bystanders":     cbe_bystanders,
        "abe_bystanders":     abe_bystanders,
        "cbe_suitable":       cbe_suitable,
        "abe_suitable":       abe_suitable,
        "cbe_efficiency_est": cbe_eff if cbe_suitable else "NONE",
        "abe_efficiency_est": abe_eff if abe_suitable else "NONE",
        "cbe_flag":           _cbe_flag(),
        "abe_flag":           _abe_flag(),
        "edit_window_seq":    guide[3:8],
        "cbe_product_seq":    cbe_product_seq,
        "abe_product_seq":    abe_product_seq,
        "guide_annotated":    _annotate_guide(guide, cbe_targets, abe_targets, cbe_w),
    }


def _annotate_guide(
    guide: str,
    cbe_targets: list[dict],
    abe_targets: list[dict],
    window: tuple[int, int],
) -> list[dict]:
    """
    Return per-nucleotide annotation for the guide sequence.
    Each element: {"pos": int, "base": str, "role": str, "in_window": bool}
    role = "CBE_target" | "ABE_target" | "window" | "seed" | "normal"
    """
    cbe_idxs = {t["guide_idx"] for t in cbe_targets}
    abe_idxs = {t["guide_idx"] for t in abe_targets}
    annotated = []
    for i, nuc in enumerate(guide):
        pos = i + 1
        in_win = _is_in_window(pos, window)
        if i in cbe_idxs:
            role = "CBE_target"
        elif i in abe_idxs:
            role = "ABE_target"
        elif in_win:
            role = "window"
        elif pos >= 9:   # seed region
            role = "seed"
        else:
            role = "normal"
        annotated.append({"pos": pos, "base": nuc, "role": role, "in_window": in_win})
    return annotated


def batch_analyze_base_editing(candidates: list) -> None:
    """
    Annotate GRNACandidate objects with base editing data in-place.
    Stores results in score_breakdown["base_edit"].
    """
    for c in candidates:
        try:
            result = analyze_base_editing(c.sequence, getattr(c, "strand", "+"))
            if hasattr(c, "score_breakdown"):
                c.score_breakdown["base_edit"] = result
        except Exception:
            pass
