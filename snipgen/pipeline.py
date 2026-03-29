"""SnipGen pipeline orchestrator.

PipelineConfig is a plain dataclass fully decoupled from the CLI,
making the pipeline unit-testable without invoking Click.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from snipgen.filters.filter_chain import FilterChain
from snipgen.filters.gc_filter import GCFilter
from snipgen.filters.offtarget_filter import OffTargetFilter
from snipgen.filters.pam_filter import PAMFilter
from snipgen.io.fasta_reader import FastaReader
from snipgen.io.output_writer import OutputWriter
from snipgen.models.grna_candidate import GRNACandidate
from snipgen.preprocessing.sequence_cleaner import SequenceCleaner
from snipgen.preprocessing.window_extractor import WindowExtractor
from snipgen.scoring.composite_scorer import CompositeScorer
from snipgen.scoring.ml_scorer import load_ml_scorer
from snipgen.scoring.rule_scorer import RuleScorer

logger = logging.getLogger("snipgen.pipeline")


@dataclass
class PipelineConfig:
    fasta_path: str | Path
    output_dir: str | Path = "results"
    output_formats: list[str] = field(default_factory=lambda: ["csv", "json"])
    cas_variant: str = "SpCas9"
    guide_length: int = 20
    min_gc: float = 0.40
    max_gc: float = 0.70
    top_n: int = 20
    ml_model_path: str | None = None
    rule_weight: float = 1.0
    ml_weight: float = 0.0
    max_n_fraction: float = 0.05
    mask_homopolymer_run: int | None = 10
    seed_length: int = 12
    max_seed_gc: float = 0.75


@dataclass
class PipelineResult:
    top_candidates: list[GRNACandidate]
    rejected: list[GRNACandidate]
    stats: dict
    written_files: dict[str, Path] = field(default_factory=dict)


class SnipGenPipeline:
    """Wire all stages together and run the full gRNA design pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config

        from snipgen.filters.pam_filter import PAM_REGISTRY
        pam_cfg = PAM_REGISTRY[config.cas_variant]
        pam_pos = pam_cfg["position"]
        pam_len = pam_cfg["length"]

        self.reader = FastaReader(config.fasta_path)
        self.cleaner = SequenceCleaner(
            max_n_fraction=config.max_n_fraction,
            mask_homopolymer_run=config.mask_homopolymer_run,
        )
        self.extractor = WindowExtractor(
            guide_length=config.guide_length,
            pam_length=pam_len,
            pam_position=pam_pos,
        )
        self.filter_chain = FilterChain([
            GCFilter(config.min_gc, config.max_gc),
            PAMFilter(config.cas_variant),
            OffTargetFilter(
                seed_length=config.seed_length,
                max_seed_gc=config.max_seed_gc,
            ),
        ])
        ml_scorer = load_ml_scorer(config.ml_model_path)
        self.scorer = CompositeScorer(
            RuleScorer(), ml_scorer,
            rule_weight=config.rule_weight,
            ml_weight=config.ml_weight,
        )
        self.writer = OutputWriter(config.output_dir, config.output_formats)

    def run(self) -> PipelineResult:
        all_candidates: list[GRNACandidate] = []

        for record in self.reader:
            cleaned = self.cleaner.clean(record)
            candidates = self.extractor.extract(cleaned)
            all_candidates.extend(candidates)

        logger.info("Total raw candidates extracted: %d", len(all_candidates))

        passed, rejected = self.filter_chain.run(all_candidates)
        scored = self.scorer.score_all(passed)
        ranked = sorted(scored, key=lambda c: c.final_score, reverse=True)
        top_n = ranked[: self.config.top_n]

        stats = self._compute_stats(all_candidates, passed, top_n)

        metadata = {
            "cas_variant": self.config.cas_variant,
            "guide_length": self.config.guide_length,
            "min_gc": self.config.min_gc,
            "max_gc": self.config.max_gc,
            "top_n_requested": self.config.top_n,
            **stats,
        }
        written = self.writer.write(top_n, rejected, metadata=metadata)

        return PipelineResult(
            top_candidates=top_n,
            rejected=rejected,
            stats=stats,
            written_files=written,
        )

    @staticmethod
    def _compute_stats(
        all_candidates: list[GRNACandidate],
        passed: list[GRNACandidate],
        top_n: list[GRNACandidate],
    ) -> dict:
        total = len(all_candidates)
        n_passed = len(passed)
        return {
            "total_candidates_evaluated": total,
            "candidates_passed_filters": n_passed,
            "candidates_rejected": total - n_passed,
            "pass_rate": round(n_passed / total, 4) if total else 0.0,
            "top_n_returned": len(top_n),
        }
