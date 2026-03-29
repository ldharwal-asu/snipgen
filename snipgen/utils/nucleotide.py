"""Pure nucleotide utility functions — no external state or side effects."""

import re
from itertools import product

# IUPAC ambiguity code expansion map
IUPAC_MAP: dict[str, list[str]] = {
    "A": ["A"],
    "C": ["C"],
    "G": ["G"],
    "T": ["T"],
    "R": ["A", "G"],
    "Y": ["C", "T"],
    "S": ["G", "C"],
    "W": ["A", "T"],
    "K": ["G", "T"],
    "M": ["A", "C"],
    "B": ["C", "G", "T"],
    "D": ["A", "G", "T"],
    "H": ["A", "C", "T"],
    "V": ["A", "C", "G"],
    "N": ["A", "C", "G", "T"],
}

_COMPLEMENT: dict[str, str] = str.maketrans("ACGTacgt", "TGCAtgca")


def reverse_complement(seq: str) -> str:
    """Return the reverse complement of a DNA sequence."""
    return seq.translate(_COMPLEMENT)[::-1]


def gc_content(seq: str) -> float:
    """Return GC fraction [0.0–1.0] of a DNA sequence. Returns 0.0 for empty."""
    if not seq:
        return 0.0
    seq = seq.upper()
    return (seq.count("G") + seq.count("C")) / len(seq)


def expand_iupac(pattern: str) -> list[str]:
    """Expand an IUPAC ambiguity pattern into all matching concrete sequences.

    Example: 'NGG' -> ['AGG', 'CGG', 'GGG', 'TGG']
    """
    pattern = pattern.upper()
    choices = [IUPAC_MAP.get(base, [base]) for base in pattern]
    return ["".join(combo) for combo in product(*choices)]


def has_homopolymer(seq: str, min_run: int = 4) -> bool:
    """Return True if any single nucleotide repeats min_run or more times consecutively."""
    return bool(re.search(rf"(.)\1{{{min_run - 1},}}", seq.upper()))


def has_poly_t(seq: str, min_run: int = 4) -> bool:
    """Return True if sequence contains a run of T's of at least min_run length."""
    return "T" * min_run in seq.upper()


def is_valid_dna(seq: str) -> bool:
    """Return True if sequence contains only ACGTN characters."""
    return bool(re.fullmatch(r"[ACGTNacgtn]+", seq))
