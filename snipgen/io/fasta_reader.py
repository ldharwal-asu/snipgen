"""FASTA file parsing via BioPython with validation."""

import logging
from pathlib import Path
from typing import Iterator

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

from snipgen.utils.nucleotide import is_valid_dna

logger = logging.getLogger("snipgen.io.fasta_reader")


class FastaReader:
    """Generator-based FASTA reader with per-record validation.

    Keeps memory constant regardless of input file size by yielding one
    SeqRecord at a time.
    """

    def __init__(self, path: str | Path, min_length: int = 23):
        self.path = Path(path)
        self.min_length = min_length
        self._record_count: int | None = None

        if not self.path.exists():
            raise FileNotFoundError(f"FASTA file not found: {self.path}")

    def __iter__(self) -> Iterator[SeqRecord]:
        seen = 0
        skipped = 0
        with open(self.path) as fh:
            for record in SeqIO.parse(fh, "fasta"):
                seq_str = str(record.seq).upper()

                if len(seq_str) < self.min_length:
                    logger.warning(
                        "Skipping record '%s': length %d < min %d",
                        record.id, len(seq_str), self.min_length
                    )
                    skipped += 1
                    continue

                if not is_valid_dna(seq_str):
                    # Warn but still yield — cleaner will handle ambiguous chars
                    logger.warning(
                        "Record '%s' contains non-ACGTN characters — will be cleaned",
                        record.id
                    )

                seen += 1
                yield record

        self._record_count = seen
        if skipped:
            logger.info("Skipped %d records (too short)", skipped)

    def record_count(self) -> int:
        """Return the number of valid records yielded. Requires at least one iteration."""
        if self._record_count is None:
            # Consume the iterator to count
            for _ in self:
                pass
        return self._record_count  # type: ignore[return-value]
