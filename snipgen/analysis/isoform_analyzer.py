"""
Isoform Specificity Analyzer for SnipGen.

For a given gene, fetches all RefSeq transcript (mRNA) accessions and
checks what fraction of them each guide sequence targets. This tells the
researcher:

  - Is this guide "pan-isoform" (cuts every transcript)?
  - Is it "isoform-selective" (cuts only one or a few transcripts)?
  - Is it in an exon skipped by some isoforms?

Why this matters
────────────────
Many clinically important genes have 3–20+ RefSeq transcripts. A guide
targeting an exon present in only 30% of isoforms may leave disease-
causing splice variants intact. Conversely, researchers studying isoform-
specific biology may *want* selective guides.

Implementation
──────────────
1. Fetch all RefSeq NM_* accession IDs for the gene via NCBI Entrez esearch.
2. Download the FASTA for each (up to _MAX_ISOFORMS, rate-limited).
3. Search each FASTA for the reverse-complement-aware presence of the 20-mer.
4. Return per-guide isoform coverage fraction + list of isoforms hit/missed.

Performance
───────────
Results are cached in memory. A 15-gene lookup with 5 isoforms each
takes ~10–15 s (mostly NCBI latency). For larger genes like DMD (79
exons, 7 isoforms) the analysis is still fast because we search FASTA
strings not parse GTF files.

Output per guide
────────────────
{
  "isoform_checked":     bool,
  "n_isoforms_total":    int,
  "n_isoforms_targeted": int,
  "coverage_fraction":   float,   # 0.0 – 1.0
  "specificity_label":   str,     # "PAN-ISOFORM" | "BROAD" | "SELECTIVE" | "SINGLE"
  "isoforms_hit":        list[str],  # accession IDs where guide found
  "isoforms_missed":     list[str],  # accession IDs where guide NOT found
  "flag":                str,
}
"""

from __future__ import annotations

import time
from typing import Optional

_ENTREZ_EMAIL = "snipgen-tool@noreply.asu.edu"
_ENTREZ_TOOL  = "snipgen"
_MAX_ISOFORMS = 12    # cap to keep NCBI calls reasonable
_REQUEST_DELAY = 0.4  # seconds between NCBI requests (rate limit: 3/s)

# Module-level caches
_isoform_fasta_cache: dict[str, str]       = {}   # accession → sequence (uppercase, no gaps)
_gene_accession_cache: dict[str, list[str]] = {}   # gene:organism → [NM_xxx, ...]

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _reverse_complement(seq: str) -> str:
    return seq.upper().translate(_COMPLEMENT)[::-1]


def _sequence_from_fasta(fasta_text: str) -> str:
    """Strip FASTA header(s) and return uppercase sequence string."""
    lines = [l.strip() for l in fasta_text.splitlines() if not l.startswith(">") and l.strip()]
    return "".join(lines).upper().replace(" ", "").replace("\n", "")


def _fetch_accessions(gene_symbol: str, organism: str, taxid: str) -> list[str]:
    """Return up to _MAX_ISOFORMS RefSeq NM_ accessions for gene."""
    cache_key = f"{gene_symbol.upper()}:{organism.lower()}"
    if cache_key in _gene_accession_cache:
        return _gene_accession_cache[cache_key]

    try:
        from Bio import Entrez
        Entrez.email = _ENTREZ_EMAIL
        Entrez.tool  = _ENTREZ_TOOL

        term = (
            f"{gene_symbol}[Gene Name] AND {taxid}[Taxonomy ID] "
            f"AND mRNA[Filter] AND RefSeq[Filter]"
        )
        h   = Entrez.esearch(db="nuccore", term=term, retmax=_MAX_ISOFORMS)
        rec = Entrez.read(h); h.close()
        ids = rec.get("IdList", [])[:_MAX_ISOFORMS]
        time.sleep(_REQUEST_DELAY)

        if not ids:
            _gene_accession_cache[cache_key] = []
            return []

        # Convert GI→accession
        h2  = Entrez.efetch(db="nuccore", id=",".join(ids), rettype="acc", retmode="text")
        acc_text = h2.read(); h2.close()
        time.sleep(_REQUEST_DELAY)

        accessions = [a.strip().split(".")[0] for a in acc_text.strip().splitlines() if a.strip()]
        # Keep only NM_ and NR_ accessions (RefSeq mRNA/ncRNA)
        accessions = [a for a in accessions if a.startswith(("NM_", "NR_"))]

    except Exception:
        accessions = []

    _gene_accession_cache[cache_key] = accessions
    return accessions


def _fetch_fasta_sequence(accession: str) -> Optional[str]:
    """Fetch and cache the FASTA sequence for one accession. Returns uppercase seq or None."""
    if accession in _isoform_fasta_cache:
        return _isoform_fasta_cache[accession]

    try:
        from Bio import Entrez
        Entrez.email = _ENTREZ_EMAIL
        Entrez.tool  = _ENTREZ_TOOL

        h    = Entrez.efetch(db="nuccore", id=accession, rettype="fasta", retmode="text")
        fasta = h.read(); h.close()
        time.sleep(_REQUEST_DELAY)

        seq = _sequence_from_fasta(fasta)
        if not seq:
            return None
        _isoform_fasta_cache[accession] = seq
        return seq

    except Exception:
        return None


