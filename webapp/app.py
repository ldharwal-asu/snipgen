"""SnipGen FastAPI web application — async job queue edition."""

import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse

from snipgen.analysis.base_editor import analyze_base_editing
from snipgen.analysis.cloning_primers import design_cloning_oligos, design_all_vectors
from snipgen.analysis.isoform_analyzer import analyze_guide_isoforms
from snipgen.filters.gnomad_filter import check_guide_gnomad
from snipgen.filters.pam_filter import PAM_REGISTRY
from snipgen.pipeline import PipelineConfig, SnipGenPipeline
from snipgen.scoring.clinvar_annotator import annotate_gene as clinvar_annotate_gene
from webapp.crispor_client import (
    submit_sequence as crispor_submit,
    fetch_scores as crispor_fetch,
    crispor_to_offtarget_score,
)
from webapp.job_queue import queue, JobStatus

app = FastAPI(title="SnipGen", description="AI-driven CRISPR guide RNA design")

_static = Path(__file__).resolve().parent / "static"
_ENTREZ_EMAIL = "snipgen-tool@noreply.asu.edu"

_GENE_ACCESSIONS: dict[str, dict[str, str]] = {
    "human": {
        "TP53":  "NM_000546", "BRCA1": "NM_007294", "BRCA2": "NM_000059",
        "EGFR":  "NM_005228", "KRAS":  "NM_004985", "PTEN":  "NM_000314",
        "MYC":   "NM_002467", "VEGFA": "NM_001171627", "PCSK9": "NM_174936",
        "HBB":   "NM_000518", "DMD":   "NM_004006",  "CFTR":  "NM_000492",
        "APOE":  "NM_000041", "ACE2":  "NM_021804",  "STAT3": "NM_139276",
    },
    "mouse": {
        "Trp53": "NM_011640", "Brca1": "NM_009764", "Kras": "NM_021284",
        "Egfr":  "NM_207655", "Myc":   "NM_010849", "Hbb":  "NM_008220",
        "Dmd":   "NM_007868",
    },
}

ORGANISM_TAXIDS = {
    "human": "9606", "mouse": "10090", "zebrafish": "7955",
    "rat": "10116", "drosophila": "7227", "c_elegans": "6239",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fetch_sequence_entrez(gene: str, organism: str) -> tuple[str, str]:
    from Bio import Entrez
    Entrez.email = _ENTREZ_EMAIL
    Entrez.tool  = "snipgen"
    org_lower    = organism.lower()
    gene_upper   = gene.upper()
    accession: Optional[str] = None

    if org_lower in _GENE_ACCESSIONS and gene_upper in _GENE_ACCESSIONS[org_lower]:
        accession = _GENE_ACCESSIONS[org_lower][gene_upper]

    if accession is None:
        taxid = ORGANISM_TAXIDS.get(org_lower, "9606")
        term = f"{gene}[Gene Name] AND {taxid}[Taxonomy ID] AND mRNA[Filter] AND RefSeq[Filter]"
        try:
            h = Entrez.esearch(db="nuccore", term=term, retmax=5)
            rec = Entrez.read(h); h.close()
        except Exception as exc:
            raise ValueError(f"NCBI search failed: {exc}")
        ids = rec.get("IdList", [])
        if not ids:
            raise ValueError(f"No RefSeq mRNA found for '{gene}' in {organism}.")
        accession = ids[0]

    try:
        h = Entrez.efetch(db="nuccore", id=accession, rettype="fasta", retmode="text")
        fasta = h.read(); h.close()
    except Exception as exc:
        raise ValueError(f"NCBI fetch failed for {accession}: {exc}")

    if not fasta.strip():
        raise ValueError(f"Empty sequence for {accession}.")
    return fasta, accession


def _run_pipeline(fasta_bytes: bytes, cas_variant: str, guide_length: int,
                  min_gc: float, max_gc: float, top_n: int,
                  organism: str, gene_symbol: str = "") -> dict:
    """
    Run the full SnipGen pipeline. Executed in a background thread by job_queue.
    Returns the JSON-serialisable result dict.
    """
    fasta_text = fasta_bytes.decode("utf-8", errors="replace")

    with tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode="wb") as tmp:
        tmp.write(fasta_bytes)
        tmp_path = Path(tmp.name)

    crispor_batch_id: Optional[str] = None

    try:
        with tempfile.TemporaryDirectory() as out_dir:
            config = PipelineConfig(
                fasta_path=tmp_path,
                output_dir=out_dir,
                output_formats=["json"],
                cas_variant=cas_variant,
                guide_length=guide_length,
                min_gc=min_gc,
                max_gc=max_gc,
                top_n=top_n,
            )
            pipeline = SnipGenPipeline(config)
            pipeline.run()
            output = json.loads((Path(out_dir) / "candidates.json").read_text())

        gene = (gene_symbol or "").strip().upper()
        candidates = output.get("candidates", [])

        # ── Base editing analysis (always run — pure sequence analysis) ───────
        for c in candidates:
            seq    = c.get("sequence", "")
            strand = c.get("strand", "+")
            try:
                c["base_edit"] = analyze_base_editing(seq, strand)
            except Exception:
                pass

        # ── Cloning primers (always run — pure sequence, no network) ──────────
        for c in candidates:
            seq = c.get("sequence", "")
            try:
                c["cloning"] = design_all_vectors(seq)
            except Exception:
                pass

        # ── ClinVar gene annotation (gene-search mode) ────────────────────────
        if gene:
            try:
                c_ann = clinvar_annotate_gene(gene)
                output["clinvar_gene"] = c_ann
            except Exception:
                output["clinvar_gene"] = {}

        # ── gnomAD + isoform annotation (gene-search mode, human only) ────────
        if gene and organism.lower() == "human":
            for c in candidates:
                seq    = c.get("sequence", "")
                start  = c.get("start", 0)
                end    = c.get("end", start + len(seq))
                strand = c.get("strand", "+")

                try:
                    c["gnomad"] = check_guide_gnomad(
                        guide_seq=seq,
                        gene_symbol=gene,
                        guide_start_in_mrna=start,
                        guide_end_in_mrna=end,
                        strand=strand,
                        organism=organism,
                    )
                except Exception:
                    c["gnomad"] = {"gnomad_checked": False, "flag": "gnomAD check failed"}

            # Isoform — cap at top 8 guides (transcript FASTA cached after first)
            for c in candidates[:8]:
                seq = c.get("sequence", "")
                try:
                    c["isoform"] = analyze_guide_isoforms(
                        guide_seq=seq,
                        gene_symbol=gene,
                        organism=organism,
                    )
                except Exception:
                    c["isoform"] = {"isoform_checked": False, "flag": "Isoform check failed"}

        # ── CRISPOR submission (fire-and-forget) ──────────────────────────────
        try:
            crispor_batch_id = crispor_submit(fasta_text, organism, cas_variant)
        except Exception:
            crispor_batch_id = None

        output["crispor_batch_id"] = crispor_batch_id
        output["crispor_genome"]   = organism
        output["gene_symbol"]      = gene
        return output

    finally:
        tmp_path.unlink(missing_ok=True)


