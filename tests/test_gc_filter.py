"""Tests for GC content filter."""

import pytest
from snipgen.filters.gc_filter import GCFilter
from snipgen.models.grna_candidate import GRNACandidate


def _candidate(gc: float) -> GRNACandidate:
    return GRNACandidate(
        sequence="A" * 20, pam="NGG", chromosome="chr1",
        start=0, end=20, strand="+", gc_content=gc
    )


@pytest.mark.parametrize("gc,expected", [
    (0.39, False),
    (0.40, True),
    (0.55, True),
    (0.70, True),
    (0.71, False),
])
def test_gc_filter_boundaries(gc, expected):
    f = GCFilter(min_gc=0.40, max_gc=0.70)
    c = _candidate(gc)
    f.apply(c)
    assert c.gc_pass is expected


def test_custom_thresholds():
    f = GCFilter(min_gc=0.50, max_gc=0.60)
    c = _candidate(0.45)
    f.apply(c)
    assert c.gc_pass is False

    c2 = _candidate(0.55)
    f.apply(c2)
    assert c2.gc_pass is True


def test_filter_name():
    f = GCFilter()
    assert "GCFilter" in f.name
