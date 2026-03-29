"""Write ranked gRNA candidates to CSV and/or JSON."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from snipgen.models.grna_candidate import GRNACandidate

logger = logging.getLogger("snipgen.io.output_writer")

_CSV_COLUMNS = [
    "sequence", "pam", "chromosome", "start", "end", "strand",
    "gc_content", "seed_gc", "has_poly_t", "has_homopolymer",
    "gc_pass", "pam_pass", "offtarget_pass",
    "rule_score", "ml_score", "final_score",
]


class OutputWriter:
    """Writes candidate results to the specified output directory."""

    def __init__(self, output_dir: str | Path, formats: list[str] | None = None):
        self.output_dir = Path(output_dir)
        self.formats = [f.lower() for f in (formats or ["csv", "json"])]
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        candidates: list[GRNACandidate],
        rejected: list[GRNACandidate],
        metadata: dict | None = None,
    ) -> dict[str, Path]:
        """Write candidates (and rejected) to output files. Returns dict of written paths."""
        written: dict[str, Path] = {}

        if "csv" in self.formats:
            written["candidates_csv"] = self._write_csv(
                candidates, self.output_dir / "candidates.csv"
            )
            if rejected:
                written["rejected_csv"] = self._write_csv(
                    rejected, self.output_dir / "rejected_candidates.csv"
                )

        if "json" in self.formats:
            written["candidates_json"] = self._write_json(
                candidates, rejected, metadata or {}, self.output_dir / "candidates.json"
            )

        logger.info("Output written to %s", self.output_dir)
        return written

    def _write_csv(self, candidates: list[GRNACandidate], path: Path) -> Path:
        rows = [c.to_dict() for c in candidates]
        df = pd.DataFrame(rows, columns=_CSV_COLUMNS)
        df.to_csv(path, index=False)
        logger.debug("Wrote %d rows to %s", len(rows), path)
        return path

    def _write_json(
        self,
        candidates: list[GRNACandidate],
        rejected: list[GRNACandidate],
        metadata: dict,
        path: Path,
    ) -> Path:
        payload = {
            "metadata": {
                "snipgen_version": "0.1.0",
                "run_timestamp": datetime.now(timezone.utc).isoformat(),
                **metadata,
                "total_candidates_returned": len(candidates),
                "total_rejected": len(rejected),
            },
            "candidates": [c.to_dict() for c in candidates],
        }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)
        logger.debug("Wrote JSON to %s", path)
        return path
