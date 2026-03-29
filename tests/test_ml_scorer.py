"""Tests for ML scorer hook."""

import pytest
from snipgen.scoring.ml_scorer import PassthroughMLScorer, MLScorerProtocol, load_ml_scorer
from snipgen.models.grna_candidate import GRNACandidate


def _candidate() -> GRNACandidate:
    return GRNACandidate(
        sequence="GCATCGATCGATCGATCGAT", pam="AGG", chromosome="chr1",
        start=0, end=20, strand="+", gc_content=0.45
    )


def test_passthrough_returns_half():
    scorer = PassthroughMLScorer()
    candidates = [_candidate() for _ in range(5)]
    scores = scorer.score(candidates)
    assert all(s == 0.5 for s in scores)
    assert len(scores) == 5


def test_passthrough_not_available():
    assert PassthroughMLScorer().is_available() is False


def test_passthrough_satisfies_protocol():
    scorer = PassthroughMLScorer()
    assert isinstance(scorer, MLScorerProtocol)


def test_passthrough_empty_input():
    scorer = PassthroughMLScorer()
    assert scorer.score([]) == []


def test_load_ml_scorer_no_path():
    scorer = load_ml_scorer(None)
    assert isinstance(scorer, PassthroughMLScorer)


def test_load_ml_scorer_bad_path(tmp_path):
    scorer = load_ml_scorer(str(tmp_path / "nonexistent.joblib"))
    # Should fall back to passthrough
    assert isinstance(scorer, PassthroughMLScorer)
