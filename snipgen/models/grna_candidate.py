from dataclasses import dataclass, field


@dataclass
class GRNACandidate:
    """Central data contract for a single gRNA candidate (SnipGen v2)."""

    # Core sequence info
    sequence: str
    pam: str
    chromosome: str
    start: int
    end: int
    strand: str
    gc_content: float

    # Filter pass/fail flags
    gc_pass: bool = False
    pam_pass: bool = False
    offtarget_pass: bool = False

    # Off-target heuristic detail (set by OffTargetFilter)
    seed_gc: float = 0.0
    has_poly_t: bool = False
    has_homopolymer: bool = False

    # V1 scores (kept for backward compat)
    rule_score: float = 0.0
    ml_score: float = 0.5
    final_score: float = 0.0  # composite 0-100 in v2

    # V2 multi-dimensional scores (0-100 scale)
    on_target_score: float = 0.0
    off_target_score: float = 100.0
    consequence_score: float = 100.0
    confidence_score: float = 50.0

    # Safety classification
    safety_label: str = "MEDIUM"   # HIGH / MEDIUM / LOW / AVOID
    safety_color: str = "yellow"   # green / yellow / orange / red

    # Off-target detail counts (Tier 1 within-sequence)
    off_targets_1mm: int = 0
    off_targets_2mm: int = 0
    off_targets_3mm: int = 0
    off_target_burden_raw: float = 0.0

    # Natural language recommendation
    recommendation: str = ""

    # Structured rejection codes (e.g. GC_LOW, DUPLICATE, PAM_MISSING)
    rejection_codes: list = field(default_factory=list)

    # Score breakdown dict (populated by scorers for explainability)
    score_breakdown: dict = field(default_factory=dict)

    def passes_all_filters(self) -> bool:
        return self.gc_pass and self.pam_pass and self.offtarget_pass

    def to_dict(self) -> dict:
        return {
            # Core
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
            # Filter flags
            "gc_pass": self.gc_pass,
            "pam_pass": self.pam_pass,
            "offtarget_pass": self.offtarget_pass,
            # V1 compat
            "rule_score": round(self.rule_score, 4),
            "ml_score": round(self.ml_score, 4),
            # V2 scores (0-100)
            "final_score": round(self.final_score, 1),
            "on_target_score": round(self.on_target_score, 1),
            "off_target_score": round(self.off_target_score, 1),
            "consequence_score": round(self.consequence_score, 1),
            "confidence_score": round(self.confidence_score, 1),
            # Safety
            "safety_label": self.safety_label,
            "safety_color": self.safety_color,
            # Off-target detail
            "off_targets_1mm": self.off_targets_1mm,
            "off_targets_2mm": self.off_targets_2mm,
            "off_targets_3mm": self.off_targets_3mm,
            "off_target_burden_raw": round(self.off_target_burden_raw, 2),
            # Explainability
            "recommendation": self.recommendation,
            "rejection_codes": self.rejection_codes,
            "score_breakdown": self.score_breakdown,
        }
