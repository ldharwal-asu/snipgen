"""Normalize raw SeqRecord sequences into clean uppercase strings."""

import logging
import re
from typing import NamedTuple

from Bio.SeqRecord import SeqRecord

logger = logging.getLogger("snipgen.preprocessing.sequence_cleaner")

_VALID_BASES = frozenset("ACGTN")


class CleanedSequence(NamedTuple):
    record_id: str
    sequence: str
    warnings: list[str]


class SequenceCleaner:
    """Convert a BioPython SeqRecord into a clean, uppercase DNA string.

    Steps:
    1. Uppercase
    2. Warn if N fraction exceeds threshold
    3. Optionally mask low-complexity homopolymer runs
    4. Strip any characters outside ACGTN
    """

    def __init__(
        self,
        max_n_fraction: float = 0.05,
        mask_homopolymer_run: int | None = 10,
    ):
        self.max_n_fraction = max_n_fraction
        self.mask_homopolymer_run = mask_homopolymer_run

    def clean(self, record: SeqRecord) -> CleanedSequence:
        seq = str(record.seq).upper()
        warnings: list[str] = []

        # Remove whitespace
        seq = seq.replace(" ", "").replace("\n", "").replace("\r", "")

        # Strip non-ACGTN characters, replace with N
        cleaned_chars = []
        stripped = 0
        for ch in seq:
            if ch in _VALID_BASES:
                cleaned_chars.append(ch)
            else:
                cleaned_chars.append("N")
                stripped += 1
        if stripped:
            warnings.append(
                f"Replaced {stripped} non-ACGTN characters with N in '{record.id}'"
            )
        seq = "".join(cleaned_chars)

        # Check N fraction
        n_fraction = seq.count("N") / len(seq) if seq else 0.0
        if n_fraction > self.max_n_fraction:
            warnings.append(
                f"'{record.id}' has {n_fraction:.1%} N content "
                f"(threshold: {self.max_n_fraction:.1%})"
            )

        # Mask low-complexity homopolymer runs
        if self.mask_homopolymer_run is not None:
            pattern = rf"([ACGT])\1{{{self.mask_homopolymer_run - 1},}}"
            masked_count = [0]

            def _mask(m: re.Match) -> str:
                masked_count[0] += 1
                return "N" * len(m.group(0))

            seq = re.sub(pattern, _mask, seq)
            if masked_count[0]:
                warnings.append(
                    f"Masked {masked_count[0]} low-complexity homopolymer run(s) "
                    f"(≥{self.mask_homopolymer_run} nt) in '{record.id}'"
                )

        for w in warnings:
            logger.warning(w)

        return CleanedSequence(record_id=record.id, sequence=seq, warnings=warnings)
