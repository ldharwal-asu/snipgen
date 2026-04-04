"""V2 composite scorer: on-target, off-target, consequence, confidence → final_score (0-100)."""

import logging

from snipgen.models.grna_candidate import GRNACandidate
from snipgen.scoring.confidence_scorer import ConfidenceScorer
from snipgen.scoring.consequence_scorer import ConsequenceScorer
from snipgen.scoring.offtarget_scorer import OffTargetScorer
from snipgen.scoring.ontarget_scorer import OnTargetScorer
from snipgen.scoring.recommendation import generate_recommendation

logger = logging.getLogger("snipgen.scoring.composite_scorer")

# Safety-first preset weights
DEFAULT_WEIGHTS = {
    "on_target": 0.30,
    "off_target": 0.25,
    "consequence": 0.30,
    "confidence": 0.15,
}


class CompositeScorer:
    """Four-dimensional safety-first composite scorer (0-100 scale).

    Dimensions:
        on_target     — cutting efficiency probability
        off_target    — off-target burden (higher = fewer/weaker OTs)
        consequence   — biological danger of off-target sites
        confidence    — recommendation certainty

    Accepts V1 kwargs (rule_scorer, ml_scorer, rule_weight, ml_weight)
    for backward compatibility but ignores them.
    """

    def __init__(
        self,
        weights: dict | None = None,
        annotation_db=None,
        data_tier: str = "tier1",
        max_mismatches: int = 3,
        # V1 compat — accepted but unused
        rule_scorer=None,
        ml_scorer=None,
        rule_weight: float = 1.0,
        ml_weight: float = 0.0,
    ):
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.on_target_scorer = OnTargetScorer()
        self.off_target_scorer = OffTargetScorer(max_mismatches=max_mismatches)
        self.consequence_scorer = ConsequenceScorer(annotation_db=annotation_db)
        self.confidence_scorer = ConfidenceScorer(data_tier=data_tier)

    def score_all(
        self,
        candidates: list[GRNACandidate],
        full_sequences: dict[str, str] | None = None,
    ) -> list[GRNACandidate]:
        """Score all candidates in-place and return them."""
        if not candidates:
            return candidates

        full_sequences = full_sequences or {}
        w = self.weights
        total_w = sum(w.values()) or 1.0

        # 1. On-target quality
        for c in candidates:
            score, breakdown = self.on_target_scorer.score(c)
            c.on_target_score = score
            c.rule_score = round(score / 100.0, 4)  # V1 compat
            c.score_breakdown.update(breakdown)

        # 2. Off-target burden (Tier 1 within-sequence)
        self.off_target_scorer.score_all(candidates, full_sequences)

        # 3. Consequence safety
        self.consequence_scorer.score_all(candidates)

        # 4. Preliminary composite (without confidence) for margin calculation
        conf_w = w.get("confidence", 0.15)
        pre_total = total_w - conf_w
        for c in candidates:
            c.final_score = round(
                (
                    w["on_target"] * c.on_target_score
                    + w["off_target"] * c.off_target_score
                    + w["consequence"] * c.consequence_score
                ) / pre_total,
                1,
            )

        # 5. Confidence (uses preliminary final_score for margin signal)
        self.confidence_scorer.score_all(candidates)

        # 6. True final score including confidence dimension
        for c in candidates:
            c.final_score = round(
                (
                    w["on_target"] * c.on_target_score
                    + w["off_target"] * c.off_target_score
                    + w["consequence"] * c.consequence_score
                    + conf_w * c.confidence_score
                ) / total_w,
                1,
            )
            c.ml_score = 0.5  # V1 compat

        # 7. Natural language recommendations
        for c in candidates:
            c.recommendation = generate_recommendation(c)

        logger.info("Scored %d candidates (v2 composite, 4-dimensional)", len(candidates))
        return candidates
