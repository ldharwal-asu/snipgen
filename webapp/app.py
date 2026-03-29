"""SnipGen FastAPI web application."""

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from snipgen.filters.pam_filter import PAM_REGISTRY
from snipgen.pipeline import PipelineConfig, SnipGenPipeline

app = FastAPI(title="SnipGen", description="AI-driven CRISPR guide RNA design")

# Serve static files (index.html, etc.)
_static = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static)), name="static")


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


@app.post("/design")
async def design(
    file: UploadFile = File(..., description="FASTA file"),
    cas_variant: str = Query("SpCas9"),
    guide_length: int = Query(20, ge=17, le=25),
    min_gc: float = Query(0.40, ge=0.0, le=1.0),
    max_gc: float = Query(0.70, ge=0.0, le=1.0),
    top_n: int = Query(20, ge=1, le=200),
):
    """Run the SnipGen pipeline on an uploaded FASTA file."""
    if cas_variant not in PAM_REGISTRY:
        raise HTTPException(400, f"Unknown Cas variant '{cas_variant}'")
    if min_gc >= max_gc:
        raise HTTPException(400, "min_gc must be less than max_gc")

    # Write upload to a temp file
    with tempfile.NamedTemporaryFile(suffix=".fasta", delete=False) as tmp:
        tmp.write(await file.read())
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

            # Read the JSON output the pipeline already generated
            json_path = Path(out_dir) / "candidates.json"
            output = json.loads(json_path.read_text())

    except Exception as exc:
        raise HTTPException(500, str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)

    return JSONResponse(output)
