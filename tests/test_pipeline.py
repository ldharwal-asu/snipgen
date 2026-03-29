"""End-to-end pipeline tests."""

import json
from pathlib import Path

import pytest

from snipgen.pipeline import PipelineConfig, SnipGenPipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_runs_end_to_end(tmp_path):
    config = PipelineConfig(
        fasta_path=FIXTURES / "sample_target.fasta",
        output_dir=tmp_path / "results",
        output_formats=["csv", "json"],
        top_n=10,
    )
    pipeline = SnipGenPipeline(config)
    result = pipeline.run()

    assert result.stats["total_candidates_evaluated"] > 0
    assert result.stats["top_n_returned"] <= 10
    assert len(result.top_candidates) <= 10


def test_pipeline_writes_csv(tmp_path):
    config = PipelineConfig(
        fasta_path=FIXTURES / "sample_target.fasta",
        output_dir=tmp_path / "results",
        output_formats=["csv"],
    )
    SnipGenPipeline(config).run()
    csv_path = tmp_path / "results" / "candidates.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().splitlines()
    assert len(lines) >= 1  # at least a header


def test_pipeline_writes_json(tmp_path):
    config = PipelineConfig(
        fasta_path=FIXTURES / "sample_target.fasta",
        output_dir=tmp_path / "results",
        output_formats=["json"],
    )
    SnipGenPipeline(config).run()
    json_path = tmp_path / "results" / "candidates.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "metadata" in data
    assert "candidates" in data


def test_pipeline_top_n_respected(tmp_path):
    config = PipelineConfig(
        fasta_path=FIXTURES / "sample_target.fasta",
        output_dir=tmp_path / "results",
        top_n=5,
    )
    result = SnipGenPipeline(config).run()
    assert len(result.top_candidates) <= 5


def test_pipeline_candidates_sorted_by_score(tmp_path):
    config = PipelineConfig(
        fasta_path=FIXTURES / "sample_target.fasta",
        output_dir=tmp_path / "results",
        top_n=50,
    )
    result = SnipGenPipeline(config).run()
    scores = [c.final_score for c in result.top_candidates]
    assert scores == sorted(scores, reverse=True)
