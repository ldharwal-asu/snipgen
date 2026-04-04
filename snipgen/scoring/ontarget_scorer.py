"""On-target quality scorer implementing Doench 2016-inspired rules (0-100 scale)."""

from snipgen.models.grna_candidate import GRNACandidate

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _reverse_complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def _self_complementarity_score(seq: str) -> float:
    rc = _reverse_complement(seq)
    penalty = 0.0
    for length in range(6, min(13, len(seq) + 1)):
        for i in range(len(seq) - length + 1):
            if seq[i : i + length] in rc:
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
    if seq[0] == "G":
        score += 15.0
    if seq[2] == "C":
        score += 10.0
    if seq[3] == "T":
        score -= 15.0
    if seq[-1] == "G":
        score += 10.0
    if seq[-2] == "G":
        score += 5.0
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
    if has_poly_t:
        return 0.0
    if has_homopolymer:
        return 20.0
    for i in range(len(seq) - 2):
        if seq[i] == seq[i + 1] == seq[i + 2]:
            return 60.0
    return 100.0


class OnTargetScorer:
    """Six-component on-target quality scorer (0-100 scale)."""

    WEIGHTS = {
        "gc": 0.25,
        "position": 0.30,
        "homopolymer": 0.10,
        "thermodynamic": 0.15,
        "leading_base": 0.10,
        "self_comp": 0.10,
    }

    def score(self, candidate: GRNACandidate) -> tuple[float, dict]:
        seq = candidate.sequence.upper()
        seed = seq[-12:] if len(seq) >= 12 else seq

        components = {
            "gc": _gc_bell_score(candidate.gc_content),
            "position": _position_score(seq),
            "homopolymer": _homopolymer_score(seq, candidate.has_homopolymer, candidate.has_poly_t),
            "thermodynamic": _thermodynamic_score(seed),
            "leading_base": _leading_base_score(seq),
            "self_comp": _self_complementarity_score(seq),
        }

        composite = sum(self.WEIGHTS[k] * v for k, v in components.items())
        breakdown = {f"on_{k}": round(v, 1) for k, v in components.items()}
        breakdown["gc_pct"] = round(candidate.gc_content * 100, 1)

        return round(composite, 1), breakdown
