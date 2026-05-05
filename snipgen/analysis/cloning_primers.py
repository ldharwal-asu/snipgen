"""
Cloning oligo designer for CRISPR guide RNAs.

Generates the two annealed oligos needed to clone a guide into common
CRISPR expression vectors via Type IIS restriction enzyme digestion.

Supported vector / enzyme combinations
───────────────────────────────────────
  pX330 / pX458 / pX459   → BbsI    (5'-GAAGAC-3', cuts 2/6 nt downstream)
  lentiCRISPR v2            → BsmBI   (5'-CGTCTC-3', cuts 1/5 nt downstream)
  pGuide                    → Esp3I   (same overhangs as BsmBI)
  pLentiGuide               → BstXI   (5'-CACC/GGTG overhang style)
  pX601 (AAV-SpCas9)        → BsaI    (5'-GGTCTC-3')

For all SpCas9 vectors using NGG PAM:
  Top    oligo: 5'-CACC + [guide 20-mer]-3'
  Bottom oligo: 5'-AAAC + [RC of guide 20-mer]-3'

U6 promoter note:
  The U6 promoter requires a G at +1 for efficient transcription.
  If the guide does NOT start with G, we prepend G to the top oligo
  (CACC-G-[guide]) and append C to the bottom oligo (AAAC-[RC]-C).
  This is standard practice; it adds a non-targeting G that Cas9 tolerates.

For in vitro transcription (T7 promoter):
  The T7 promoter requires GG at +1/+2.
  Top oligo: TAATACGACTCACTATA + GG + [guide, trimmed to 20 nt]

Reference:
  Ran et al. (2013) Nature Protocols 8:2281-2308.
  "Genome engineering using the CRISPR-Cas9 system."
"""

from __future__ import annotations

_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def _reverse_complement(seq: str) -> str:
    return seq.upper().translate(_COMPLEMENT)[::-1]


def _rc(seq: str) -> str:
    return _reverse_complement(seq)