def _guide_in_sequence(guide_20: str, seq: str) -> bool:
    """Return True if guide (or its reverse complement) is found in seq."""
    g = guide_20.upper()
    rc = _reverse_complement(g)
    return g in seq or rc in seq


# ── Public API ────────────────────────────────────────────────────────────────

_ORGANISM_TAXIDS = {
    "human":      "9606",
    "mouse":      "10090",
    "zebrafish":  "7955",
    "rat":        "10116",
    "drosophila": "7227",
    "c_elegans":  "6239",
}


def analyze_guide_isoforms(
    guide_seq: str,
    gene_symbol: str,
    organism: str = "human",
) -> dict:
    """
    Check isoform coverage for a single guide.

    Args:
        guide_seq:    20-mer guide sequence (no PAM)
        gene_symbol:  e.g. "TP53", "BRCA1"
        organism:     "human", "mouse", etc.

    Returns isoform annotation dict (see module docstring).
    """
    empty = {
        "isoform_checked":     False,
        "n_isoforms_total":    0,
        "n_isoforms_targeted": 0,
        "coverage_fraction":   0.0,
        "specificity_label":   "UNKNOWN",
        "isoforms_hit":        [],
        "isoforms_missed":     [],
        "flag":                "",
    }

    taxid = _ORGANISM_TAXIDS.get(organism.lower(), "9606")
    accessions = _fetch_accessions(gene_symbol, organism, taxid)

    if not accessions:
        return {**empty, "flag": f"No RefSeq transcripts found for {gene_symbol} in {organism}"}

    hit, miss = [], []
    for acc in accessions:
        seq = _fetch_fasta_sequence(acc)
        if seq is None:
            continue
        if _guide_in_sequence(guide_seq, seq):
            hit.append(acc)
        else:
            miss.append(acc)

    total  = len(hit) + len(miss)
    if total == 0:
        return {**empty, "isoform_checked": True,
                "flag": "Could not fetch transcript sequences"}

    frac = len(hit) / total

    if frac == 1.0:
        label = "PAN-ISOFORM"
        flag  = f"✅ Guide targets all {total} transcripts — pan-isoform"
    elif frac >= 0.75:
        label = "BROAD"
        flag  = f"Guide targets {len(hit)}/{total} transcripts ({frac:.0%} coverage)"
    elif frac >= 0.30:
        label = "SELECTIVE"
        flag  = (
            f"⚠️ Isoform-selective: {len(hit)}/{total} transcripts targeted — "
            f"{len(miss)} isoform(s) will escape editing"
        )
    elif len(hit) == 1:
        label = "SINGLE"
        flag  = (
            f"⚠️ Single-isoform: only 1/{total} transcripts targeted — "
            f"consider whether this is the disease-relevant isoform"
        )
    else:
        label = "SELECTIVE"
        flag  = (
            f"⚠️ Isoform-selective: {len(hit)}/{total} transcripts targeted"
        )

    return {
        "isoform_checked":     True,
        "n_isoforms_total":    total,
        "n_isoforms_targeted": len(hit),
        "coverage_fraction":   round(frac, 4),
        "specificity_label":   label,
        "isoforms_hit":        hit,
        "isoforms_missed":     miss,
        "flag":                flag,
    }


def batch_analyze_isoforms(
    candidates: list,
    gene_symbol: str,
    organism: str = "human",
    max_guides: int = 10,
) -> None:
    """
    Annotate up to max_guides GRNACandidate objects with isoform data in-place.

    We cap at max_guides because each new guide just needs a string search
    (sequences are cached after the first fetch), but the first call does
    N_isoforms × NCBI fetches which takes ~5-15 s.

    The cap ensures the per-job latency stays acceptable for the web UI.
    """
    for c in candidates[:max_guides]:
        try:
            result = analyze_guide_isoforms(
                guide_seq=c.sequence,
                gene_symbol=gene_symbol,
                organism=organism,
            )
            if hasattr(c, "score_breakdown"):
                c.score_breakdown["isoform_checked"]     = result["isoform_checked"]
                c.score_breakdown["isoform_total"]       = result["n_isoforms_total"]
                c.score_breakdown["isoform_targeted"]    = result["n_isoforms_targeted"]
                c.score_breakdown["isoform_fraction"]    = result["coverage_fraction"]
                c.score_breakdown["isoform_label"]       = result["specificity_label"]
                c.score_breakdown["isoform_hit"]         = result["isoforms_hit"]
                c.score_breakdown["isoform_missed"]      = result["isoforms_missed"]
                c.score_breakdown["isoform_flag"]        = result["flag"]

                # Score penalty: selective guides lose points in therapeutic context
                label = result["specificity_label"]
                if label == "PAN-ISOFORM":
                    c.score_breakdown["isoform_bonus"] = +5.0
                elif label == "BROAD":
                    c.score_breakdown["isoform_bonus"] = 0.0
                elif label == "SELECTIVE":
                    c.score_breakdown["isoform_bonus"] = -5.0
                elif label == "SINGLE":
                    c.score_breakdown["isoform_bonus"] = -10.0
                else:
                    c.score_breakdown["isoform_bonus"] = 0.0
        except Exception:
            pass
