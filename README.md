# SnipGen

AI-driven CRISPR guide RNA design platform.

## Features

- Parse FASTA sequences (BioPython, generator-based for large genomes)
- Rule-based filters: GC content (40–70%), PAM site detection, off-target heuristics
- Support for multiple Cas variants: SpCas9, SaCas9, Cpf1/Cas12a, xCas9
- Deterministic scoring + ML scoring hook (plug in any sklearn/torch model)
- Output: ranked CSV + JSON with full audit trail of rejected candidates

## Installation

```bash
pip install biopython
pip install -e ".[dev]"
```

## Usage

```bash
# Design gRNAs from a FASTA file
snipgen design --input target.fasta --output-dir results/

# With custom options
snipgen design --input target.fasta \
               --output-dir results/ \
               --format csv json \
               --cas-variant SpCas9 \
               --guide-length 20 \
               --min-gc 0.40 \
               --max-gc 0.70 \
               --top-n 20 \
               --verbose

# Validate input only (no output files)
snipgen validate --input target.fasta

# List supported Cas variants
snipgen list-variants
```

## ML Model Integration

Drop in a trained sklearn model (joblib-serialized):

```bash
snipgen design --input target.fasta --ml-model model.joblib --ml-weight 0.4
```

The model receives an 84-dimensional feature vector per candidate (20-pos one-hot + 4 scalar features).
