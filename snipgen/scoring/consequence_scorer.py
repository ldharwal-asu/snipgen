"""Consequence-aware safety scorer (0-100 scale).

Tier 1 (default): Returns a default score — no genome-wide annotation DB available.
Tier 2+: Would look up off-target positions in RefSeq/COSMIC-derived SQLite DB.

Risk tier weights (SnipGen v2 spec):
  CRITICAL  tumor_suppressor_exon / oncogene_exon  10.0
  HIGH      coding_exon / splice_site               5.0
  MEDIUM    promoter / utr                         2.5-3.0
  LOW       intron                                  1.0
  MINIMAL   intergenic / repeat                   0.1-0.2
"""

from snipgen.models.grna_candidate import GRNACandidate

RISK_WEIGHTS: dict[str, float] = {
    "tumor_suppressor_exon": 10.0,
    "oncogene_exon": 10.0,
    "coding_exon": 5.0,
    "splice_site": 5.0,
    "promoter": 3.0,
    "utr": 2.5,
    "intron": 1.0,
    "intergenic": 0.2,
    "repeat": 0.1,
}

_TIER1_DEFAULT_SCORE = 85.0


class ConsequenceScorer:
    """Score biological consequence severity of off-target sites.

    In Tier 1 (no annotation DB), returns a fixed default score and records
    the data tier so the confidence scorer can penalise accordingly.
    """

    def __init__(self, annotation_db=None):
        self.annotation_db = annotation_db
        self.tier = "tier2" if annotation_db is not None else "tier1"

    def score_all(self, candidates: list[GRNACandidate]) -> None:
        """Annotate candidates with consequence_score in-place."""
        for c in candidates:
            if self.annotation_db is not None:
                c.consequence_score = self._score_with_db(c)
            else:
                c.consequence_score = _TIER1_DEFAULT_SCORE
                c.score_breakdown["consequence_tier"] = "tier1"
                c.score_breakdown["consequence_note"] = (
                    "No genome annotation DB; consequence score uses sequence-only default."
                )

    def _score_with_db(self, candidate: GRNACandidate) -> float:
        """Placeholder for Tier 2 DB lookup."""
        return _TIER1_DEFAULT_SCORE
