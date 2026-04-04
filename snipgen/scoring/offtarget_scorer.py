"""Tier 1 off-target burden estimation via within-sequence seed mismatch counting."""

from snipgen.models.grna_candidate import GRNACandidate


def estimate_off_target_burden(
    guide_seq: str,
    full_sequence: str,
    max_mismatches: int = 3,
) -> dict:
    """Count approximate off-target sites within the input sequence.

    Uses 12bp PAM-proximal seed as fast pre-filter, then full mismatch count.

    Returns:
        dict with total_sites, by_mismatch, burden_raw, burden_score (0-100)
    """
    guide = guide_seq.upper()[:20]
    seed = guide[-12:]
    off_targets: dict[int, int] = {i: 0 for i in range(1, max_mismatches + 1)}

    seq = full_sequence.upper()
    for i in range(len(seq) - 20):
        window = seq[i : i + 20]
        if window == guide:
            continue  # skip exact on-target match

        seed_mm = sum(1 for a, b in zip(seed, window[-12:]) if a != b)
        if seed_mm > 2:
            continue

        full_mm = sum(1 for a, b in zip(guide, window) if a != b)
        if 1 <= full_mm <= max_mismatches:
            off_targets[full_mm] += 1

    # 1-mm off-targets are ~3x more dangerous than 3-mm
    burden = sum(count * (1.0 / mm) for mm, count in off_targets.items())
    score = max(0.0, 100.0 - min(burden * 10.0, 100.0))

    return {
        "total_sites": sum(off_targets.values()),
        "by_mismatch": off_targets,
        "burden_raw": round(burden, 2),
        "burden_score": round(score, 1),
    }


class OffTargetScorer:
    """Apply Tier 1 off-target burden estimation to a batch of candidates."""

    def __init__(self, max_mismatches: int = 3):
        self.max_mismatches = max_mismatches

    def score_all(
        self,
        candidates: list[GRNACandidate],
        full_sequences: dict[str, str],
    ) -> None:
        """Annotate each candidate with off-target scores in-place."""
        for c in candidates:
            seq_text = full_sequences.get(c.chromosome, "")
            if not seq_text:
                c.off_target_score = 85.0
                continue

            result = estimate_off_target_burden(
                c.sequence, seq_text, self.max_mismatches
            )
            c.off_target_score = result["burden_score"]
            c.off_targets_1mm = result["by_mismatch"].get(1, 0)
            c.off_targets_2mm = result["by_mismatch"].get(2, 0)
            c.off_targets_3mm = result["by_mismatch"].get(3, 0)
            c.off_target_burden_raw = result["burden_raw"]
