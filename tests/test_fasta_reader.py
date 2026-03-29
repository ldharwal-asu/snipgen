"""Tests for FASTA reader."""

import pytest
from pathlib import Path

from snipgen.io.fasta_reader import FastaReader

FIXTURES = Path(__file__).parent / "fixtures"


def test_reads_valid_fasta():
    reader = FastaReader(FIXTURES / "sample_target.fasta")
    records = list(reader)
    assert len(records) == 3
    for r in records:
        assert len(str(r.seq)) >= 23


def test_raises_on_missing_file():
    with pytest.raises(FileNotFoundError):
        FastaReader("/nonexistent/path.fasta")


def test_skips_short_sequences(tmp_path):
    fasta = tmp_path / "short.fasta"
    fasta.write_text(">short\nACGT\n>ok\n" + "A" * 30 + "\n")
    reader = FastaReader(fasta, min_length=23)
    records = list(reader)
    assert len(records) == 1
    assert records[0].id == "ok"


def test_record_ids_preserved():
    reader = FastaReader(FIXTURES / "sample_target.fasta")
    ids = [r.id for r in reader]
    assert "seq1" in ids
    assert "seq2" in ids
    assert "seq3" in ids
