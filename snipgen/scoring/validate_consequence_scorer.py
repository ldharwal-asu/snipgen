"""
GENCODE/hg38 validation of the consequence scorer.

Downloads:
  - hg38 chr22 FASTA  (~13 MB gzipped, UCSC)
  - GENCODE v44 GTF   (~50 MB gzipped, Ensembl), chr22 entries only

Pipeline:
  1. Parse GTF → build per-base feature map for chr22
     Categories: coding_exon (CDS), utr (UTR), intron (gene body minus exons),
                 intergenic (outside all genes)
  2. Sample 1 000 non-overlapping 20-mer windows from each category
  3. Run every window through _score_sequence()
  4. Report per-category statistics + AUROC-style separation
  5. Save results to validation_data/consequence_validation_results.tsv

Expected ordering (lower score = higher risk / more biologically sensitive):
    coding_exon  <  utr  <  intron  <  intergenic

Usage:
    python -m snipgen.scoring.validate_consequence_scorer
    # or
    python snipgen/scoring/validate_consequence_scorer.py
"""

from __future__ import annotations

import gzip
import os
import random
import statistics
import sys
import urllib.request
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent.parent.parent
DATA_DIR    = ROOT / "validation_data"
CHR22_GZ    = DATA_DIR / "chr22.fa.gz"
GTF_GZ      = DATA_DIR / "gencode.v44.chr22.gtf.gz"
RESULTS_TSV = DATA_DIR / "consequence_validation_results.tsv"

DATA_DIR.mkdir(exist_ok=True)

CHR22_URL = (
    "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr22.fa.gz"
)
# GENCODE v44 — chr22 patch-stripped GTF (much smaller than full genome GTF)
GTF_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_44/"
    "gencode.v44.annotation.gtf.gz"
)

SAMPLE_PER_CATEGORY = 1_000
GUIDE_LEN           = 20
RANDOM_SEED         = 42


# ── download helper ────────────────────────────────────────────────────────────