def _run_batch_pipeline(
    gene_list: list[str],
    organism: str,
    cas_variant: str,
    top_n: int,
) -> dict:
    """
    Batch design: fetch sequences for each gene and run pipeline.
    Returns combined results with per-gene candidate lists.
    """
    results: dict[str, dict] = {}

    for gene in gene_list[:10]:   # hard cap at 10 genes per batch
        gene = gene.strip().upper()
        if not gene:
            continue
        try:
            fasta_text, accession = _fetch_sequence_entrez(gene, organism)
            fasta_bytes = fasta_text.encode()
            gene_result = _run_pipeline(
                fasta_bytes=fasta_bytes,
                cas_variant=cas_variant,
                guide_length=20,
                min_gc=0.40,
                max_gc=0.70,
                top_n=top_n,
                organism=organism,
                gene_symbol=gene,
            )
            gene_result["gene"] = gene
            gene_result["accession"] = accession
            results[gene] = gene_result
        except Exception as exc:
            results[gene] = {"gene": gene, "error": str(exc), "candidates": []}

    return {"batch": True, "genes": list(results.keys()), "results": results}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return (_static / "index.html").read_text()


@app.get("/variants")
async def list_variants():
    return {
        v: {"pattern": cfg["pattern"], "position": cfg["position"]}
        for v, cfg in PAM_REGISTRY.items()
    }


@app.get("/fetch-gene")
async def fetch_gene(
    gene: str = Query(...),
    organism: str = Query("human"),
):
    gene = gene.strip()
    if not gene or len(gene) > 50:
        raise HTTPException(400, "Invalid gene name")
    try:
        fasta_text, accession = _fetch_sequence_entrez(gene, organism)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Unexpected error: {exc}")

    seq_len = len("".join(
        l.strip() for l in fasta_text.splitlines() if not l.startswith(">")
    ))
    return JSONResponse({
        "gene": gene, "organism": organism,
        "accession": accession, "fasta": fasta_text, "length": seq_len,
    })


@app.post("/design")
async def design(
    file: UploadFile = File(...),
    cas_variant: str = Query("SpCas9"),
    guide_length: int = Query(20, ge=17, le=25),
    min_gc: float = Query(0.40, ge=0.0, le=1.0),
    max_gc: float = Query(0.70, ge=0.0, le=1.0),
    top_n: int = Query(20, ge=1, le=200),
    organism: str = Query("human"),
    gene_symbol: str = Query("", description="Gene symbol for gnomAD/isoform/ClinVar annotation"),
):
    """
    Accept a FASTA upload, queue the pipeline, return a job_id immediately.
    Client polls GET /job/{job_id} for status + results.
    """
    if cas_variant not in PAM_REGISTRY:
        raise HTTPException(400, f"Unknown Cas variant '{cas_variant}'")
    if min_gc >= max_gc:
        raise HTTPException(400, "min_gc must be less than max_gc")

    fasta_bytes = await file.read()
    if len(fasta_bytes) == 0:
        raise HTTPException(400, "Empty file uploaded")

    text_preview = fasta_bytes[:200].decode("utf-8", errors="replace")
    if not any(c in text_preview for c in (">", "A", "C", "G", "T", "a", "c", "g", "t")):
        raise HTTPException(400, "File does not appear to be a valid FASTA")

    job_id = queue.submit(
        _run_pipeline,
        fasta_bytes, cas_variant, guide_length, min_gc, max_gc, top_n, organism, gene_symbol,
    )

    return JSONResponse({"job_id": job_id, "status": "queued"}, status_code=202)


