"""Extract gRNA candidate windows from cleaned sequences."""

import logging

from snipgen.models.grna_candidate import GRNACandidate
from snipgen.preprocessing.sequence_cleaner import CleanedSequence
from snipgen.utils.nucleotide import gc_content, reverse_complement

logger = logging.getLogger("snipgen.preprocessing.window_extractor")


class WindowExtractor:
    """Slide a window across both strands to extract gRNA candidates.

    For each position on the forward strand (and the reverse complement),
    extract guide_length nucleotides as the spacer and pam_length nucleotides
    as the raw PAM window.

    PAM position:
    - '3prime': PAM follows the spacer (SpCas9, SaCas9, xCas9)
    - '5prime': PAM precedes the spacer (Cpf1/Cas12a)
    """

    def __init__(
        self,
        guide_length: int = 20,
        pam_length: int = 3,
        pam_position: str = "3prime",
    ):
        self.guide_length = guide_length
        self.pam_length = pam_length
        self.pam_position = pam_position

    def extract(self, cleaned: CleanedSequence) -> list[GRNACandidate]:
        seq = cleaned.sequence
        candidates: list[GRNACandidate] = []

        for strand, scan_seq in [("+", seq), ("-", reverse_complement(seq))]:
            new = self._extract_from_strand(
                scan_seq=scan_seq,
                original_seq=seq,
                record_id=cleaned.record_id,
                strand=strand,
            )
            candidates.extend(new)

        logger.debug(
            "Extracted %d raw candidates from '%s'", len(candidates), cleaned.record_id
        )
        return candidates

    def _extract_from_strand(
        self,
        scan_seq: str,
        original_seq: str,
        record_id: str,
        strand: str,
    ) -> list[GRNACandidate]:
        seq_len = len(scan_seq)
        candidates: list[GRNACandidate] = []

        if self.pam_position == "3prime":
            window_size = self.guide_length + self.pam_length
            for i in range(seq_len - window_size + 1):
                spacer = scan_seq[i: i + self.guide_length]
                pam = scan_seq[i + self.guide_length: i + window_size]

                # Skip windows containing N (from masked regions)
                if "N" in spacer:
                    continue

                start, end = self._coords(i, i + self.guide_length, seq_len, strand, original_seq)
                candidates.append(GRNACandidate(
                    sequence=spacer,
                    pam=pam,
                    chromosome=record_id,
                    start=start,
                    end=end,
                    strand=strand,
                    gc_content=gc_content(spacer),
                ))
        else:  # 5prime PAM (Cpf1/Cas12a)
            window_size = self.pam_length + self.guide_length
            for i in range(seq_len - window_size + 1):
                pam = scan_seq[i: i + self.pam_length]
                spacer = scan_seq[i + self.pam_length: i + window_size]

                if "N" in spacer:
                    continue

                start, end = self._coords(
                    i + self.pam_length, i + window_size, seq_len, strand, original_seq
                )
                candidates.append(GRNACandidate(
                    sequence=spacer,
                    pam=pam,
                    chromosome=record_id,
                    start=start,
                    end=end,
                    strand=strand,
                    gc_content=gc_content(spacer),
                ))

        return candidates

    @staticmethod
    def _coords(
        scan_start: int, scan_end: int, seq_len: int, strand: str, original_seq: str
    ) -> tuple[int, int]:
        """Convert scan-strand coordinates back to original (+ strand) coordinates."""
        if strand == "+":
            return scan_start, scan_end
        else:
            # On the minus strand, the scan is on the reverse complement.
            # Convert back: original_start = seq_len - scan_end
            return seq_len - scan_end, seq_len - scan_start
