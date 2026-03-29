"""Deterministic rule-based scoring for gRNA candidates."""

from snipgen.models.grna_candidate import GRNACandidate


class RuleScorer:
    """Score candidates based on five weighted sequence-quality components.

    All components produce values in [0.0, 1.0] and are linearly combined.

    Components and weights:
    - GC proximity to 50%  (0.25): peaks at 50% GC, falls toward 40/70% bounds
    - Seed region GC       (0.20): lower seed GC → better (less off-target risk)
    - G at position 1      (0.15): G at 5' end improves U6 transcription efficiency
    - No homopolymer       (0.20): 1.0 if no 4+ homopolymer run, else 0.0
    - No poly-T            (0.20): 1.0 if no TTTT present, else 0.0

    Weights sum to 1.0, so final score is directly in [0.0, 1.0].
    """

    _GC_WEIGHT = 0.25
    _SEED_WEIGHT = 0.20
    _G1_WEIGHT = 0.15
    _HOMO_WEIGHT = 0.20
    _POLYT_WEIGHT = 0.20

    def score(self, candidate: GRNACandidate) -> float:
        gc = candidate.gc_content

        # GC proximity to 50%: linear fall-off from 50% toward 40% and 70%
        # Range spans 0.3 (from 50% down to 20% or up to 80%) — clipped to 0
        gc_score = max(0.0, 1.0 - abs(gc - 0.5) / 0.3)

        seed_score = max(0.0, 1.0 - candidate.seed_gc)

        g1_score = 1.0 if candidate.sequence and candidate.sequence[0] == "G" else 0.0

        homo_score = 0.0 if candidate.has_homopolymer else 1.0

        polyt_score = 0.0 if candidate.has_poly_t else 1.0

        return (
            self._GC_WEIGHT   * gc_score
            + self._SEED_WEIGHT * seed_score
            + self._G1_WEIGHT   * g1_score
            + self._HOMO_WEIGHT * homo_score
            + self._POLYT_WEIGHT * polyt_score
        )
