"""Confidence and uncertainty scoring layer (0-100 scale)."""

from snipgen.models.grna_candidate import GRNACandidate


def classify_confidence(score: float) -> tuple[str, str]:
    """Map 0-100 confidence score to (safety_label, safety_color)."""
    if score >= 80:
        return "HIGH", "green"
    if score >= 50:
        return "MEDIUM", "yellow"
    if score >= 20:
        return "LOW", "orange"
    return "AVOID", "red"


class ConfidenceScorer:
    """Estimate recommendation confidence (0-100) from multiple signals.

    Signals and weights:
        score_margin      0.20  — gap from next-best composite
        sub_agreement     0.30  — variance across on/off/consequence sub-scores
        data_quality      0.25  — tier1=40, tier2=80, tier3=100
        complexity        0.15  — sequence complexity via unique 2-mers
        validation        0.10  — placeholder (50 = no validation data)
    """

    def __init__(self, data_tier: str = "tier1"):
        self.data_tier = data_tier
        self._tier_score = {"tier1": 40.0, "tier2": 80.0, "tier3": 100.0}

    def score_all(self, candidates: list[GRNACandidate]) -> None:
        """Annotate candidates with confidence_score, safety_label, safety_color in-place."""
        if not candidates:
            return

        composites = [c.final_score for c in candidates]
        sorted_composites = sorted(composites, reverse=True)

        for c in candidates:
            # 1. Score margin to next-best
            try:
                rank = sorted_composites.index(c.final_score)
            except ValueError:
                rank = 0
            if rank < len(sorted_composites) - 1:
                margin = c.final_score - sorted_composites[rank + 1]
                margin_signal = min(margin * 5.0, 100.0)
            else:
                margin_signal = 50.0

            # 2. Sub-score agreement (low variance = high confidence)
            sub = [c.on_target_score, c.off_target_score, c.consequence_score]
            mean_sub = sum(sub) / 3.0
            variance = sum((s - mean_sub) ** 2 for s in sub) / 3.0
            agreement_signal = max(0.0, 100.0 - variance * 0.02)

            # 3. Data quality tier
            tier_signal = self._tier_score.get(self.data_tier, 40.0)

            # 4. Sequence complexity via unique dinucleotides
            seq = c.sequence.upper()
            unique_2mers = len({seq[j : j + 2] for j in range(len(seq) - 1)})
            complexity_signal = min(unique_2mers * 6.0, 100.0)

            # 5. Validation placeholder
            validation_signal = 50.0

            confidence = (
                0.20 * margin_signal
                + 0.30 * agreement_signal
                + 0.25 * tier_signal
                + 0.15 * complexity_signal
                + 0.10 * validation_signal
            )
            c.confidence_score = round(confidence, 1)
            c.safety_label, c.safety_color = classify_confidence(confidence)
