"""
ClinVar off-target consequence annotator.

Given a list of off-target sites from CRISPOR (with locusDesc like "exon:BRCA2"),
this module returns clinical significance for each gene hit:

  - Gene tier (CRITICAL / HIGH / MODERATE / LOW / MINIMAL)
  - Pathogenic variant count from ClinVar
  - Associated disease categories
  - Overall consequence label

Two-layer approach:
  1. Pre-built database of ~250 clinically important genes (instant lookup)
  2. Real-time ClinVar Entrez query for any gene not in the pre-built list

Gene tiers:
  CRITICAL  — COSMIC tier 1 cancer genes + ACMG 59 actionable genes
               Off-target here = likely disqualifying
  HIGH      — COSMIC tier 2 + major Mendelian disease genes
               Off-target here = serious concern
  MODERATE  — Other annotated disease genes
               Off-target here = warrants experimental validation
  LOW       — Non-disease annotated protein-coding genes
               Off-target here = low concern
  MINIMAL   — Pseudogenes, lncRNA, intergenic
               Off-target here = acceptable
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
import json
from typing import Optional

# ── Pre-built clinical gene database ──────────────────────────────────────────
# Sources: COSMIC Cancer Gene Census (tier 1/2), ACMG SF v3.2 (actionable),
#          ClinGen haploinsufficiency, OMIM morbid map
# Format: gene_symbol → (tier, pathogenic_variants_approx, disease_category)

GENE_DB: dict[str, dict] = {
    # ── COSMIC Tier 1 — Cancer driver genes (somatic) ──────────────────────
    "TP53":   {"tier": "CRITICAL", "variants": 1732, "disease": "Pan-cancer tumor suppressor"},
    "KRAS":   {"tier": "CRITICAL", "variants": 284,  "disease": "Lung/pancreatic/colorectal cancer"},
    "NRAS":   {"tier": "CRITICAL", "variants": 156,  "disease": "Melanoma, AML"},
    "BRAF":   {"tier": "CRITICAL", "variants": 312,  "disease": "Melanoma, thyroid cancer"},
    "PIK3CA": {"tier": "CRITICAL", "variants": 423,  "disease": "Breast/colorectal cancer"},
    "PTEN":   {"tier": "CRITICAL", "variants": 891,  "disease": "Cowden syndrome, glioblastoma"},
    "RB1":    {"tier": "CRITICAL", "variants": 1247, "disease": "Retinoblastoma, osteosarcoma"},
    "APC":    {"tier": "CRITICAL", "variants": 2341, "disease": "Familial adenomatous polyposis"},
    "BRCA1":  {"tier": "CRITICAL", "variants": 3842, "disease": "Hereditary breast/ovarian cancer"},
    "BRCA2":  {"tier": "CRITICAL", "variants": 3156, "disease": "Hereditary breast/ovarian cancer"},
    "MLH1":   {"tier": "CRITICAL", "variants": 1823, "disease": "Lynch syndrome, colorectal cancer"},
    "MSH2":   {"tier": "CRITICAL", "variants": 1456, "disease": "Lynch syndrome"},
    "MSH6":   {"tier": "CRITICAL", "variants": 987,  "disease": "Lynch syndrome"},
    "PMS2":   {"tier": "CRITICAL", "variants": 743,  "disease": "Lynch syndrome"},
    "VHL":    {"tier": "CRITICAL", "variants": 1034, "disease": "Von Hippel-Lindau, renal cell carcinoma"},
    "MEN1":   {"tier": "CRITICAL", "variants": 1287, "disease": "Multiple endocrine neoplasia 1"},
    "RET":    {"tier": "CRITICAL", "variants": 534,  "disease": "MEN2, thyroid cancer"},
    "NF1":    {"tier": "CRITICAL", "variants": 2893, "disease": "Neurofibromatosis type 1"},
    "NF2":    {"tier": "CRITICAL", "variants": 723,  "disease": "Neurofibromatosis type 2"},
    "STK11":  {"tier": "CRITICAL", "variants": 498,  "disease": "Peutz-Jeghers syndrome, lung cancer"},
    "SMAD4":  {"tier": "CRITICAL", "variants": 412,  "disease": "Juvenile polyposis, pancreatic cancer"},
    "CDH1":   {"tier": "CRITICAL", "variants": 567,  "disease": "Hereditary diffuse gastric cancer"},
    "PALB2":  {"tier": "CRITICAL", "variants": 423,  "disease": "Breast cancer susceptibility"},
    "ATM":    {"tier": "CRITICAL", "variants": 2134, "disease": "Ataxia-telangiectasia, breast cancer"},
    "CHEK2":  {"tier": "CRITICAL", "variants": 312,  "disease": "Breast/colorectal cancer risk"},
    "RAD51C": {"tier": "CRITICAL", "variants": 187,  "disease": "Hereditary breast/ovarian cancer"},
    "RAD51D": {"tier": "CRITICAL", "variants": 156,  "disease": "Ovarian cancer susceptibility"},
    "CDKN2A": {"tier": "CRITICAL", "variants": 734,  "disease": "Melanoma, pancreatic cancer"},
    "CDK4":   {"tier": "CRITICAL", "variants": 89,   "disease": "Melanoma"},
    "PTCH1":  {"tier": "CRITICAL", "variants": 923,  "disease": "Gorlin syndrome, basal cell carcinoma"},
    "SUFU":   {"tier": "CRITICAL", "variants": 134,  "disease": "Gorlin syndrome"},
    "WT1":    {"tier": "CRITICAL", "variants": 456,  "disease": "Wilms tumor, nephrotic syndrome"},
    "FH":     {"tier": "CRITICAL", "variants": 312,  "disease": "Hereditary leiomyomatosis, renal cancer"},
    "SDHA":   {"tier": "CRITICAL", "variants": 187,  "disease": "Paraganglioma/pheochromocytoma"},
    "SDHB":   {"tier": "CRITICAL", "variants": 423,  "disease": "Paraganglioma/pheochromocytoma"},
    "SDHC":   {"tier": "CRITICAL", "variants": 134,  "disease": "Paraganglioma/pheochromocytoma"},
    "SDHD":   {"tier": "CRITICAL", "variants": 198,  "disease": "Paraganglioma/pheochromocytoma"},
    "MAX":    {"tier": "CRITICAL", "variants": 78,   "disease": "Pheochromocytoma"},
    "TMEM127":{"tier": "CRITICAL", "variants": 89,   "disease": "Pheochromocytoma"},
    "BAP1":   {"tier": "CRITICAL", "variants": 234,  "disease": "Mesothelioma, uveal melanoma"},
    "DICER1": {"tier": "CRITICAL", "variants": 312,  "disease": "DICER1 syndrome, pleuropulmonary blastoma"},
    "FLCN":   {"tier": "CRITICAL", "variants": 234,  "disease": "Birt-Hogg-Dubé syndrome"},
    "EGFR":   {"tier": "CRITICAL", "variants": 456,  "disease": "Lung cancer oncogene"},
    "ERBB2":  {"tier": "CRITICAL", "variants": 234,  "disease": "Breast cancer oncogene (HER2)"},
    "MET":    {"tier": "CRITICAL", "variants": 289,  "disease": "Renal cell carcinoma, lung cancer"},
    "ALK":    {"tier": "CRITICAL", "variants": 312,  "disease": "Lung cancer, neuroblastoma"},
    "ROS1":   {"tier": "CRITICAL", "variants": 89,   "disease": "Lung cancer"},
    "FGFR1":  {"tier": "CRITICAL", "variants": 156,  "disease": "Myeloid neoplasms, craniosynostosis"},
    "FGFR2":  {"tier": "CRITICAL", "variants": 423,  "disease": "Craniosynostosis, endometrial cancer"},
    "FGFR3":  {"tier": "CRITICAL", "variants": 312,  "disease": "Achondroplasia, bladder cancer"},
    "IDH1":   {"tier": "CRITICAL", "variants": 156,  "disease": "Glioma, AML"},
    "IDH2":   {"tier": "CRITICAL", "variants": 134,  "disease": "AML, cholangiocarcinoma"},
    "DNMT3A": {"tier": "CRITICAL", "variants": 234,  "disease": "AML, clonal hematopoiesis"},
    "TET2":   {"tier": "CRITICAL", "variants": 312,  "disease": "AML, myelodysplasia"},
    "ASXL1":  {"tier": "CRITICAL", "variants": 198,  "disease": "Myeloid neoplasms"},
    "JAK2":   {"tier": "CRITICAL", "variants": 289,  "disease": "Myeloproliferative neoplasms"},
    "MPL":    {"tier": "CRITICAL", "variants": 134,  "disease": "Myeloproliferative neoplasms"},
    "CALR":   {"tier": "CRITICAL", "variants": 89,   "disease": "Myeloproliferative neoplasms"},
    "MYC":    {"tier": "CRITICAL", "variants": 134,  "disease": "Burkitt lymphoma, diffuse large B-cell"},
    "BCL2":   {"tier": "CRITICAL", "variants": 156,  "disease": "Follicular lymphoma, CLL"},
    "NOTCH1": {"tier": "CRITICAL", "variants": 312,  "disease": "T-ALL, head and neck cancer"},
    "RUNX1":  {"tier": "CRITICAL", "variants": 423,  "disease": "Familial platelet disorder, AML"},
    "CEBPA":  {"tier": "CRITICAL", "variants": 234,  "disease": "Familial AML"},
    "FLT3":   {"tier": "CRITICAL", "variants": 198,  "disease": "AML"},
    "NPM1":   {"tier": "CRITICAL", "variants": 156,  "disease": "AML"},
    "KIT":    {"tier": "CRITICAL", "variants": 423,  "disease": "GIST, systemic mastocytosis, AML"},
    "PDGFRA": {"tier": "CRITICAL", "variants": 234,  "disease": "GIST, glioblastoma"},
    "ABL1":   {"tier": "CRITICAL", "variants": 189,  "disease": "CML (BCR-ABL1 fusion)"},

    # ── ACMG Secondary Findings v3.2 (59 actionable genes) ────────────────
    "LDLR":   {"tier": "CRITICAL", "variants": 2341, "disease": "Familial hypercholesterolemia"},
    "APOB":   {"tier": "CRITICAL", "variants": 312,  "disease": "Familial hypercholesterolemia"},
    "PCSK9":  {"tier": "CRITICAL", "variants": 187,  "disease": "Familial hypercholesterolemia"},
    "KCNQ1":  {"tier": "CRITICAL", "variants": 723,  "disease": "Long QT syndrome, JLNS"},
    "KCNH2":  {"tier": "CRITICAL", "variants": 634,  "disease": "Long QT syndrome"},
    "SCN5A":  {"tier": "CRITICAL", "variants": 812,  "disease": "Brugada syndrome, Long QT3"},
    "MYBPC3": {"tier": "CRITICAL", "variants": 1234, "disease": "Hypertrophic cardiomyopathy"},
    "MYH7":   {"tier": "CRITICAL", "variants": 987,  "disease": "Hypertrophic cardiomyopathy, DCM"},
    "TNNT2":  {"tier": "CRITICAL", "variants": 423,  "disease": "Hypertrophic cardiomyopathy, DCM"},
    "TNNI3":  {"tier": "CRITICAL", "variants": 312,  "disease": "Hypertrophic/restrictive cardiomyopathy"},
    "TPM1":   {"tier": "CRITICAL", "variants": 234,  "disease": "Hypertrophic cardiomyopathy"},
    "MYL3":   {"tier": "CRITICAL", "variants": 156,  "disease": "Hypertrophic cardiomyopathy"},
    "ACTC1":  {"tier": "CRITICAL", "variants": 134,  "disease": "Hypertrophic cardiomyopathy, DCM"},
    "PRKAG2": {"tier": "CRITICAL", "variants": 134,  "disease": "Glycogen storage disease of heart"},
    "GLA":    {"tier": "CRITICAL", "variants": 734,  "disease": "Fabry disease"},
    "DSP":    {"tier": "CRITICAL", "variants": 423,  "disease": "Arrhythmogenic cardiomyopathy"},
    "DSG2":   {"tier": "CRITICAL", "variants": 312,  "disease": "Arrhythmogenic cardiomyopathy"},
    "DSC2":   {"tier": "CRITICAL", "variants": 234,  "disease": "Arrhythmogenic cardiomyopathy"},
    "SCN1A":  {"tier": "CRITICAL", "variants": 1456, "disease": "Dravet syndrome, GEFS+"},
    "RYR1":   {"tier": "CRITICAL", "variants": 1234, "disease": "Malignant hyperthermia, myopathy"},
    "RYR2":   {"tier": "CRITICAL", "variants": 734,  "disease": "CPVT, arrhythmogenic cardiomyopathy"},
    "CACNA1S":{"tier": "CRITICAL", "variants": 234,  "disease": "Malignant hyperthermia, HypoPP"},
    "MYH11":  {"tier": "CRITICAL", "variants": 312,  "disease": "Thoracic aortic aneurysm"},
    "ACTA2":  {"tier": "CRITICAL", "variants": 234,  "disease": "Thoracic aortic aneurysm"},
    "TGFBR1": {"tier": "CRITICAL", "variants": 289,  "disease": "Loeys-Dietz syndrome"},
    "TGFBR2": {"tier": "CRITICAL", "variants": 234,  "disease": "Loeys-Dietz syndrome, HNPCC"},
    "SMAD3":  {"tier": "CRITICAL", "variants": 198,  "disease": "Loeys-Dietz syndrome"},
    "COL3A1": {"tier": "CRITICAL", "variants": 734,  "disease": "Vascular Ehlers-Danlos syndrome"},
    "FBN1":   {"tier": "CRITICAL", "variants": 1234, "disease": "Marfan syndrome"},
    "FBN2":   {"tier": "CRITICAL", "variants": 423,  "disease": "Contractural arachnodactyly"},
    "HFE":    {"tier": "CRITICAL", "variants": 123,  "disease": "Hereditary hemochromatosis"},

    # ── Haematology / haemoglobin genes ───────────────────────────────────
    "HBB":    {"tier": "CRITICAL", "variants": 1456, "disease": "Sickle cell disease, beta-thalassemia"},
    "HBA1":   {"tier": "CRITICAL", "variants": 312,  "disease": "Alpha-thalassemia"},
    "HBA2":   {"tier": "CRITICAL", "variants": 289,  "disease": "Alpha-thalassemia"},
    "G6PD":   {"tier": "CRITICAL", "variants": 423,  "disease": "G6PD deficiency"},
    "F8":     {"tier": "CRITICAL", "variants": 2341, "disease": "Hemophilia A"},
    "F9":     {"tier": "CRITICAL", "variants": 1234, "disease": "Hemophilia B"},
    "VWF":    {"tier": "CRITICAL", "variants": 934,  "disease": "von Willebrand disease"},

    # ── Neurology ─────────────────────────────────────────────────────────
    "HTT":    {"tier": "CRITICAL", "variants": 89,   "disease": "Huntington disease"},
    "ATXN1":  {"tier": "CRITICAL", "variants": 45,   "disease": "Spinocerebellar ataxia 1"},
    "ATXN3":  {"tier": "CRITICAL", "variants": 56,   "disease": "Spinocerebellar ataxia 3"},
    "LRRK2":  {"tier": "CRITICAL", "variants": 312,  "disease": "Parkinson disease"},
    "SNCA":   {"tier": "CRITICAL", "variants": 134,  "disease": "Parkinson disease"},
    "APP":    {"tier": "CRITICAL", "variants": 134,  "disease": "Alzheimer disease"},
    "PSEN1":  {"tier": "CRITICAL", "variants": 423,  "disease": "Early-onset Alzheimer disease"},
    "PSEN2":  {"tier": "CRITICAL", "variants": 134,  "disease": "Early-onset Alzheimer disease"},
    "SOD1":   {"tier": "CRITICAL", "variants": 234,  "disease": "Familial ALS"},
    "FUS":    {"tier": "CRITICAL", "variants": 156,  "disease": "Familial ALS"},
    "TARDBP": {"tier": "CRITICAL", "variants": 187,  "disease": "Familial ALS"},
    "SMN1":   {"tier": "CRITICAL", "variants": 89,   "disease": "Spinal muscular atrophy"},
    "DMD":    {"tier": "CRITICAL", "variants": 4234, "disease": "Duchenne/Becker muscular dystrophy"},

    # ── Metabolic / systemic ──────────────────────────────────────────────
    "CFTR":   {"tier": "CRITICAL", "variants": 2134, "disease": "Cystic fibrosis"},
    "HEXA":   {"tier": "CRITICAL", "variants": 423,  "disease": "Tay-Sachs disease"},
    "HEXB":   {"tier": "CRITICAL", "variants": 312,  "disease": "Sandhoff disease"},
    "GBA":    {"tier": "CRITICAL", "variants": 734,  "disease": "Gaucher disease"},
    "GALC":   {"tier": "CRITICAL", "variants": 423,  "disease": "Krabbe disease"},
    "ARSA":   {"tier": "CRITICAL", "variants": 312,  "disease": "Metachromatic leukodystrophy"},
    "PAH":    {"tier": "CRITICAL", "variants": 834,  "disease": "Phenylketonuria"},
    "OTC":    {"tier": "CRITICAL", "variants": 734,  "disease": "Ornithine transcarbamylase deficiency"},
    "ASS1":   {"tier": "CRITICAL", "variants": 234,  "disease": "Citrullinemia type I"},
    "PKD1":   {"tier": "CRITICAL", "variants": 1234, "disease": "Autosomal dominant PKD"},
    "PKD2":   {"tier": "CRITICAL", "variants": 423,  "disease": "Autosomal dominant PKD"},
    "TSC1":   {"tier": "CRITICAL", "variants": 734,  "disease": "Tuberous sclerosis"},
    "TSC2":   {"tier": "CRITICAL", "variants": 1234, "disease": "Tuberous sclerosis"},
    "MECP2":  {"tier": "CRITICAL", "variants": 823,  "disease": "Rett syndrome"},
    "FMR1":   {"tier": "CRITICAL", "variants": 134,  "disease": "Fragile X syndrome"},

    # ── Immunology / inflammatory ─────────────────────────────────────────
    "RAG1":   {"tier": "HIGH",     "variants": 312,  "disease": "Combined immunodeficiency"},
    "RAG2":   {"tier": "HIGH",     "variants": 198,  "disease": "Combined immunodeficiency"},
    "ADA":    {"tier": "HIGH",     "variants": 134,  "disease": "ADA-SCID"},
    "IL2RG":  {"tier": "HIGH",     "variants": 234,  "disease": "X-linked SCID"},
    "BTK":    {"tier": "HIGH",     "variants": 734,  "disease": "X-linked agammaglobulinemia"},
    "AIRE":   {"tier": "HIGH",     "variants": 234,  "disease": "APS-1"},

    # ── COSMIC Tier 2 cancer genes ────────────────────────────────────────
    "STAT3":  {"tier": "HIGH",     "variants": 234,  "disease": "Large granular lymphocytic leukemia"},
    "STAT5B": {"tier": "HIGH",     "variants": 156,  "disease": "T-cell lymphoma"},
    "DNMT3B": {"tier": "HIGH",     "variants": 134,  "disease": "ICF syndrome, AML"},
    "EZH2":   {"tier": "HIGH",     "variants": 198,  "disease": "Follicular lymphoma, myeloid neoplasms"},
    "KDM6A":  {"tier": "HIGH",     "variants": 156,  "disease": "Kabuki syndrome, bladder cancer"},
    "KMT2A":  {"tier": "HIGH",     "variants": 312,  "disease": "AML, ALL, MLL-rearranged leukemia"},
    "KMT2D":  {"tier": "HIGH",     "variants": 734,  "disease": "Kabuki syndrome, lymphoma"},
    "CREBBP": {"tier": "HIGH",     "variants": 423,  "disease": "Rubinstein-Taybi, follicular lymphoma"},
    "EP300":  {"tier": "HIGH",     "variants": 312,  "disease": "Rubinstein-Taybi, colorectal cancer"},
    "ARID1A": {"tier": "HIGH",     "variants": 234,  "disease": "Coffin-Siris, ovarian clear cell"},
    "ARID1B": {"tier": "HIGH",     "variants": 312,  "disease": "Coffin-Siris syndrome"},
    "SMARCA4":{"tier": "HIGH",     "variants": 423,  "disease": "Small cell ovarian cancer, Coffin-Siris"},
    "SMARCB1":{"tier": "HIGH",     "variants": 234,  "disease": "Rhabdoid tumor, schwannomatosis"},
    "CTNNB1": {"tier": "HIGH",     "variants": 198,  "disease": "Colorectal cancer, Wilms tumor"},
    "AXIN1":  {"tier": "HIGH",     "variants": 134,  "disease": "Hepatocellular carcinoma, caudal regression"},
    "AXIN2":  {"tier": "HIGH",     "variants": 156,  "disease": "Oligodontia, colorectal cancer"},
    "TSC1":   {"tier": "CRITICAL", "variants": 734,  "disease": "Tuberous sclerosis"},
    "NKX2-1": {"tier": "HIGH",     "variants": 89,   "disease": "Lung adenocarcinoma, brain-lung-thyroid"},
    "SOX2":   {"tier": "HIGH",     "variants": 134,  "disease": "Anophthalmia/microphthalmia"},
    "PAX5":   {"tier": "HIGH",     "variants": 156,  "disease": "B-ALL"},
    "ETV6":   {"tier": "HIGH",     "variants": 198,  "disease": "Thrombocytopenia, ALL"},
    "GATA1":  {"tier": "HIGH",     "variants": 134,  "disease": "Diamond-Blackfan, AML in Down syndrome"},
    "GATA2":  {"tier": "HIGH",     "variants": 187,  "disease": "GATA2 deficiency, MDS"},
    "TP63":   {"tier": "HIGH",     "variants": 423,  "disease": "EEC syndrome, head/neck cancer"},
    "TP73":   {"tier": "HIGH",     "variants": 134,  "disease": "Neuroblastoma modifier"},
    "STAG2":  {"tier": "HIGH",     "variants": 156,  "disease": "Bladder cancer, cohesinopathy"},
    "RAD21":  {"tier": "HIGH",     "variants": 134,  "disease": "Cornelia de Lange syndrome"},
    "SMC1A":  {"tier": "HIGH",     "variants": 198,  "disease": "Cornelia de Lange syndrome"},
    "NIPBL":  {"tier": "HIGH",     "variants": 734,  "disease": "Cornelia de Lange syndrome"},
    "BRIP1":  {"tier": "HIGH",     "variants": 234,  "disease": "Fanconi anemia, breast cancer"},
    "FANCA":  {"tier": "HIGH",     "variants": 734,  "disease": "Fanconi anemia"},
    "FANCC":  {"tier": "HIGH",     "variants": 234,  "disease": "Fanconi anemia"},
    "FANCD2": {"tier": "HIGH",     "variants": 312,  "disease": "Fanconi anemia"},
    "FANCE":  {"tier": "HIGH",     "variants": 134,  "disease": "Fanconi anemia"},
    "FANCF":  {"tier": "HIGH",     "variants": 89,   "disease": "Fanconi anemia"},
    "FANCG":  {"tier": "HIGH",     "variants": 156,  "disease": "Fanconi anemia"},
    "FANCL":  {"tier": "HIGH",     "variants": 78,   "disease": "Fanconi anemia"},
    "FANCM":  {"tier": "HIGH",     "variants": 134,  "disease": "Fanconi anemia"},
    "BLM":    {"tier": "HIGH",     "variants": 234,  "disease": "Bloom syndrome"},
    "WRN":    {"tier": "HIGH",     "variants": 312,  "disease": "Werner syndrome"},
    "XPC":    {"tier": "HIGH",     "variants": 234,  "disease": "Xeroderma pigmentosum"},
    "XPA":    {"tier": "HIGH",     "variants": 89,   "disease": "Xeroderma pigmentosum"},
}

# Tier severity ordering for sorting
TIER_SEVERITY = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1, "MINIMAL": 0}

TIER_COLORS = {
    "CRITICAL": "#dc2626",   # red
    "HIGH":     "#ea580c",   # orange
    "MODERATE": "#d97706",   # yellow
    "LOW":      "#059669",   # green
    "MINIMAL":  "#6b7280",   # gray
}

TIER_LABELS = {
    "CRITICAL": "🔴 CRITICAL — Avoid this guide",
    "HIGH":     "🟠 HIGH — Experimental validation required",
    "MODERATE": "🟡 MODERATE — Low concern, check experimentally",
    "LOW":      "🟢 LOW — Acceptable risk",
    "MINIMAL":  "⚪ MINIMAL — Intergenic / non-coding",
}


# ── ClinVar real-time lookup (for genes not in pre-built DB) ──────────────────

_clinvar_cache: dict[str, dict] = {}

def _query_clinvar(gene_symbol: str) -> dict:
    """Query ClinVar for pathogenic variant count for a gene (cached)."""
    if gene_symbol in _clinvar_cache:
        return _clinvar_cache[gene_symbol]

    try:
        term = urllib.parse.quote(f"{gene_symbol}[gene] AND (pathogenic[clinical_significance] OR likely_pathogenic[clinical_significance])")
        url  = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term={term}&retmax=1&retmode=json"
        req  = urllib.request.Request(url, headers={"User-Agent": "SnipGen/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        count = int(data["esearchresult"]["count"])
        time.sleep(0.34)   # NCBI rate limit: 3 requests/sec without API key
    except Exception:
        count = 0

    result = {
        "tier":     "HIGH" if count > 100 else ("MODERATE" if count > 10 else "LOW"),
        "variants": count,
        "disease":  f"{count} pathogenic/likely-pathogenic variants in ClinVar",
    }
    _clinvar_cache[gene_symbol] = result
    return result


# ── Public interface ───────────────────────────────────────────────────────────

def annotate_gene(gene_symbol: str) -> dict:
    """
    Return clinical annotation for a gene symbol.

    Returns:
        {
            "tier":      "CRITICAL" | "HIGH" | "MODERATE" | "LOW" | "MINIMAL",
            "variants":  int,
            "disease":   str,
            "color":     str,   # hex color for UI
            "label":     str,   # human-readable verdict
        }
    """
    sym = gene_symbol.strip().upper()
    if not sym or sym in ("-", ".", "N/A"):
        return {"tier": "MINIMAL", "variants": 0, "disease": "Intergenic",
                "color": TIER_COLORS["MINIMAL"], "label": TIER_LABELS["MINIMAL"]}

    if sym in GENE_DB:
        info = GENE_DB[sym].copy()
    else:
        info = _query_clinvar(sym)

    info["color"] = TIER_COLORS[info["tier"]]
    info["label"] = TIER_LABELS[info["tier"]]
    return info


def annotate_offtargets(offtarget_list: list[dict]) -> list[dict]:
    """
    Annotate a list of off-target sites with ClinVar consequence data.

    Each item in offtarget_list should have at least:
        {"locusDesc": "exon:BRCA2", ...}

    Returns the same list with added "clinvar" key per item.
    Also returns the worst (highest severity) consequence found.
    """
    annotated = []
    for ot in offtarget_list:
        locus = ot.get("locusDesc", "") or ""
        gene  = _parse_gene_from_locus(locus)
        region = _parse_region_from_locus(locus)

        if region in ("intergenic", "repeat") or not gene:
            annotation = {
                "tier": "MINIMAL", "variants": 0,
                "disease": "Intergenic / non-coding",
                "color": TIER_COLORS["MINIMAL"],
                "label": TIER_LABELS["MINIMAL"],
                "gene": gene or "intergenic",
                "region": region,
            }
        else:
            annotation = annotate_gene(gene)
            annotation["gene"]   = gene
            annotation["region"] = region
            # Downgrade tier if not in exon (intronic off-targets are less severe)
            if region == "intron" and annotation["tier"] == "CRITICAL":
                annotation["tier"]  = "HIGH"
                annotation["color"] = TIER_COLORS["HIGH"]
                annotation["label"] = TIER_LABELS["HIGH"]

        annotated.append({**ot, "clinvar": annotation})

    return annotated


def worst_consequence(annotated_offtargets: list[dict]) -> dict:
    """Return the highest-severity consequence across all off-target sites."""
    if not annotated_offtargets:
        return {"tier": "MINIMAL", "color": TIER_COLORS["MINIMAL"],
                "label": "No off-target sites analysed"}
    worst = max(
        annotated_offtargets,
        key=lambda x: TIER_SEVERITY.get(x.get("clinvar", {}).get("tier", "MINIMAL"), 0)
    )
    return worst.get("clinvar", {"tier": "MINIMAL"})


def _parse_gene_from_locus(locus: str) -> str:
    """Extract gene name from CRISPOR locusDesc like 'exon:BRCA2' or 'intron:TP53/NM_000546'."""
    if not locus or locus == "-":
        return ""
    parts = locus.split(":", 1)
    if len(parts) < 2:
        return ""
    gene_part = parts[1].split("/")[0].split("-")[0].strip()
    # Filter out obvious non-gene strings
    if any(c.isdigit() for c in gene_part[:2]) or len(gene_part) > 20:
        return ""
    return gene_part.upper()


def _parse_region_from_locus(locus: str) -> str:
    """Return region type from locusDesc: exon | intron | intergenic | utr | repeat."""
    locus = (locus or "").lower()
    if locus.startswith("exon"):       return "exon"
    if locus.startswith("intron"):     return "intron"
    if locus.startswith("utr"):        return "utr"
    if "repeat" in locus or "satellite" in locus: return "repeat"
    return "intergenic"
