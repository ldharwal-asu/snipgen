"""Tests for PAM filter."""

import pytest
from snipgen.filters.pam_filter import PAMFilter, PAM_REGISTRY
from snipgen.models.grna_candidate import GRNACandidate


def _candidate(pam: str) -> GRNACandidate:
    return GRNACandidate(
        sequence="GCATCGATCGATCGATCGAT", pam=pam, chromosome="chr1",
        start=0, end=20, strand="+", gc_content=0.45
    )


@pytest.mark.parametrize("pam,expected", [
    ("AGG", True),
    ("CGG", True),
    ("GGG", True),
    ("TGG", True),
    ("ACC", False),
    ("ATT", False),
    ("NCC", False),
])
def test_spcas9_pam(pam, expected):
    f = PAMFilter("SpCas9")
    c = _candidate(pam)
    f.apply(c)
    assert c.pam_pass is expected


def test_unknown_variant_raises():
    with pytest.raises(ValueError, match="Unknown Cas variant"):
        PAMFilter("UnknownCas")


def test_all_registry_variants_instantiate():
    for variant in PAM_REGISTRY:
        f = PAMFilter(variant)
        assert f.name  # just check it instantiates cleanly


def test_pam_filter_name():
    f = PAMFilter("SpCas9")
    assert "SpCas9" in f.name
