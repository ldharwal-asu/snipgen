"""Abstract base class for all gRNA candidate filters."""

from abc import ABC, abstractmethod

from snipgen.models.grna_candidate import GRNACandidate


class BaseFilter(ABC):
    """Filters annotate candidates with pass/fail flags — they never discard.

    Discarding happens in FilterChain after all filters have run.
    This preserves a complete audit trail for every candidate considered.
    """

    @abstractmethod
    def apply(self, candidate: GRNACandidate) -> GRNACandidate:
        """Annotate the candidate in-place and return it."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable filter name for logging and reporting."""
        ...
