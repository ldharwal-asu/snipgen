"""Compose and run multiple filters, returning passed and rejected candidates."""

import logging

from snipgen.filters.base_filter import BaseFilter
from snipgen.models.grna_candidate import GRNACandidate

logger = logging.getLogger("snipgen.filters.filter_chain")


class FilterChain:
    """Apply a sequence of filters to all candidates, then separate pass/fail.

    Each filter annotates candidates in-place. Separation into passed/rejected
    lists happens after all filters have run so every candidate has a complete
    set of per-filter verdicts.
    """

    def __init__(self, filters: list[BaseFilter]):
        self.filters = filters

    def run(
        self, candidates: list[GRNACandidate]
    ) -> tuple[list[GRNACandidate], list[GRNACandidate]]:
        """Annotate all candidates and return (passed, rejected).

        Passed candidates have gc_pass, pam_pass, and offtarget_pass all True.
        Rejected candidates are retained for audit output.
        """
        for filt in self.filters:
            for candidate in candidates:
                filt.apply(candidate)

        passed = [c for c in candidates if c.passes_all_filters()]
        rejected = [c for c in candidates if not c.passes_all_filters()]

        logger.info(
            "FilterChain: %d passed, %d rejected (total: %d)",
            len(passed), len(rejected), len(candidates)
        )
        return passed, rejected

    def filter_summary(self, candidates: list[GRNACandidate]) -> dict[str, int]:
        """Return per-filter rejection counts after running the chain."""
        return {
            "gc_fail":         sum(1 for c in candidates if not c.gc_pass),
            "pam_fail":        sum(1 for c in candidates if not c.pam_pass),
            "offtarget_fail":  sum(1 for c in candidates if not c.offtarget_pass),
        }
