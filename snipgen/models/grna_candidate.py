from dataclasses import dataclass, field


@dataclass
class GRNACandidate:
    """Central data contract for a single gRNA candidate throughout the pipeline."""

    # Core sequence info
    sequence: str       # 20-nt spacer (5'→3')
    pam: str            # PAM sequence immediately 3' of spacer (or 5' for Cpf1)
    chromosome: str     # Source sequence ID from FASTA header
    start: int          # 0-based start on source strand
    end: int            # 0-based end (exclusive)
    strand: str         # '+' or '-'
    gc_content: float   # Fraction [0.0–1.0] of G+C in spacer

    # Filter pass/fail flags (set by filter modules)
    gc_pass: bool = False
    pam_pass: bool = False
    offtarget_pass: bool = False

    # Off-target heuristic detail (set by OffTargetFilter)
    seed_gc: float = 0.0        # GC fraction in seed region (last 12 nt proximal to PAM)
    has_poly_t: bool = False     # True if TTTT present (Pol-III termination signal)
    has_homopolymer: bool = False  # True if any 4+ run of identical nucleotides

    # Scores (set by scoring modules)
    rule_score: float = 0.0
    ml_score: float = 0.5
    final_score: float = 0.0

    def passes_all_filters(self) -> bool:
        return self.gc_pass and self.pam_pass and self.offtarget_pass

    def to_dict(self) -> dict:
        return {
            "sequence": self.sequence,
            "pam": self.pam,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "strand": self.strand,
            "gc_content": round(self.gc_content, 4),
            "seed_gc": round(self.seed_gc, 4),
            "has_poly_t": self.has_poly_t,
            "has_homopolymer": self.has_homopolymer,
            "gc_pass": self.gc_pass,
            "pam_pass": self.pam_pass,
            "offtarget_pass": self.offtarget_pass,
            "rule_score": round(self.rule_score, 4),
            "ml_score": round(self.ml_score, 4),
            "final_score": round(self.final_score, 4),
        }