def _download(url: str, dest: Path, label: str) -> None:
    if dest.exists():
        print(f"  [cache] {label} already present — skipping download")
        return
    print(f"  [download] {label} …", flush=True)
    tmp = dest.with_suffix(".tmp")
    def _progress(count, block, total):
        if total > 0:
            pct = min(100, count * block * 100 // total)
            print(f"\r    {pct}% ", end="", flush=True)
    urllib.request.urlretrieve(url, tmp, _progress)
    print()
    tmp.rename(dest)
    print(f"  [ok] saved {dest.stat().st_size / 1e6:.1f} MB → {dest.name}")


# ── chr22 loader ───────────────────────────────────────────────────────────────

def load_chr22(path: Path) -> str:
    print("  Loading chr22 sequence …", flush=True)
    parts: list[str] = []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith(">"):
                continue
            parts.append(line.strip())
    seq = "".join(parts).upper()
    print(f"  chr22 length: {len(seq):,} bp")
    return seq


# ── GTF parser — chr22 only ────────────────────────────────────────────────────

def parse_gtf_chr22(path: Path) -> tuple[list[tuple[int,int]], list[tuple[int,int]], list[tuple[int,int]]]:
    """
    Returns three sorted interval lists (0-based half-open):
        genes   — entire gene loci
        exons   — all exon records
        cds     — CDS records (coding exons only)

    UTR = exon - CDS  (computed later)
    Intron = gene - exon
    Intergenic = chr - gene
    """
    print("  Parsing GENCODE GTF (chr22 entries) …", flush=True)
    genes:  list[tuple[int,int]] = []
    exons:  list[tuple[int,int]] = []
    cds:    list[tuple[int,int]] = []
    utrs:   list[tuple[int,int]] = []

    opener = gzip.open if str(path).endswith(".gz") else open
    n_lines = 0
    with opener(path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 9:
                continue
            chrom, _, feat, start, end = cols[0], cols[1], cols[2], int(cols[3]), int(cols[4])
            if chrom != "chr22":
                continue
            n_lines += 1
            iv = (start - 1, end)   # convert to 0-based half-open
            if   feat == "gene":    genes.append(iv)
            elif feat == "exon":    exons.append(iv)
            elif feat == "CDS":     cds.append(iv)
            elif feat == "UTR":     utrs.append(iv)

    print(f"  chr22 GTF records: {n_lines:,}  genes={len(genes):,}  exons={len(exons):,}  CDS={len(cds):,}  UTR={len(utrs):,}")
    return (sorted(genes), sorted(exons), sorted(cds), sorted(utrs))


# ── per-base label array ───────────────────────────────────────────────────────
# Labels: 0=intergenic, 1=intron, 2=utr, 3=coding_exon

def build_label_array(chr_len: int,
                      genes: list[tuple[int,int]],
                      exons: list[tuple[int,int]],
                      cds:   list[tuple[int,int]],
                      utrs:  list[tuple[int,int]]) -> bytearray:
    print("  Building per-base label array …", flush=True)
    labels = bytearray(chr_len)   # default 0 = intergenic

    for s, e in genes:
        for i in range(max(0,s), min(chr_len, e)):
            labels[i] = 1           # intron (overridden below)

    for s, e in exons:
        for i in range(max(0,s), min(chr_len, e)):
            if labels[i] == 1:      # only upgrade intron → exon base
                labels[i] = 2       # utr (refined below)

    # CDS overrides exon
    for s, e in cds:
        for i in range(max(0,s), min(chr_len, e)):
            labels[i] = 3           # coding_exon

    # Explicit UTR from GTF (fills any exon bases not covered by CDS)
    for s, e in utrs:
        for i in range(max(0,s), min(chr_len, e)):
            if labels[i] == 2:      # only if still marked as generic exon
                labels[i] = 2       # already utr, confirm

    label_names = {0: "intergenic", 1: "intron", 2: "utr", 3: "coding_exon"}
    counts = {v: labels.count(k) for k, v in label_names.items()}
    for name, cnt in counts.items():
        print(f"    {name}: {cnt:,} bp ({cnt/chr_len*100:.1f}%)")

    return labels


# ── window sampler ─────────────────────────────────────────────────────────────

def sample_windows(seq: str, labels: bytearray, label_val: int,
                   n: int, rng: random.Random) -> list[str]:
    """
    Sample n non-overlapping 20-mer windows where ALL 20 bases have
    the target label and the sequence contains only ACGT.
    """
    valid_starts: list[int] = []
    chr_len = len(seq)
    step = 1
    # Collect candidate starts (stride 5 for speed, then shuffle)
    for i in range(0, chr_len - GUIDE_LEN, 5):
        if all(labels[i + j] == label_val for j in range(GUIDE_LEN)):
            window = seq[i:i + GUIDE_LEN]
            if all(c in "ACGT" for c in window):
                valid_starts.append(i)

    rng.shuffle(valid_starts)

    # Non-overlapping selection
    selected: list[str] = []
    used: list[tuple[int,int]] = []
    for s in valid_starts:
        e = s + GUIDE_LEN
        if any(s < ue and e > us for us, ue in used):
            continue
        selected.append(seq[s:e])
        used.append((s, e))
        if len(selected) >= n:
            break

    return selected


# ── scoring ────────────────────────────────────────────────────────────────────

def score_windows(windows: list[str]) -> list[float]:
    sys.path.insert(0, str(ROOT))
    from snipgen.scoring.consequence_scorer import _score_sequence

    scores = []
    for w in windows:
        gc = sum(1 for c in w if c in "GC") / len(w)
        score, _ = _score_sequence(w, gc)
        scores.append(score)
    return scores


# ── statistics ─────────────────────────────────────────────────────────────────

def mann_whitney_u(a: list[float], b: list[float]) -> float:
    """Simple Mann-Whitney U statistic normalised to AUROC (0.5 = random)."""
    u = sum(1 for x in a for y in b if x < y) + 0.5 * sum(1 for x in a for y in b if x == y)
    return u / (len(a) * len(b))


def summarise(scores: list[float], label: str) -> dict:
    return {
        "category": label,
        "n":        len(scores),
        "mean":     round(statistics.mean(scores), 2),
        "stdev":    round(statistics.stdev(scores), 2),
        "median":   round(statistics.median(scores), 2),
        "p10":      round(sorted(scores)[len(scores)//10], 2),
        "p90":      round(sorted(scores)[9*len(scores)//10], 2),
    }


def ascii_histogram(scores: list[float], label: str, width: int = 40) -> str:
    bins = [0] * 10
    for s in scores:
        b = min(9, int(s // 10))
        bins[b] += 1
    max_count = max(bins) or 1
    lines = [f"  {label}"]
    for i, cnt in enumerate(bins):
        bar = "█" * int(cnt / max_count * width)
        lines.append(f"  {i*10:3d}-{i*10+9:3d} | {bar:<{width}} {cnt}")
    return "\n".join(lines)


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    rng = random.Random(RANDOM_SEED)

    print("\n══ Step 1: Download reference data ══")
    _download(CHR22_URL, CHR22_GZ, "hg38 chr22 FASTA")
    _download(GTF_URL,   GTF_GZ,   "GENCODE v44 GTF")

    print("\n══ Step 2: Load chr22 sequence ══")
    chr22 = load_chr22(CHR22_GZ)

    print("\n══ Step 3: Parse GENCODE annotations ══")
    genes, exons, cds, utrs = parse_gtf_chr22(GTF_GZ)

    print("\n══ Step 4: Build per-base label array ══")
    labels = build_label_array(len(chr22), genes, exons, cds, utrs)

    print(f"\n══ Step 5: Sample {SAMPLE_PER_CATEGORY:,} guides per category ══")
    categories = {
        "coding_exon":  3,
        "utr":          2,
        "intron":       1,
        "intergenic":   0,
    }
    windows: dict[str, list[str]] = {}
    for cat, val in categories.items():
        w = sample_windows(chr22, labels, val, SAMPLE_PER_CATEGORY, rng)
        windows[cat] = w
        print(f"  {cat}: {len(w)} windows sampled")

    print("\n══ Step 6: Score with consequence scorer ══")
    scores: dict[str, list[float]] = {}
    for cat, ws in windows.items():
        scores[cat] = score_windows(ws)
        print(f"  {cat}: scored {len(scores[cat])} guides")

    print("\n══ Step 7: Results ══\n")
    summaries = [summarise(scores[c], c) for c in categories]

    header = f"{'Category':<15} {'N':>5} {'Mean':>7} {'Stdev':>7} {'Median':>7} {'P10':>7} {'P90':>7}"
    print(header)
    print("─" * len(header))
    for s in summaries:
        print(f"{s['category']:<15} {s['n']:>5} {s['mean']:>7} {s['stdev']:>7} {s['median']:>7} {s['p10']:>7} {s['p90']:>7}")

    print("\n  Expected ordering: coding_exon < utr < intron < intergenic")
    means = {c: statistics.mean(scores[c]) for c in categories}
    ordered = sorted(means, key=means.get)
    print(f"  Observed ordering: {' < '.join(ordered)}")

    expected = ["coding_exon", "utr", "intron", "intergenic"]
    passed = all(means[expected[i]] <= means[expected[i+1]] for i in range(len(expected)-1))
    print(f"  Ordering correct: {'✅ YES' if passed else '❌ NO'}")

    print("\n  AUROC-style separation (higher = scorer separates categories better):")
    pairs = [
        ("coding_exon vs intergenic", "coding_exon", "intergenic"),
        ("coding_exon vs intron",     "coding_exon", "intron"),
        ("coding_exon vs utr",        "coding_exon", "utr"),
        ("utr vs intron",             "utr",         "intron"),
        ("intron vs intergenic",      "intron",       "intergenic"),
    ]
    for label, a, b in pairs:
        auroc = mann_whitney_u(scores[a], scores[b])
        bar = "█" * int(auroc * 20)
        print(f"  {label:<35} AUROC={auroc:.3f}  {bar}")

    print()
    for cat in categories:
        print(ascii_histogram(scores[cat], cat))
        print()

    # Save TSV
    with open(RESULTS_TSV, "w") as f:
        f.write("category\tscore\n")
        for cat, sc_list in scores.items():
            for sc in sc_list:
                f.write(f"{cat}\t{sc}\n")
    print(f"  Results saved → {RESULTS_TSV}")


if __name__ == "__main__":
    main()
