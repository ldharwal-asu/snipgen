"""FASTA file parsing via BioPython with validation, gzip support, and sequence stats."""

import gzip
import logging
from pathlib import Path
from typing import Iterator

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

from snipgen.utils.nucleotide import gc_content, is_valid_dna

logger = logging.getLogger("snipgen.io.fasta_reader")


class FastaReader:
    """Generator-based FASTA reader.

    Supports plain (.fasta/.fa/.fna) and gzip-compressed files (.gz).
    Memory stays constant regardless of file size — yields one SeqRecord at a time.
    """

    def __init__(self, path: str | Path, min_length: int = 23):
        self.path = Path(path)
        self.min_length = min_length
        self._record_count: int | None = None
        self.sequence_stats: list[dict] = []

        if not self.path.exists():
            raise FileNotFoundError(f"FASTA file not found: {self.path}")

    def _open(self):
        """Return an open file handle, handling gzip transparently."""
        if self.path.suffix.lower() == ".gz":
            return gzip.open(self.path, "rt")
        return open(self.path)

    def __iter__(self) -> Iterator[SeqRecord]:
        seen = 0
        skipped = 0
        self.sequence_stats = []

        with self._open() as fh:
            for record in SeqIO.parse(fh, "fasta"):
                seq_str = str(record.seq).upper()

                if len(seq_str) < self.min_length:
                    logger.warning(
                        "Skipping '%s': length %d < min %d",
                        record.id, len(seq_str), self.min_length,
                    )
                    skipped += 1
                    continue

                if not is_valid_dna(seq_str):
                    logger.warning(
                        "Record '%s' contains non-ACGTN characters — will be cleaned",
                        record.id,
                    )

                n_count = seq_str.count("N")
                self.sequence_stats.append({
                    "id": record.id,
                    "length": len(seq_str),
                    "gc_content": round(gc_content(seq_str), 4),
                    "n_count": n_count,
                    "n_fraction": round(n_count / max(len(seq_str), 1), 4),
                })

                seen += 1
                yield record

        self._record_count = seen
        if skipped:
            logger.info("Skipped %d records (too short)", skipped)
        logger.info("Parsed %d valid FASTA records", seen)

    def record_count(self) -> int:
        if self._record_count is None:
            for _ in self:
                pass
        return self._record_count  # type: ignore[return-value]
