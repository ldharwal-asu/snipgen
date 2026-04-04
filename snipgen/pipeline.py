"""SnipGen v2 pipeline orchestrator."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from snipgen.filters.deduplicator import deduplicate_guides
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
    dedup_window: int = 10
    scoring_weights: dict | None = None


@dataclass
class PipelineResult:
    top_candidates: list[GRNACandidate]
    rejected: list[GRNACandidate]
    stats: dict
    written_files: dict[str, Path] = field(default_factory=dict)


class SnipGenPipeline:
    """Wire all stages together and run the full v2 gRNA design pipeline."""

    def __init__(self, config: PipelineConfig):
        self.config = config

        from snipgen.filters.pam_filter import PAM_REGISTRY
        pam_cfg = PAM_REGISTRY[config.cas_variant]

        self.reader = FastaReader(config.fasta_path)
        self.cleaner = SequenceCleaner(
            max_n_fraction=config.max_n_fraction,
            mask_homopolymer_run=config.mask_homopolymer_run,
        )
        self.extractor = WindowExtractor(
            guide_length=config.guide_length,
            pam_length=pam_cfg["length"],
            pam_position=pam_cfg["position"],
        )
        self.filter_chain = FilterChain([
            GCFilter(config.min_gc, config.max_gc),
            PAMFilter(config.cas_variant),
            OffTargetFilter(
                seed_length=config.seed_length,
                max_seed_gc=config.max_seed_gc,
            ),
        ])
        self.scorer = CompositeScorer(weights=config.scoring_weights)
        self.writer = OutputWriter(config.output_dir, config.output_formats)

    def run(self) -> PipelineResult:
        all_candidates: list[GRNACandidate] = []
        full_sequences: dict[str, str] = {}

        for record in self.reader:
            cleaned = self.cleaner.clean(record)
            full_sequences[record.id] = str(cleaned.sequence).upper()
            candidates = self.extractor.extract(cleaned)
            all_candidates.extend(candidates)

        logger.info("Total raw candidates extracted: %d", len(all_candidates))

        # Filter
        passed, rejected = self.filter_chain.run(all_candidates)

        # Position-aware deduplication
        deduped, dedup_removed = deduplicate_guides(passed, window=self.config.dedup_window)
        rejected.extend(dedup_removed)
        logger.info(
            "Deduplication: %d → %d (removed %d positional duplicates)",
            len(passed), len(deduped), len(dedup_removed),
        )

        # V2 multi-dimensional scoring
        scored = self.scorer.score_all(deduped, full_sequences=full_sequences)
        ranked = sorted(scored, key=lambda c: c.final_score, reverse=True)
        top_n = ranked[: self.config.top_n]

        # Annotate with rank IDs
        for i, c in enumerate(top_n, 1):
            c.score_breakdown["rank"] = i
            c.score_breakdown["guide_id"] = f"SG-{i:03d}"

        stats = self._compute_stats(all_candidates, passed, deduped, top_n)

        metadata = {
            "snipgen_version": "0.2.0",
            "cas_variant": self.config.cas_variant,
            "guide_length": self.config.guide_length,
            "min_gc": self.config.min_gc,
            "max_gc": self.config.max_gc,
            "top_n_requested": self.config.top_n,
            "sequence_stats": self.reader.sequence_stats,
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
        passed_filters: list[GRNACandidate],
        after_dedup: list[GRNACandidate],
        top_n: list[GRNACandidate],
    ) -> dict:
        total = len(all_candidates)
        n_passed = len(passed_filters)

        safety_dist: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "AVOID": 0}
        for c in after_dedup:
            safety_dist[c.safety_label] = safety_dist.get(c.safety_label, 0) + 1

        return {
            "total_candidates_evaluated": total,
            "candidates_passed_filters": n_passed,
            "candidates_rejected": total - n_passed,
            "candidates_after_dedup": len(after_dedup),
            "pass_rate": round(n_passed / total, 4) if total else 0.0,
            "top_n_returned": len(top_n),
            "safety_distribution": safety_dist,
        }
