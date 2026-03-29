"""GC content filter for gRNA candidates."""

from snipgen.filters.base_filter import BaseFilter
from snipgen.models.grna_candidate import GRNACandidate


class GCFilter(BaseFilter):
    """Reject candidates whose GC content falls outside [min_gc, max_gc].

    Thresholds based on Doench 2016 and Moreno-Mateos 2015:
    - Below 40%: gRNA–DNA duplex thermodynamically unstable (low Tm)
    - Above 70%: secondary structures form in the gRNA scaffold
    """

    def __init__(self, min_gc: float = 0.40, max_gc: float = 0.70):
        self.min_gc = min_gc
        self.max_gc = max_gc

    def apply(self, candidate: GRNACandidate) -> GRNACandidate:
        candidate.gc_pass = self.min_gc <= candidate.gc_content <= self.max_gc
        return candidate

    @property
    def name(self) -> str:
        return f"GCFilter({self.min_gc:.0%}–{self.max_gc:.0%})"
