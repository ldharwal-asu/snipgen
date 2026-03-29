"""Click-based CLI for SnipGen."""

import sys

import click

from snipgen.filters.pam_filter import PAM_REGISTRY
from snipgen.pipeline import PipelineConfig, SnipGenPipeline
from snipgen.utils.logger import configure_root


@click.group()
def main():
    """SnipGen — AI-driven CRISPR guide RNA design."""


@main.command()
@click.option("--input",   "fasta_path",    required=True,  type=click.Path(exists=True), help="Input FASTA file")
@click.option("--output-dir",               default="results", show_default=True,           help="Output directory")
@click.option("--format",  "formats",       multiple=True,  default=("csv", "json"),       help="Output formats (csv, json)")
@click.option("--cas-variant",              default="SpCas9", show_default=True,            help=f"Cas variant: {', '.join(PAM_REGISTRY)}")
@click.option("--guide-length",             default=20,       show_default=True, type=int,  help="gRNA spacer length (nt)")
@click.option("--min-gc",                   default=0.40,     show_default=True, type=float,help="Minimum GC fraction")
@click.option("--max-gc",                   default=0.70,     show_default=True, type=float,help="Maximum GC fraction")
@click.option("--top-n",                    default=20,       show_default=True, type=int,  help="Number of top candidates to return")
@click.option("--ml-model",  "ml_model_path", default=None,   type=click.Path(),            help="Path to joblib ML model (optional)")
@click.option("--ml-weight",                default=0.0,      show_default=True, type=float,help="Weight for ML score (0.0 = rule-only)")
@click.option("--verbose",                  is_flag=True,     default=False,                help="Enable verbose logging")
def design(
    fasta_path, output_dir, formats, cas_variant, guide_length,
    min_gc, max_gc, top_n, ml_model_path, ml_weight, verbose
):
    """Design gRNA candidates from a FASTA input file."""
    configure_root(verbose=verbose)

    config = PipelineConfig(
        fasta_path=fasta_path,
        output_dir=output_dir,
        output_formats=list(formats),
        cas_variant=cas_variant,
        guide_length=guide_length,
        min_gc=min_gc,
        max_gc=max_gc,
        top_n=top_n,
        ml_model_path=ml_model_path,
        rule_weight=1.0,
        ml_weight=ml_weight,
    )

    try:
        pipeline = SnipGenPipeline(config)
        result = pipeline.run()
    except Exception as exc:
        click.echo(f"ERROR: {exc}", err=True)
        sys.exit(1)

    _print_summary(result)
    click.echo(f"\nOutput written to: {output_dir}/")


def _print_summary(result) -> None:
    s = result.stats
    click.echo("\n=== SnipGen Results ===")
    click.echo(f"  Candidates evaluated : {s['total_candidates_evaluated']}")
    click.echo(f"  Passed filters       : {s['candidates_passed_filters']} "
               f"({s['pass_rate']:.1%})")
    click.echo(f"  Rejected             : {s['candidates_rejected']}")
    click.echo(f"  Top-N returned       : {s['top_n_returned']}")

    if result.top_candidates:
        click.echo("\n--- Top candidates ---")
        click.echo(f"{'Rank':<5} {'Sequence':<22} {'PAM':<6} {'Score':>6}  {'GC%':>5}  {'Strand'}")
        click.echo("-" * 60)
        for i, c in enumerate(result.top_candidates[:10], 1):
            click.echo(
                f"{i:<5} {c.sequence:<22} {c.pam:<6} {c.final_score:>6.3f}  "
                f"{c.gc_content:>5.1%}  {c.strand}"
            )
        if len(result.top_candidates) > 10:
            click.echo(f"  ... and {len(result.top_candidates) - 10} more (see output files)")


@main.command()
@click.option("--input", "fasta_path", required=True, type=click.Path(exists=True), help="Input FASTA file")
@click.option("--verbose", is_flag=True, default=False)
def validate(fasta_path, verbose):
    """Parse and validate a FASTA file without producing output files."""
    configure_root(verbose=verbose)
    from snipgen.io.fasta_reader import FastaReader
    from snipgen.preprocessing.sequence_cleaner import SequenceCleaner

    reader = FastaReader(fasta_path)
    cleaner = SequenceCleaner()
    total_records = 0
    total_nt = 0
    all_warnings: list[str] = []

    for record in reader:
        total_records += 1
        cleaned = cleaner.clean(record)
        total_nt += len(cleaned.sequence)
        all_warnings.extend(cleaned.warnings)

    click.echo(f"Records: {total_records}")
    click.echo(f"Total nucleotides: {total_nt:,}")
    if all_warnings:
        click.echo(f"Warnings ({len(all_warnings)}):")
        for w in all_warnings:
            click.echo(f"  - {w}")
    else:
        click.echo("No warnings.")


@main.command("list-variants")
def list_variants():
    """List all supported Cas variants and their PAM patterns."""
    click.echo(f"{'Variant':<12} {'PAM Pattern':<12} {'Position'}")
    click.echo("-" * 36)
    for variant, cfg in PAM_REGISTRY.items():
        click.echo(f"{variant:<12} {cfg['pattern']:<12} {cfg['position']}")
