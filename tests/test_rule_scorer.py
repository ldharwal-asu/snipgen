"""Tests for rule-based scorer."""

import pytest
from snipgen.scoring.rule_scorer import RuleScorer
from snipgen.models.grna_candidate import GRNACandidate


def _candidate(seq: str, seed_gc: float = 0.4, poly_t: bool = False, homo: bool = False) -> GRNACandidate:
    from snipgen.utils.nucleotide import gc_content
    c = GRNACandidate(
        sequence=seq, pam="AGG", chromosome="chr1",
        start=0, end=len(seq), strand="+", gc_content=gc_content(seq)
    )
    c.seed_gc = seed_gc
    c.has_poly_t = poly_t
    c.has_homopolymer = homo
    return c


def test_score_in_range():
    scorer = RuleScorer()
    c = _candidate("GCATCGATCGATCGATCGAT")
    score = scorer.score(c)
    assert 0.0 <= score <= 1.0


def test_perfect_candidate_scores_high():
    # G at pos 1, ~50% GC, low seed GC, no poly-T, no homopolymer
    scorer = RuleScorer()
    c = _candidate("GCATCGATCGATCGATCGAT", seed_gc=0.3)
    score = scorer.score(c)
    assert score > 0.6


def test_poly_t_penalizes():
    scorer = RuleScorer()
    good = _candidate("GCATCGATCGATCGATCGAT", poly_t=False)
    bad  = _candidate("GCATCGATCGATCGATCGAT", poly_t=True)
    assert scorer.score(good) > scorer.score(bad)


def test_homopolymer_penalizes():
    scorer = RuleScorer()
    good = _candidate("GCATCGATCGATCGATCGAT", homo=False)
    bad  = _candidate("GCATCGATCGATCGATCGAT", homo=True)
    assert scorer.score(good) > scorer.score(bad)


def test_weights_sum_to_one():
    s = RuleScorer
    total = s._GC_WEIGHT + s._SEED_WEIGHT + s._G1_WEIGHT + s._HOMO_WEIGHT + s._POLYT_WEIGHT
    assert abs(total - 1.0) < 1e-9