@app.post("/batch-design")
async def batch_design(
    genes: str = Query(..., description="Comma-separated gene symbols (max 10)"),
    organism: str = Query("human"),
    cas_variant: str = Query("SpCas9"),
    top_n: int = Query(5, ge=1, le=20),
):
    """
    Batch design mode: design guides for multiple genes at once.
    Accepts comma-separated gene symbols, returns job_id.
    """
    gene_list = [g.strip() for g in genes.split(",") if g.strip()][:10]
    if not gene_list:
        raise HTTPException(400, "No valid gene symbols provided")
    if cas_variant not in PAM_REGISTRY:
        raise HTTPException(400, f"Unknown Cas variant '{cas_variant}'")

    job_id = queue.submit(
        _run_batch_pipeline,
        gene_list, organism, cas_variant, top_n,
    )

    return JSONResponse({
        "job_id": job_id,
        "status": "queued",
        "genes": gene_list,
        "mode": "batch",
    }, status_code=202)


@app.get("/job/{job_id}")
async def job_status(job_id: str):
    """
    Poll for pipeline job status.

    Response shapes:
      {"status": "queued",  "progress": "Queued…",  "elapsed_s": 0.1}
      {"status": "running", "progress": "Scoring…", "elapsed_s": 3.4}
      {"status": "done",    "result": {...},         "elapsed_s": 8.1}
      {"status": "failed",  "error": "...",          "elapsed_s": 2.0}
    """
    job = queue.get(job_id)
    if not job:
        raise HTTPException(404, f"Job '{job_id}' not found (may have expired)")
    return JSONResponse(job.to_dict())


@app.get("/crispor-scores")
async def crispor_scores(
    batch_id: str = Query(...),
    gene_symbol: str = Query("", description="Gene symbol for ClinVar off-target annotation"),
):
    """Poll CRISPOR for real off-target results, annotated with ClinVar data."""
    if not batch_id or not batch_id.replace("-", "").replace("_", "").isalnum() or len(batch_id) > 30:
        raise HTTPException(400, "Invalid batch_id")

    scores = crispor_fetch(batch_id)
    if scores is None:
        return JSONResponse({"status": "pending"})

    converted = {}
    for seq, data in scores.items():
        entry = {**data, "snipgen_offtarget_score": crispor_to_offtarget_score(data)}

        # ClinVar annotation: annotate the gene locus of off-target hits
        locus = data.get("gene_locus", "")
        if locus and locus != "—":
            # locus format: "exon:GENENAME" or "intron:GENENAME"
            parts = locus.split(":")
            gene_name = parts[-1].strip() if len(parts) >= 2 else ""
            if gene_name:
                try:
                    gene_ann = clinvar_annotate_gene(gene_name)
                    entry["clinvar_offtarget"] = {
                        "gene":   gene_name,
                        "tier":   gene_ann.get("tier", "MINIMAL"),
                        "variants": gene_ann.get("variants", 0),
                        "disease": gene_ann.get("disease", ""),
                        "color":  gene_ann.get("color", "#9ca3af"),
                        "label":  gene_ann.get("label", ""),
                    }
                except Exception:
                    pass

        converted[seq] = entry

    return JSONResponse({"status": "ready", "scores": converted})


@app.get("/cloning-primers")
async def cloning_primers(
    guide: str = Query(..., description="20-mer guide sequence (no PAM)"),
    vector: str = Query("pX330"),
):
    """Generate cloning oligos for a single guide + vector combination."""
    guide = guide.strip().upper()
    if len(guide) < 17 or len(guide) > 25:
        raise HTTPException(400, "Guide must be 17-25 nt")
    if any(n not in "ACGTN" for n in guide):
        raise HTTPException(400, "Guide must contain only ACGTN")
    return JSONResponse(design_cloning_oligos(guide, vector))


@app.get("/base-edit")
async def base_edit(
    guide: str = Query(..., description="20-mer guide sequence (no PAM)"),
    strand: str = Query("+"),
):
    """Analyze a guide for base editing suitability (CBE/ABE)."""
    guide = guide.strip().upper()
    if len(guide) < 17:
        raise HTTPException(400, "Guide must be ≥17 nt")
    return JSONResponse(analyze_base_editing(guide, strand))
