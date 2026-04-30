"""Consequence-aware safety scorer (0-100 scale).

Tier 1 (sequence-based heuristics):
    No genome annotation DB available. Score is estimated from sequence
    features that correlate with genomic context — CpG density, GC content,
    sequence complexity, splice-site motifs, and repetitive element signals.
    These are probabilistic proxies, not definitive annotations.

Tier 2+: Would look up guide positions in RefSeq/COSMIC-derived SQLite DB.

Score interpretation (higher = safer / lower consequence risk):
    90-100  Likely intergenic or repeat — minimal consequence
    70-89   Likely intronic — low consequence
    50-69   Possible UTR or promoter — moderate consequence
    30-49   Likely coding exon — high consequence
    0-29    Likely critical exon (CpG island, high complexity) — avoid

Risk tier weights (SnipGen v2 spec):
    CRITICAL  tumor_suppressor_exon / oncogene_exon  10.0
    HIGH      coding_exon / splice_site               5.0
    MEDIUM    promoter / utr                         2.5-3.0
    LOW       intron                                  1.0
    MINIMAL   intergenic / repeat                   0.1-0.2
"""

from __future__ import annotations

import math

from snipgen.models.grna_candidate import GRNACandidate

RISK_WEIGHTS: dict[str, float] = {
    "tumor_suppressor_exon": 10.0,
    "oncogene_exon":         10.0,
    "coding_exon":            5.0,
    "splice_site":            5.0,
    "promoter":               3.0,
    "utr":                    2.5,
    "intron":                 1.0,
    "intergenic":             0.2,
    "repeat":                 0.1,
}


# ── Sequence-based consequence heuristics ─────────────────────────────────────

def _cpg_density(seq: str) -> float:
    """CpG dinucleotide frequency (0-1). High = likely promoter/exon."""
    if len(seq) < 2:
        return 0.0
    cpg = sum(1 for i in range(len(seq) - 1) if seq[i] == "C" and seq[i + 1] == "G")
    return cpg / (len(seq) - 1)


def _sequence_complexity(seq: str) -> float:
    """
    Linguistic complexity via dinucleotide entropy (0-1).
    High = complex sequence = more likely coding/regulatory.
    Low  = repetitive = more likely intergenic/repeat element.
    """
    if len(seq) < 2:
        return 0.5
    pairs: dict[str, int] = {}
    for i in range(len(seq) - 1):
        d = seq[i:i + 2]
        pairs[d] = pairs.get(d, 0) + 1
    total = sum(pairs.values())
    entropy = 0.0
    for count in pairs.values():
        p = count / total
        entropy -= p * math.log2(p)
    # Max entropy for 16 dinucleotides = log2(16) = 4.0
    return entropy / 4.0


def _splice_site_risk(seq: str) -> float:
    """
    Detect canonical splice site motifs within the guide.
    GT/AG at guide edges suggests proximity to exon-intron boundaries.
    Returns a risk score 0-1 (1 = high splice site risk).
    """
    risk = 0.0
    # Donor site motif: GT near 5' end
    if seq[:2] == "GT" or seq[1:3] == "GT":
        risk += 0.5
    # Acceptor site motif: AG near 3' end
    if seq[-2:] == "AG" or seq[-3:-1] == "AG":
        risk += 0.5
    # Internal GT-AG
    for i in range(2, len(seq) - 3):
        if seq[i:i + 2] == "GT" and seq[i + 3:i + 5] == "AG":
            risk = min(risk + 0.3, 1.0)
    return min(risk, 1.0)


def _repeat_signal(seq: str) -> float:
    """
    Low-complexity / repeat signal (0-1). High = likely repeat element.
    Detects homopolymer runs, tandem repeats, and low dinucleotide diversity.
    """
    # Max homopolymer run
    max_run, cur = 1, 1
    for i in range(1, len(seq)):
        if seq[i] == seq[i - 1]:
            cur += 1; max_run = max(max_run, cur)
        else:
            cur = 1

    # Tandem dinucleotide repeat (e.g. ATATATATAT)
    tandem = 0
    for i in range(0, len(seq) - 3, 2):
        if seq[i:i + 2] == seq[i + 2:i + 4]:
            tandem += 1

    run_score   = min((max_run - 1) / 6.0, 1.0)
    tandem_score = min(tandem / 5.0, 1.0)
    return (run_score * 0.6 + tandem_score * 0.4)


