"""
CRISPOR API client for real genome-wide off-target scoring.

CRISPOR (crispor.tefor.net / crispor.gi.ucsc.edu) runs Cas-OFFinder under
the hood and returns MIT specificity scores, CFD scores, and off-target
counts from actual genome alignment against hg38 (or other genomes).

Workflow (async — designed for Vercel serverless timeouts):
    1. submit_sequence()  →  batch_id  (< 1 s)
    2. fetch_scores()     →  dict | None  (call until not None, ~20-60 s)

The caller is responsible for polling — this module is stateless.

Supported genomes (CRISPOR genome codes):
    human      → hg38
    mouse      → mm39
    zebrafish  → danRer11
    rat        → rn7
    drosophila → dm6
    c_elegans  → ce11
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Optional

# CRISPOR mirror — use UCSC which proved reachable
_BASE = "http://crispor.gi.ucsc.edu/crispor.py"
_TIMEOUT = 8       # seconds per HTTP call (keep under Vercel 10s limit)
_MAX_SEQ_LEN = 3_000   # CRISPOR degrades gracefully but let's stay sane

GENOME_MAP = {
    "human":      "hg38",
    "mouse":      "mm39",
    "zebrafish":  "danRer11",
    "rat":        "rn7",
    "drosophila": "dm6",
    "c_elegans":  "ce11",
}

PAM_MAP = {
    "SpCas9":  "NGG",
    "SaCas9":  "NNGRRT",
    "Cpf1":    "TTTN",
    "xCas9":   "NGG",
    "Cas9-NG": "NG",
}


def _crispor_get(params: dict, timeout: int = _TIMEOUT) -> Optional[str]:
    """GET request to CRISPOR; returns response text or None on error."""
    url = _BASE + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SnipGen/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def submit_sequence(
    fasta_text: str,
    organism: str = "human",
    cas_variant: str = "SpCas9",
) -> Optional[str]:
    """
    Submit a FASTA sequence to CRISPOR for off-target analysis.

    Returns the batchId string (e.g. 'iBne64A8a3Ya7XHH89x3') if successful,
    or None if the submission failed or CRISPOR is unreachable.

    The returned batchId should be stored and passed to fetch_scores() after
    a suitable delay (20-60 seconds depending on sequence length).
    """
    genome = GENOME_MAP.get(organism.lower(), "hg38")
    pam    = PAM_MAP.get(cas_variant, "NGG")

    # Extract raw DNA sequence from FASTA (strip headers + whitespace)
    lines = fasta_text.strip().splitlines()
    seq_parts = [l.strip() for l in lines if l and not l.startswith(">")]
    seq = "".join(seq_parts).upper()

    # Trim to CRISPOR's comfortable range; keep 5' end (most relevant for mRNA)
    if len(seq) > _MAX_SEQ_LEN:
        seq = seq[:_MAX_SEQ_LEN]

    # Remove anything that isn't ACGT (Ns, soft-masking artifacts)
    seq = re.sub(r"[^ACGT]", "N", seq)

    if len(seq) < 23:
        return None  # too short to have any guides

    html = _crispor_get({"seq": seq, "org": genome, "pam": pam})
    if not html:
        return None

    # CRISPOR encodes the batchId in all download links
    match = re.search(r"batchId=([A-Za-z0-9_-]{10,25})", html)
    if not match:
        return None

    return match.group(1)


def fetch_scores(batch_id: str) -> Optional[dict[str, dict]]:
    """
    Attempt to download CRISPOR results for a previously submitted batch.

    Returns a dict keyed by 20-mer guide sequence (uppercase, no PAM) →
        {
          "mit_score":      float,   # 0-100 MIT specificity (higher = safer)
          "cfd_score":      float,   # 0-100 CFD specificity (higher = safer)
          "ot_count":       int,     # total off-target sites in genome
          "gene_locus":     str,     # e.g. "exon:TP53" or ""
          "ot_0mm":         int,     # off-targets with 0 mismatches (exact matches)
          "ot_1mm":         int,     # 1-mismatch off-targets
          "ot_2mm":         int,     # 2-mismatch off-targets
          "ot_3mm":         int,     # 3-mismatch off-targets
        }

    Returns None if results are not yet available or an error occurred.
    The caller should retry after a few seconds.
    """
    tsv = _crispor_get(
        {"batchId": batch_id, "download": "guides", "format": "tsv"},
        timeout=_TIMEOUT,
    )
    if not tsv or tsv.strip().startswith("We are very sorry"):
        return None  # not ready yet

    # Parse TSV
    results: dict[str, dict] = {}
    lines = tsv.strip().splitlines()
    if not lines:
        return None

    header = lines[0].lstrip("#").split("\t")
    for line in lines[1:]:
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 5:
            continue

        row = dict(zip(header, cols))
        guide_with_pam = row.get("targetSeq", "")
        if len(guide_with_pam) < 20:
            continue

        guide_seq = guide_with_pam[:20].upper()   # strip PAM

        try:
            mit  = float(row.get("mitSpecScore", 0) or 0)
            cfd  = float(row.get("cfdSpecScore", 0) or 0)
            otc_raw = row.get("offtargetCount", "0") or "0"
            # offtargetCount can be "64" or "64/0/1/2/3" (total/0mm/1mm/2mm/3mm)
            if "/" in otc_raw:
                parts = otc_raw.split("/")
                ot_total = int(parts[0])
                ot_0mm = int(parts[1]) if len(parts) > 1 else 0
                ot_1mm = int(parts[2]) if len(parts) > 2 else 0
                ot_2mm = int(parts[3]) if len(parts) > 3 else 0
                ot_3mm = int(parts[4]) if len(parts) > 4 else 0
            else:
                ot_total = int(otc_raw)
                ot_0mm = ot_1mm = ot_2mm = ot_3mm = 0
        except (ValueError, TypeError):
            continue

        results[guide_seq] = {
            "mit_score":  round(mit, 1),
            "cfd_score":  round(cfd, 1),
            "ot_count":   ot_total,
            "gene_locus": row.get("targetGenomeGeneLocus", "").strip(),
            "ot_0mm":     ot_0mm,
            "ot_1mm":     ot_1mm,
            "ot_2mm":     ot_2mm,
            "ot_3mm":     ot_3mm,
        }

    return results if results else None


def crispor_to_offtarget_score(crispor: dict) -> float:
    """
    Convert CRISPOR results for one guide → SnipGen off-target score (0-100).

    Mapping philosophy:
      - MIT specificity score is the primary signal (validated against wet-lab data)
      - CFD score modulates (CFD is better for mismatches with RNA context)
      - Heavy penalty for any 0-mm off-targets (exact matches elsewhere in genome)
      - Moderate penalty for high off-target count

    Score 90-100: MIT ≥ 90, CFD ≥ 85, 0 exact off-targets
    Score 70-89:  MIT 70-89, few low-mismatch off-targets
    Score 40-69:  MIT 50-70, several off-targets
    Score 0-39:   MIT < 50 or any exact off-target
    """
    mit   = crispor["mit_score"]
    cfd   = crispor["cfd_score"]
    ot_0  = crispor["ot_0mm"]
    ot_1  = crispor["ot_1mm"]
    ot_total = crispor["ot_count"]

    # Base: blend MIT (70%) + CFD (30%)
    base = 0.70 * mit + 0.30 * cfd

    # Penalty for exact off-target matches (critical — possible true cuts)
    if ot_0 >= 1:
        base -= 40.0 * min(ot_0, 3)      # 40 pts per exact off-target, cap at 3

    # Penalty for 1-mismatch off-targets (likely cuts at high Cas9 concentrations)
    if ot_1 >= 1:
        base -= 8.0 * min(ot_1, 5)

    # Mild penalty for very high off-target counts (even with low MIT score,
    # a count > 200 indicates highly repetitive guide)
    if ot_total > 200:
        base -= 10.0
    elif ot_total > 50:
        base -= 5.0

    return round(max(0.0, min(100.0, base)), 1)
