"""Heuristic off-target risk filter."""

from snipgen.filters.base_filter import BaseFilter
from snipgen.models.grna_candidate import GRNACandidate
from snipgen.utils.nucleotide import gc_content, has_homopolymer, has_poly_t


class OffTargetFilter(BaseFilter):
    """Apply seed-region and sequence-composition heuristics to reduce off-target risk.

    Three hard-fail checks:
    1. Seed region GC > max_seed_gc (default 75%) — high seed GC drives off-target R-loops
    2. Poly-T run (default ≥4 T's) — Pol-III termination signal in U6 context
    3. Homopolymer run (default ≥4 identical bases) — reduces on-target efficiency

    The seed region is the 12 nt proximal to the PAM (last 12 of the 20-nt spacer
    for 3' PAM systems like SpCas9).
    """

    def __init__(
        self,
        seed_length: int = 12,
        max_seed_gc: float = 0.75,
        poly_t_run: int = 4,
        homopolymer_run: int = 4,
    ):
        self.seed_length = seed_length
        self.max_seed_gc = max_seed_gc
        self.poly_t_run = poly_t_run
        self.homopolymer_run = homopolymer_run

    def apply(self, candidate: GRNACandidate) -> GRNACandidate:
        seq = candidate.sequence.upper()

        # Seed region: last seed_length nucleotides (proximal to PAM)
        seed = seq[-self.seed_length:] if len(seq) >= self.seed_length else seq
        candidate.seed_gc = gc_content(seed)
        seed_ok = candidate.seed_gc <= self.max_seed_gc

        # Poly-T check
        candidate.has_poly_t = has_poly_t(seq, min_run=self.poly_t_run)
        poly_t_ok = not candidate.has_poly_t

        # Homopolymer check
        candidate.has_homopolymer = has_homopolymer(seq, min_run=self.homopolymer_run)
        homopolymer_ok = not candidate.has_homopolymer

        candidate.offtarget_pass = seed_ok and poly_t_ok and homopolymer_ok
        return candidate

    @property
    def name(self) -> str:
        return "OffTargetFilter"