def _score_sequence(seq: str, gc: float) -> tuple[float, dict]:
    """
    Estimate consequence safety score (0-100) from sequence features alone.

    High score (safe)  = intergenic-like: low GC, low complexity, high repeats
    Low score (danger) = exonic-like: high CpG, high complexity, splice motifs
    """
    seq = seq.upper()

    cpg      = _cpg_density(seq)
    complexity = _sequence_complexity(seq)
    splice   = _splice_site_risk(seq)
    repeat   = _repeat_signal(seq)

    # Seed GC (PAM-proximal 12 bp) — high seed GC → likely in coding region
    seed     = seq[8:] if len(seq) >= 12 else seq
    seed_gc  = sum(1 for n in seed if n in "GC") / len(seed)

    # --- Risk accumulation (0 = safe, higher = more dangerous) ---
    risk = 0.0

    # CpG density: strong indicator of promoter/exon CpG islands
    # CpG > 0.10 is characteristic of CpG islands (promoters/exons)
    if cpg > 0.10:
        risk += 35.0 * (cpg / 0.15)      # peaks at ~35 pts at CpG=0.15

    # High overall GC: >65% strongly suggests coding/regulatory
    if gc > 0.65:
        risk += 20.0 * ((gc - 0.65) / 0.20)
    elif gc > 0.55:
        risk += 10.0 * ((gc - 0.55) / 0.10)

    # High seed GC raises coding probability
    if seed_gc > 0.70:
        risk += 10.0 * ((seed_gc - 0.70) / 0.30)

    # Sequence complexity: high complexity = likely exonic
    if complexity > 0.80:
        risk += 15.0 * ((complexity - 0.80) / 0.20)
    elif complexity > 0.65:
        risk += 8.0 * ((complexity - 0.65) / 0.15)

    # Splice site motifs
    risk += splice * 18.0

    # Repeat signal REDUCES risk (repeats are low consequence)
    risk -= repeat * 20.0

    # Low GC (<40%) suggests intergenic — reduce risk
    if gc < 0.40:
        risk -= 15.0 * ((0.40 - gc) / 0.20)

    risk = max(0.0, min(100.0, risk))
    score = round(100.0 - risk, 1)

    breakdown = {
        "cpg_density":       round(cpg, 3),
        "seq_complexity":    round(complexity, 3),
        "splice_risk":       round(splice, 3),
        "repeat_signal":     round(repeat, 3),
        "seed_gc":           round(seed_gc, 3),
        "consequence_risk_raw": round(risk, 1),
    }
    return score, breakdown


class ConsequenceScorer:
    """
    Score biological consequence severity of potential off-target sites.

    Tier 1 (default): Sequence-based heuristics — CpG density, GC content,
    sequence complexity, splice-site motifs, and repeat signals proxy for
    genomic context without requiring an annotation database.

    Tier 2+: Position lookup in RefSeq/COSMIC-derived annotation DB.
    """

    def __init__(self, annotation_db=None):
        self.annotation_db = annotation_db
        self.tier = "tier2" if annotation_db is not None else "tier1_sequence_heuristic"

    def score_all(self, candidates: list[GRNACandidate]) -> None:
        """Annotate candidates with consequence_score in-place."""
        for c in candidates:
            if self.annotation_db is not None:
                c.consequence_score = self._score_with_db(c)
            else:
                score, breakdown = _score_sequence(c.sequence, c.gc_content)
                c.consequence_score = score
                c.score_breakdown["consequence_tier"] = self.tier
                c.score_breakdown.update({f"csq_{k}": v for k, v in breakdown.items()})

    def _score_with_db(self, candidate: GRNACandidate) -> float:
        """Placeholder for Tier 2 DB lookup."""
        score, _ = _score_sequence(candidate.sequence, candidate.gc_content)
        return score
