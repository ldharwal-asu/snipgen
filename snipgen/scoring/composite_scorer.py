"""Aggregate rule-based and ML scores into a single final score."""

import logging

from snipgen.models.grna_candidate import GRNACandidate
from snipgen.scoring.ml_scorer import MLScorerProtocol
from snipgen.scoring.rule_scorer import RuleScorer

logger = logging.getLogger("snipgen.scoring.composite_scorer")


class CompositeScorer:
    """Combine rule_score and ml_score into a weighted final_score.

    If the ML scorer is unavailable (PassthroughMLScorer.is_available() == False),
    ml_weight is silently collapsed to 0 and rule_weight takes full weight.
    This ensures the tool is fully functional without a trained model.
    """

    def __init__(
        self,
        rule_scorer: RuleScorer,
        ml_scorer: MLScorerProtocol,
        rule_weight: float = 1.0,
        ml_weight: float = 0.0,
    ):
        self.rule_scorer = rule_scorer
        self.ml_scorer = ml_scorer
        self.rule_weight = rule_weight
        # Graceful degradation: collapse ml_weight if no model is loaded
        self.ml_weight = ml_weight if ml_scorer.is_available() else 0.0

        if ml_weight > 0 and not ml_scorer.is_available():
            logger.info(
                "ML scorer not available; ml_weight %.2f collapsed to 0 "
                "(rule scoring only)",
                ml_weight,
            )

    def score_all(self, candidates: list[GRNACandidate]) -> list[GRNACandidate]:
        """Score all candidates in-place and return them."""
        if not candidates:
            return candidates

        ml_scores = self.ml_scorer.score(candidates)
        total_w = self.rule_weight + self.ml_weight or 1.0

        for candidate, ml_s in zip(candidates, ml_scores):
            candidate.rule_score = self.rule_scorer.score(candidate)
            candidate.ml_score = ml_s
            candidate.final_score = (
                self.rule_weight * candidate.rule_score
                + self.ml_weight * ml_s
            ) / total_w

        return candidates
