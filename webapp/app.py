"""SnipGen FastAPI web application."""

import io
import json
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from snipgen.filters.pam_filter import PAM_REGISTRY
from snipgen.pipeline import PipelineConfig, SnipGenPipeline

app = FastAPI(title="SnipGen", description="AI-driven CRISPR guide RNA design")

# Resolve the static directory relative to this file so it works on any host
_static = Path(__file__).resolve().parent / "static"

# NCBI Entrez email (required by NCBI policy — identifies the tool)
_ENTREZ_EMAIL = "snipgen-tool@noreply.asu.edu"

# Gene → RefSeq mRNA accession for well-known human/mouse genes
# Used as a fast-path before falling back to Entrez search
_GENE_ACCESSIONS: dict[str, dict[str, str]] = {
    "human": {
        "TP53":   "NM_000546",
        "BRCA1":  "NM_007294",
        "BRCA2":  "NM_000059",
        "EGFR":   "NM_005228",
        "KRAS":   "NM_004985",
        "PTEN":   "NM_000314",
        "MYC":    "NM_002467",
        "VEGFA":  "NM_001171627",
        "PCSK9":  "NM_174936",
        "HBB":    "NM_000518",
        "DMD":    "NM_004006",
        "CFTR":   "NM_000492",
        "APOE":   "NM_000041",
        "ACE2":   "NM_021804",
        "STAT3":  "NM_139276",
    },
    "mouse": {
        "Trp53":  "NM_011640",
        "Brca1":  "NM_009764",
        "Kras":   "NM_021284",
        "Egfr":   "NM_207655",
        "Myc":    "NM_010849",
        "Hbb":    "NM_008220",
        "Dmd":    "NM_007868",
    },
}

ORGANISM_TAXIDS = {
    "human": "9606",
    "mouse": "10090",
    "zebrafish": "7955",
    "rat": "10116",
    "drosophila": "7227",
    "c_elegans": "6239",
}


def _fetch_sequence_entrez(gene: str, organism: str) -> tuple[str, str]:
    """
    Fetch mRNA/CDS sequence for a gene via NCBI Entrez.

    Returns (fasta_text, accession) or raises ValueError with a user-friendly message.

    Strategy:
      1. Check _GENE_ACCESSIONS fast-path (known human/mouse genes)
      2. Fall back to Entrez esearch on gene symbol + organism
      3. Fetch first hit via efetch (FASTA format)
      4. Trim to coding sequence region if CDS annotation present
    """
    from Bio import Entrez, SeqIO
    Entrez.email = _ENTREZ_EMAIL
    Entrez.tool  = "snipgen"

    accession: Optional[str] = None

    # Fast-path lookup
    org_lower = organism.lower()
    gene_upper = gene.upper()
    if org_lower in _GENE_ACCESSIONS and gene_upper in _GENE_ACCESSIONS[org_lower]:
        accession = _GENE_ACCESSIONS[org_lower][gene_upper]

    # Entrez search fallback
    if accession is None:
        taxid = ORGANISM_TAXIDS.get(org_lower, "9606")
        search_term = f"{gene}[Gene Name] AND {taxid}[Taxonomy ID] AND mRNA[Filter] AND RefSeq[Filter]"
        try:
            handle = Entrez.esearch(db="nuccore", term=search_term, retmax=5)
            record = Entrez.read(handle)
            handle.close()
        except Exception as exc:
            raise ValueError(f"NCBI search failed: {exc}. Check your internet connection.")

        ids = record.get("IdList", [])
        if not ids:
            raise ValueError(
                f"No RefSeq mRNA found for '{gene}' in {organism}. "
                "Check the gene symbol spelling (e.g. 'TP53' not 'tp53')."
            )
        accession = ids[0]  # best hit

    # Fetch FASTA
    try:
        handle = Entrez.efetch(db="nuccore", id=accession, rettype="fasta", retmode="text")
        fasta_text = handle.read()
        handle.close()
    except Exception as exc:
        raise ValueError(f"NCBI sequence fetch failed for {accession}: {exc}")

    if not fasta_text.strip():
        raise ValueError(f"Empty sequence returned for {accession}.")

    return fasta_text, accession


@app.get("/", response_class=HTMLResponse)
async def root():
    return (_static / "index.html").read_text()


@app.get("/variants")
async def list_variants():
    """Return all supported Cas variants."""
    return {
        variant: {
            "pattern": cfg["pattern"],
            "position": cfg["position"],
        }
        for variant, cfg in PAM_REGISTRY.items()
    }


@app.get("/fetch-gene")
async def fetch_gene(
    gene: str = Query(..., description="Gene symbol e.g. TP53"),
    organism: str = Query("human", description="Organism: human, mouse, zebrafish, rat"),
):
    """
    Fetch a gene's mRNA sequence from NCBI and return it as FASTA text.
    Used by the frontend to auto-populate the sequence input.
    """
    gene = gene.strip()
    if not gene:
        raise HTTPException(400, "gene parameter is required")
    if len(gene) > 50:
        raise HTTPException(400, "Gene name too long")

    try:
        fasta_text, accession = _fetch_sequence_entrez(gene, organism)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Unexpected error fetching gene: {exc}")

    return JSONResponse({
        "gene":      gene,
        "organism":  organism,
        "accession": accession,
        "fasta":     fasta_text,
        "length":    len(fasta_text.split("\n", 1)[-1].replace("\n", "")),
    })


@app.post("/design")
async def design(
    file: UploadFile = File(None, description="FASTA file (optional if gene_fasta provided)"),
    gene_fasta: Optional[str] = Query(None, description="Raw FASTA text from /fetch-gene"),
    cas_variant: str = Query("SpCas9"),
    guide_length: int = Query(20, ge=17, le=25),
    min_gc: float = Query(0.40, ge=0.0, le=1.0),
    max_gc: float = Query(0.70, ge=0.0, le=1.0),
    top_n: int = Query(20, ge=1, le=200),
):
    """Run the SnipGen pipeline on an uploaded FASTA file or inline FASTA text."""
    if cas_variant not in PAM_REGISTRY:
        raise HTTPException(400, f"Unknown Cas variant '{cas_variant}'")
    if min_gc >= max_gc:
        raise HTTPException(400, "min_gc must be less than max_gc")
    if file is None and not gene_fasta:
        raise HTTPException(400, "Provide either a file upload or gene_fasta text")

    # Write FASTA to temp file (from upload or inline text)
    with tempfile.NamedTemporaryFile(suffix=".fasta", delete=False, mode="wb") as tmp:
        if file is not None:
            tmp.write(await file.read())
        else:
            tmp.write(gene_fasta.encode())
        tmp_path = Path(tmp.name)

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
            result = pipeline.run()

            json_path = Path(out_dir) / "candidates.json"
            output = json.loads(json_path.read_text())

    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    return JSONResponse(output)
