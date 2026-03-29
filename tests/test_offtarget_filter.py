"""Tests for off-target heuristic filter."""

import pytest
from snipgen.filters.offtarget_filter import OffTargetFilter
from snipgen.models.grna_candidate import GRNACandidate


def _candidate(seq: str) -> GRNACandidate:
    from snipgen.utils.nucleotide import gc_content
    return GRNACandidate(
        sequence=seq, pam="AGG", chromosome="chr1",
        start=0, end=len(seq), strand="+", gc_content=gc_content(seq)
    )


def test_clean_sequence_passes():
    f = OffTargetFilter()
    c = _candidate("GCATCGATCGATCGATCGAT")
    f.apply(c)
    assert c.offtarget_pass is True


def test_poly_t_rejected():
    f = OffTargetFilter()
    c = _candidate("GCATCGATCGATCTTTTGAT")
    f.apply(c)
    assert c.has_poly_t is True
    assert c.offtarget_pass is False


def test_homopolymer_rejected():
    f = OffTargetFilter()
    c = _candidate("GCATCGATCGATCAAAAGAT")
    f.apply(c)
    assert c.has_homopolymer is True
    assert c.offtarget_pass is False


def test_high_seed_gc_rejected():
    # Last 12 nt all GC → seed_gc = 1.0 > 0.75
    f = OffTargetFilter()
    c = _candidate("ATATATATGGCCGGCCGGCC")
    f.apply(c)
    assert c.seed_gc > 0.75
    assert c.offtarget_pass is False


def test_seed_gc_computed():
    f = OffTargetFilter(seed_length=12)
    c = _candidate("GCATCGATCGATCGATCGAT")
    f.apply(c)
    assert 0.0 <= c.seed_gc <= 1.0
