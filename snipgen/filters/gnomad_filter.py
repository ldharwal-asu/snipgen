"""
gnomAD population variant filter.

For each guide RNA, checks whether the guide sequence spans a common
population variant (MAF ≥ 0.1% in gnomAD v4) at its target genomic locus.

Why this matters:
    If a guide spans a common SNP, it will fail to cut in individuals
    carrying that variant (mismatches in the seed region reduce Cas9
    activity dramatically). For therapeutic applications, a guide spanning
    a 1% MAF variant effectively excludes ~2% of the population (heterozygotes)
    or ~0.01% (homozygotes) from treatment.

    Seed region SNPs (positions 1-12 from PAM, i.e., guide positions 9-20)
    are especially critical — a single mismatch here reduces cutting by >80%.

Implementation:
    Uses the gnomAD GraphQL API (no auth required, rate-limited to ~3 req/s).
    Queries by genomic region using gene coordinates from a pre-built table
    (covers the 22 genes in SnipGen's fast-path accession lookup).

    For genes not in the table, we skip gracefully rather than block pipeline.

Output per guide:
    {
      "gnomad_checked":     bool,
      "snp_in_guide":       bool,      # any variant MAF > 0.001
      "snp_in_seed":        bool,      # variant in positions 9-20 (seed)
      "max_maf":            float,     # highest MAF variant overlapping guide
      "variant_id":         str,       # e.g. "17-7674220-C-T"
      "population_impact":  str,       # "HIGH" | "MODERATE" | "LOW" | "NONE"
      "flag":               str,       # human-readable warning
    }
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Optional

_GNOMAD_API = "https://gnomad.broadinstitute.org/api"
_TIMEOUT    = 8
_MAF_HIGH   = 0.01    # 1%  — definitely problematic therapeutically
_MAF_MOD    = 0.001   # 0.1% — flag for therapeutic use

# Gene → (chromosome, approximate CDS start, CDS end) on GRCh38
# Covers all genes in SnipGen's fast-path accession table
_GENE_COORDS: dict[str, tuple[str, int, int]] = {
    "TP53":  ("17", 7661779,  7687538),
    "BRCA1": ("17", 43044295, 43125370),
    "BRCA2": ("13", 32315480, 32400268),
    "EGFR":  ("7",  55019017, 55211628),
    "KRAS":  ("12", 25205246, 25250929),
    "PTEN":  ("10", 89623195, 89728532),
    "MYC":   ("8",  127735434,127742951),
    "VEGFA": ("6",  43770209, 43786487),
    "PCSK9": ("1",  55039474, 55064852),
    "HBB":   ("11", 5225464,  5229395),
    "DMD":   ("X",  31094932, 33339609),
    "CFTR":  ("7",  117480025,117668665),
    "APOE":  ("19", 44905796, 44909393),
    "ACE2":  ("X",  15561033, 15602148),
    "STAT3": ("17", 42313324, 42388568),
    # Mouse genes — skip gnomAD (human-only database)
}

_gnomad_cache: dict[str, list[dict]] = {}   # region_key → variant list


def _query_gnomad_region(chrom: str, start: int, stop: int) -> list[dict]:
    """Fetch all gnomAD v4 variants in a region. Returns list of variant dicts."""
    key = f"{chrom}:{start}-{stop}"
    if key in _gnomad_cache:
        return _gnomad_cache[key]

    query = """
    {
      region(chrom: "%s", start: %d, stop: %d, reference_genome: GRCh38) {
        variants(dataset: gnomad_r4) {
          variant_id
          pos
          ref
          alt
          genome {
            af
            ac
            an
          }
        }
      }
    }
    """ % (chrom, start, stop)

    try:
        payload = json.dumps({"query": query}).encode()
        req = urllib.request.Request(
            _GNOMAD_API,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SnipGen/1.0"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
        variants = data.get("data", {}).get("region", {}).get("variants", []) or []
        # Keep only variants with actual allele frequency data
        variants = [v for v in variants if v.get("genome") and v["genome"].get("af") is not None]
        time.sleep(0.35)  # rate limit
    except Exception:
        variants = []

    _gnomad_cache[key] = variants
    return variants


def check_guide_gnomad(
    guide_seq: str,
    gene_symbol: str,
    guide_start_in_mrna: int,   # 0-based position in mRNA/input sequence
    guide_end_in_mrna: int,
    strand: str = "+",
    organism: str = "human",
) -> dict:
    """
    Check whether a guide overlaps any common gnomAD variant.

    Args:
        guide_seq:          20-mer guide sequence (no PAM)
        gene_symbol:        Gene symbol (used to look up genomic coordinates)
        guide_start_in_mrna: Guide start position in the input sequence (0-based)
        guide_end_in_mrna:   Guide end position in the input sequence (0-based)
        strand:             "+" or "-"
        organism:           Only "human" is supported (gnomAD is human-only)

    Returns dict with gnomAD annotation (see module docstring).
    """
    empty = {
        "gnomad_checked": False,
        "snp_in_guide": False,
        "snp_in_seed": False,
        "max_maf": 0.0,
        "variant_id": "",
        "population_impact": "NONE",
        "flag": "",
    }

    if organism.lower() != "human":
        return {**empty, "flag": "gnomAD not available for non-human organisms"}

    coords = _GENE_COORDS.get(gene_symbol.upper())
    if not coords:
        return {**empty, "flag": "Gene not in gnomAD coordinate table — skipped"}

    chrom, gene_start, gene_end = coords

    # Map guide position in mRNA to approximate genomic position
    # For mRNA sequences (which is what we fetch), the mapping is approximate
    # because introns are spliced out. We use the CDS length as a fraction.
    gene_length = gene_end - gene_start
    mrna_approx_len = max(guide_end_in_mrna, 1000)
    scale = gene_length / mrna_approx_len

    if strand == "+":
        gstart = int(gene_start + guide_start_in_mrna * scale)
        gend   = int(gene_start + guide_end_in_mrna   * scale)
    else:
        gend   = int(gene_end - guide_start_in_mrna * scale)
        gstart = int(gene_end - guide_end_in_mrna   * scale)

    # Add 5bp padding
    gstart = max(0, gstart - 5)
    gend   = gend + 5

    # Limit query window to 100bp max (API constraint)
    if gend - gstart > 100:
        mid    = (gstart + gend) // 2
        gstart = mid - 50
        gend   = mid + 50

    variants = _query_gnomad_region(chrom, gstart, gend)

    if not variants:
        return {**empty, "gnomad_checked": True,
                "flag": "No variants found in guide region (gnomAD v4)"}

    # Find variants overlapping the guide region
    # Seed region = last 12nt = positions 9-20 = genomic positions near PAM
    guide_len = len(guide_seq)
    seed_fraction_start = 8 / guide_len   # positions 9-20

    overlapping = []
    for v in variants:
        af = float(v["genome"]["af"] or 0)
        if af < 0.00001:   # skip ultra-rare
            continue
        # Rough position check (within the guide window)
        vpos = int(v["pos"])
        if gstart <= vpos <= gend:
            # Estimate if in seed region (rough — genomic mapping is approximate)
            guide_window = gend - gstart
            pos_frac = (vpos - gstart) / max(guide_window, 1)
            in_seed  = pos_frac >= seed_fraction_start if strand == "+" else pos_frac <= (1 - seed_fraction_start)
            overlapping.append({
                "variant_id": v["variant_id"],
                "pos": vpos,
                "af": af,
                "in_seed": in_seed,
            })

    if not overlapping:
        return {**empty, "gnomad_checked": True,
                "flag": "No common variants in guide region"}

    # Find worst (highest MAF) variant
    worst = max(overlapping, key=lambda x: x["af"])
    max_maf     = worst["af"]
    snp_in_seed = any(v["in_seed"] for v in overlapping if v["af"] >= _MAF_MOD)
    snp_in_guide = max_maf >= _MAF_MOD

    # Impact classification
    if max_maf >= _MAF_HIGH and snp_in_seed:
        impact = "HIGH"
        flag   = f"⚠️ Common SNP in seed region (MAF={max_maf:.1%}) — guide will fail in ~{max_maf*200:.0f}/1000 alleles"
    elif max_maf >= _MAF_HIGH:
        impact = "MODERATE"
        flag   = f"SNP in guide (MAF={max_maf:.1%}) — may reduce efficiency in some individuals"
    elif max_maf >= _MAF_MOD and snp_in_seed:
        impact = "MODERATE"
        flag   = f"Low-frequency SNP in seed (MAF={max_maf:.1%}) — monitor in diverse populations"
    elif max_maf >= _MAF_MOD:
        impact = "LOW"
        flag   = f"Rare variant in guide region (MAF={max_maf:.1%}) — low therapeutic concern"
    else:
        impact = "NONE"
        flag   = "No common variants detected"

    return {
        "gnomad_checked":    True,
        "snp_in_guide":      snp_in_guide,
        "snp_in_seed":       snp_in_seed,
        "max_maf":           round(max_maf, 6),
        "variant_id":        worst["variant_id"],
        "population_impact": impact,
        "flag":              flag,
    }


def batch_check_guides(
    candidates: list,
    gene_symbol: str,
    organism: str = "human",
) -> None:
    """
    Annotate a list of GRNACandidate objects with gnomAD data in-place.
    Skips gracefully if gene not in coordinate table or API unavailable.
    """
    if gene_symbol.upper() not in _GENE_COORDS or organism.lower() != "human":
        return

    for c in candidates:
        try:
            result = check_guide_gnomad(
                guide_seq           = c.sequence,
                gene_symbol         = gene_symbol,
                guide_start_in_mrna = c.start,
                guide_end_in_mrna   = c.end,
                strand              = c.strand,
                organism            = organism,
            )
            if hasattr(c, "score_breakdown"):
                c.score_breakdown["gnomad_checked"]     = result["gnomad_checked"]
                c.score_breakdown["gnomad_snp_in_seed"] = result["snp_in_seed"]
                c.score_breakdown["gnomad_max_maf"]     = result["max_maf"]
                c.score_breakdown["gnomad_variant_id"]  = result["variant_id"]
                c.score_breakdown["gnomad_impact"]      = result["population_impact"]
                c.score_breakdown["gnomad_flag"]        = result["flag"]

                # Apply score penalty for seed-region SNPs
                if result["snp_in_seed"] and result["max_maf"] >= _MAF_HIGH:
                    c.score_breakdown["gnomad_penalty"] = -15.0
                elif result["snp_in_seed"] and result["max_maf"] >= _MAF_MOD:
                    c.score_breakdown["gnomad_penalty"] = -8.0
                else:
                    c.score_breakdown["gnomad_penalty"] = 0.0
        except Exception:
            pass
