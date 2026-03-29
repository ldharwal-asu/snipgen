"""Tests for Click CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from snipgen.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def test_design_command(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, [
        "design",
        "--input", str(FIXTURES / "sample_target.fasta"),
        "--output-dir", str(tmp_path / "out"),
        "--top-n", "5",
    ])
    assert result.exit_code == 0, result.output
    assert "SnipGen Results" in result.output


def test_validate_command():
    runner = CliRunner()
    result = runner.invoke(main, [
        "validate",
        "--input", str(FIXTURES / "sample_target.fasta"),
    ])
    assert result.exit_code == 0
    assert "Records:" in result.output


def test_list_variants_command():
    runner = CliRunner()
    result = runner.invoke(main, ["list-variants"])
    assert result.exit_code == 0
    assert "SpCas9" in result.output
    assert "Cpf1" in result.output


def test_design_missing_input():
    runner = CliRunner()
    result = runner.invoke(main, [
        "design",
        "--input", "/nonexistent/file.fasta",
    ])
    assert result.exit_code != 0


def test_design_csv_only(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, [
        "design",
        "--input", str(FIXTURES / "sample_target.fasta"),
        "--output-dir", str(tmp_path / "out"),
        "--format", "csv",
    ])
    assert result.exit_code == 0
    assert (tmp_path / "out" / "candidates.csv").exists()
    assert not (tmp_path / "out" / "candidates.json").exists()