def design_cloning_oligos(
    guide_seq: str,
    vector: str = "pX330",
) -> dict:
    """
    Design the pair of annealing oligos for a guide RNA.

    Args:
        guide_seq:  20-mer guide sequence (no PAM, 5'→3')
        vector:     Target vector. One of:
                    "pX330", "pX458", "pX459", "lentiCRISPR", "pGuide",
                    "pX601", "generic_BbsI", "generic_BsmBI", "T7"

    Returns dict:
        {
          "top_oligo":    str,   # 5'→3' sequence to order
          "bottom_oligo": str,   # 5'→3' sequence to order (is RC of annealed strand)
          "overhang_top": str,   # The 5' overhang added (e.g. "CACC")
          "overhang_bot": str,   # The 5' overhang added to bottom
          "vector":       str,
          "enzyme":       str,
          "added_g":      bool,  # True if a G was prepended for U6 transcription
          "annealing_tm": float, # Approximate Tm of the annealed guide duplex
          "ordering_note": str,  # Human-readable note for ordering
          "t7_template":  str,   # T7 in vitro transcription template (if applicable)
        }
    """
    guide = guide_seq.upper().strip()[:20].ljust(20, "N")
    rc_guide = _rc(guide)

    vector = vector.strip()

    # Determine whether a leading G is needed for U6 transcription
    added_g = guide[0] != "G"

    # Vector → (enzyme, top_overhang_prefix, bottom_overhang_prefix)
    # All Cas9 NGG vectors use essentially the same overhang geometry
    _VECTOR_CONFIGS: dict[str, tuple[str, str, str]] = {
        "pX330":       ("BbsI",  "CACC", "AAAC"),
        "pX458":       ("BbsI",  "CACC", "AAAC"),
        "pX459":       ("BbsI",  "CACC", "AAAC"),
        "generic_BbsI":("BbsI",  "CACC", "AAAC"),
        "lentiCRISPR": ("BsmBI", "CACC", "AAAC"),
        "pGuide":      ("Esp3I", "CACC", "AAAC"),
        "pLentiGuide": ("BstXI", "CACC", "AAAC"),
        "pX601":       ("BsaI",  "CACC", "AAAC"),
        "generic_BsmBI":("BsmBI","CACC", "AAAC"),
        "T7":          ("T7",    "",     ""),
    }

    if vector not in _VECTOR_CONFIGS:
        vector = "pX330"

    enzyme, top_pre, bot_pre = _VECTOR_CONFIGS[vector]

    if enzyme == "T7":
        # T7 promoter-based in vitro transcription
        # Requires GG at +1/+2 for optimal T7 recognition
        guide_for_t7 = guide if guide[:2] == "GG" else ("GG" + guide[:18])
        top_oligo = "TAATACGACTCACTATA" + guide_for_t7
        bot_oligo = _rc(top_oligo)  # full double-stranded template
        top_with_g   = guide_for_t7
        added_g_t7   = guide[:2] != "GG"
        return {
            "top_oligo":     top_oligo,
            "bottom_oligo":  bot_oligo,
            "overhang_top":  "TAATACGACTCACTATA",
            "overhang_bot":  "",
            "vector":        vector,
            "enzyme":        "T7 RNA Polymerase",
            "added_g":       added_g_t7,
            "annealing_tm":  _tm(guide),
            "ordering_note": (
                "Order both oligos for in vitro transcription. "
                "Anneal and use as template for T7 polymerase."
            ),
            "t7_template":   top_oligo,
        }

    # Standard Type IIS restriction cloning
    if added_g:
        top_oligo = top_pre + "G" + guide
        bot_oligo = bot_pre + rc_guide + "C"
    else:
        top_oligo = top_pre + guide
        bot_oligo = bot_pre + rc_guide

    tm = _tm(guide)

    note_parts = [
        f"Order both oligos PAGE-purified or standard desalted.",
        f"Anneal: 95°C 5 min → ramp to 25°C at −5°C/min in annealing buffer.",
        f"Dilute annealed duplex 1:200 before ligation.",
        f"Digest {vector} with {enzyme} ({_ENZYME_SITES[enzyme]}), ligate at 16°C overnight.",
    ]
    if added_g:
        note_parts.insert(0, "⚠ Guide does not start with G — a G was prepended for U6 promoter transcription.")

    return {
        "top_oligo":     top_oligo,
        "bottom_oligo":  bot_oligo,
        "overhang_top":  top_pre + ("G" if added_g else ""),
        "overhang_bot":  bot_pre + ("C" if added_g else ""),
        "vector":        vector,
        "enzyme":        enzyme,
        "added_g":       added_g,
        "annealing_tm":  round(tm, 1),
        "ordering_note": " ".join(note_parts),
        "t7_template":   "",
    }


def design_all_vectors(guide_seq: str) -> dict[str, dict]:
    """Return cloning oligos for all common vectors."""
    vectors = ["pX330", "lentiCRISPR", "pX458", "pX601", "T7"]
    return {v: design_cloning_oligos(guide_seq, v) for v in vectors}


# ── Helpers ────────────────────────────────────────────────────────────────────

_ENZYME_SITES = {
    "BbsI":  "recognition site GAAGAC",
    "BsmBI": "recognition site CGTCTC",
    "Esp3I": "recognition site CGTCTC (isoschizomer of BsmBI)",
    "BstXI": "recognition site CCANNNNNTGG",
    "BsaI":  "recognition site GGTCTC",
}


def _tm(seq: str) -> float:
    """
    Approximate melting temperature of the 20-mer guide duplex.
    Uses the Wallace rule (< 20 nt) or Marmur-Doty (≥ 20 nt):
      Tm = 81.5 + 16.6 * log10([Na+]) + 0.41 * %GC - 675/N
    Assumes 50 mM Na+ and N=20.
    """
    seq = seq.upper()[:20]
    gc = sum(1 for n in seq if n in "GC")
    gc_pct = gc / len(seq) * 100 if seq else 50.0
    n = len(seq)
    # Marmur-Doty approximation with 50 mM Na+
    tm = 81.5 + 16.6 * 1.699 + 0.41 * gc_pct - 675 / n
    return tm
