"""Generate SnipGen v2 SOP PDF."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import date

OUTPUT = "/Users/lxd/summer project/SnipGen_v2_SOP.pdf"

# ── Colour palette (light theme to match the app) ─────────────────────────────
ACCENT      = colors.HexColor("#2563eb")
ACCENT_SOFT = colors.HexColor("#eff6ff")
GREEN       = colors.HexColor("#059669")
GREEN_SOFT  = colors.HexColor("#ecfdf5")
YELLOW      = colors.HexColor("#d97706")
YELLOW_SOFT = colors.HexColor("#fffbeb")
RED         = colors.HexColor("#dc2626")
RED_SOFT    = colors.HexColor("#fef2f2")
MUTED       = colors.HexColor("#6b7280")
TEXT        = colors.HexColor("#111827")
TEXT2       = colors.HexColor("#374151")
BORDER      = colors.HexColor("#e5e7eb")
BG          = colors.HexColor("#f8f9fb")
SURFACE     = colors.HexColor("#ffffff")
DARK_HEADER = colors.HexColor("#1e3a5f")

# ── Styles ─────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kwargs):
    return ParagraphStyle(name, **kwargs)

styles = {
    "cover_title": S("cover_title",
        fontSize=28, fontName="Helvetica-Bold", textColor=SURFACE,
        leading=34, spaceAfter=8, alignment=TA_LEFT),
    "cover_sub": S("cover_sub",
        fontSize=13, fontName="Helvetica", textColor=colors.HexColor("#bfdbfe"),
        leading=18, spaceAfter=6, alignment=TA_LEFT),
    "cover_meta": S("cover_meta",
        fontSize=10, fontName="Helvetica", textColor=colors.HexColor("#93c5fd"),
        leading=14, alignment=TA_LEFT),

    "h1": S("h1",
        fontSize=16, fontName="Helvetica-Bold", textColor=DARK_HEADER,
        spaceBefore=22, spaceAfter=8, leading=20),
    "h2": S("h2",
        fontSize=12, fontName="Helvetica-Bold", textColor=ACCENT,
        spaceBefore=14, spaceAfter=5, leading=16),
    "h3": S("h3",
        fontSize=10, fontName="Helvetica-Bold", textColor=TEXT2,
        spaceBefore=10, spaceAfter=3, leading=14),
    "body": S("body",
        fontSize=9.5, fontName="Helvetica", textColor=TEXT2,
        leading=15, spaceAfter=6),
    "bullet": S("bullet",
        fontSize=9.5, fontName="Helvetica", textColor=TEXT2,
        leading=14, spaceAfter=3, leftIndent=16, firstLineIndent=-10),
    "mono": S("mono",
        fontSize=8.5, fontName="Courier", textColor=ACCENT,
        leading=13, spaceAfter=3, leftIndent=12),
    "mono_plain": S("mono_plain",
        fontSize=8, fontName="Courier", textColor=TEXT2,
        leading=12, spaceAfter=2, leftIndent=20),
    "caption": S("caption",
        fontSize=8, fontName="Helvetica", textColor=MUTED,
        leading=12, spaceAfter=4, alignment=TA_CENTER),
    "tag_green": S("tag_green",
        fontSize=8, fontName="Helvetica-Bold", textColor=GREEN,
        leading=12),
    "tag_red": S("tag_red",
        fontSize=8, fontName="Helvetica-Bold", textColor=RED,
        leading=12),
    "tag_yellow": S("tag_yellow",
        fontSize=8, fontName="Helvetica-Bold", textColor=YELLOW,
        leading=12),
    "tag_blue": S("tag_blue",
        fontSize=8, fontName="Helvetica-Bold", textColor=ACCENT,
        leading=12),
    "toc_item": S("toc_item",
        fontSize=9.5, fontName="Helvetica", textColor=TEXT2,
        leading=16, leftIndent=0),
    "toc_sub": S("toc_sub",
        fontSize=9, fontName="Helvetica", textColor=MUTED,
        leading=14, leftIndent=16),
    "footer": S("footer",
        fontSize=8, fontName="Helvetica", textColor=MUTED,
        leading=11, alignment=TA_CENTER),
    "warning": S("warning",
        fontSize=9, fontName="Helvetica", textColor=RED,
        leading=13, leftIndent=10),
    "note": S("note",
        fontSize=9, fontName="Helvetica", textColor=colors.HexColor("#1e40af"),
        leading=13, leftIndent=10),
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def hr(color=BORDER, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                      spaceAfter=6, spaceBefore=4)

def sp(n=6):
    return Spacer(1, n)

def P(text, style="body"):
    return Paragraph(text, styles[style])

def bullet(text):
    return Paragraph(f"<b>•</b>  {text}", styles["bullet"])

def code(text):
    return Paragraph(text, styles["mono"])

def status_table(rows):
    """rows: list of (Component, Status, Notes)"""
    data = [["Component", "Status", "Notes / Detail"]]
    data += rows
    col_widths = [1.8*inch, 0.95*inch, 3.9*inch]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND",   (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",    (0,0), (-1,0), SURFACE),
        ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0), (-1,0), 8.5),
        ("BOTTOMPADDING",(0,0), (-1,0), 7),
        ("TOPPADDING",   (0,0), (-1,0), 7),
        ("ALIGN",        (0,0), (-1,0), "LEFT"),
        ("GRID",         (0,0), (-1,-1), 0.4, BORDER),
        ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,1), (-1,-1), 8.5),
        ("TOPPADDING",   (0,1), (-1,-1), 5),
        ("BOTTOMPADDING",(0,1), (-1,-1), 5),
        ("VALIGN",       (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
    ])
    for i, row in enumerate(rows, start=1):
        status = row[1]
        if "DONE" in status or "LIVE" in status:
            style.add("TEXTCOLOR", (1,i), (1,i), GREEN)
            style.add("FONTNAME",  (1,i), (1,i), "Helvetica-Bold")
        elif "PARTIAL" in status:
            style.add("TEXTCOLOR", (1,i), (1,i), YELLOW)
            style.add("FONTNAME",  (1,i), (1,i), "Helvetica-Bold")
        elif "STUB" in status or "MISSING" in status:
            style.add("TEXTCOLOR", (1,i), (1,i), RED)
            style.add("FONTNAME",  (1,i), (1,i), "Helvetica-Bold")
    t.setStyle(style)
    return t

def info_box(text, bg=ACCENT_SOFT, border=ACCENT):
    data = [[Paragraph(text, ParagraphStyle("ib", fontSize=9, fontName="Helvetica",
                textColor=TEXT2, leading=14, leftIndent=4))]]
    t = Table(data, colWidths=[6.68*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), bg),
        ("LINEAFTER",     (0,0), (0,-1),  1.5, border),
        ("LINEBEFORE",    (0,0), (0,-1),  3,   border),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    return t

def warning_box(text):
    return info_box(f"<b>⚠ Note:</b>  {text}", bg=RED_SOFT, border=RED)

def note_box(text):
    return info_box(f"<b>ℹ</b>  {text}", bg=ACCENT_SOFT, border=ACCENT)

def section_divider(title):
    return [
        sp(4),
        Table([[Paragraph(title, ParagraphStyle("sd", fontSize=11,
                fontName="Helvetica-Bold", textColor=SURFACE, leading=16))]],
              colWidths=[6.68*inch],
              style=TableStyle([
                  ("BACKGROUND",    (0,0), (-1,-1), DARK_HEADER),
                  ("TOPPADDING",    (0,0), (-1,-1), 8),
                  ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                  ("LEFTPADDING",   (0,0), (-1,-1), 14),
              ])),
        sp(6),
    ]

# ── Page numbering ─────────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    # Footer line
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.75*inch, 0.65*inch, w - 0.75*inch, 0.65*inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.75*inch, 0.48*inch, "SnipGen v2 — Standard Operating Procedure")
    canvas.drawString(0.75*inch, 0.36*inch, f"Confidential · Generated {date.today().strftime('%B %d, %Y')}")
    canvas.drawRightString(w - 0.75*inch, 0.48*inch, f"Page {doc.page}")
    # Header line (not on cover)
    if doc.page > 1:
        canvas.setStrokeColor(BORDER)
        canvas.line(0.75*inch, h - 0.6*inch, w - 0.75*inch, h - 0.6*inch)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(ACCENT)
        canvas.drawString(0.75*inch, h - 0.48*inch, "SNIPGEN")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(w - 0.75*inch, h - 0.48*inch, "CRISPR Guide RNA Safety Platform")
    canvas.restoreState()

def cover_page(canvas, doc):
    canvas.saveState()
    w, h = letter
    # Deep blue cover background
    canvas.setFillColor(DARK_HEADER)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    # Accent bar
    canvas.setFillColor(ACCENT)
    canvas.rect(0, h*0.52, w, 6, fill=1, stroke=0)
    # Bottom bar
    canvas.setFillColor(colors.HexColor("#0f2240"))
    canvas.rect(0, 0, w, 1.1*inch, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#60a5fa"))
    canvas.drawString(0.75*inch, 0.5*inch,
        f"SnipGen v2 SOP  ·  Generated {date.today().strftime('%B %d, %Y')}  ·  Confidential")
    canvas.restoreState()

# ── Build story ────────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.85*inch,  bottomMargin=0.85*inch,
        title="SnipGen v2 — Standard Operating Procedure",
        author="SnipGen Development",
        subject="CRISPR Guide RNA Safety Platform SOP",
    )

    story = []

    # ── COVER ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 2.1*inch))
    story.append(Paragraph("SnipGen", ParagraphStyle("logo",
        fontSize=42, fontName="Helvetica-Bold", textColor=SURFACE, leading=46)))
    story.append(Spacer(1, 0.08*inch))
    story.append(Paragraph("v2.0 — CRISPR Guide RNA Safety Platform",
        styles["cover_sub"]))
    story.append(Spacer(1, 0.18*inch))
    story.append(Paragraph("Standard Operating Procedure",
        ParagraphStyle("cover_title_sm", fontSize=18, fontName="Helvetica",
            textColor=colors.HexColor("#93c5fd"), leading=22)))
    story.append(Spacer(1, 0.5*inch))

    meta_lines = [
        ("Document Version", "1.0"),
        ("Platform Version", "v2.0 — Safety Engine"),
        ("Date",             date.today().strftime("%B %d, %Y")),
        ("Classification",   "Internal — Confidential"),
        ("Deployment",       "Vercel (Serverless)  ·  GitHub: ldharwal-asu/snipgen"),
    ]
    for k, v in meta_lines:
        story.append(Paragraph(
            f'<font color="#93c5fd"><b>{k}:</b></font>  <font color="#bfdbfe">{v}</font>',
            ParagraphStyle("cm", fontSize=9.5, fontName="Helvetica",
                textColor=SURFACE, leading=15)))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──────────────────────────────────────────────────────
    story.append(P("Table of Contents", "h1"))
    story.append(hr(ACCENT, 1))
    story.append(sp(4))

    toc = [
        ("1.", "Project Overview", []),
        ("2.", "System Architecture", [
            "2.1  Module Map",
            "2.2  Data Flow Pipeline",
        ]),
        ("3.", "Component Status Register", [
            "3.1  Backend Modules",
            "3.2  Scoring Engine",
            "3.3  API Endpoints",
            "3.4  Frontend",
            "3.5  Infrastructure",
        ]),
        ("4.", "Scoring Engine — Technical Reference", [
            "4.1  On-Target Scorer",
            "4.2  Off-Target Scorer",
            "4.3  Consequence Scorer",
            "4.4  Confidence Scorer",
            "4.5  Composite Scorer (2-Pass)",
        ]),
        ("5.", "API Reference", []),
        ("6.", "Deployment & Operations", [
            "6.1  Local Development",
            "6.2  Vercel Deployment",
            "6.3  Environment & Dependencies",
        ]),
        ("7.", "Known Limitations & Constraints", []),
        ("8.", "Development Roadmap", [
            "8.1  Phase 1 — Data Integration (Months 1-2)",
            "8.2  Phase 2 — Real Genome Scanning (Months 2-3)",
            "8.3  Phase 3 — ML Model (Months 3-4)",
            "8.4  Phase 4 — IP Filing (Month 4+)",
        ]),
        ("9.", "File Structure Reference", []),
    ]
    for num, title, subs in toc:
        story.append(Paragraph(f"<b>{num}</b>  {title}",
            ParagraphStyle("toc_h", fontSize=10.5, fontName="Helvetica",
                textColor=TEXT, leading=18, leftIndent=0)))
        for sub in subs:
            story.append(Paragraph(sub,
                ParagraphStyle("toc_s", fontSize=9, fontName="Helvetica",
                    textColor=MUTED, leading=14, leftIndent=22)))
    story.append(PageBreak())

    # ── SECTION 1: PROJECT OVERVIEW ────────────────────────────────────────────
    story += section_divider("1  Project Overview")
    story.append(P("What Is SnipGen?", "h2"))
    story.append(P(
        "SnipGen is a web-based CRISPR guide RNA (gRNA) design platform built on a "
        "modular v2 Safety Engine. It ingests FASTA-formatted DNA sequences and returns "
        "ranked guide RNA candidates scored across four independent safety dimensions: "
        "on-target efficiency, off-target burden, genomic consequence risk, and scoring "
        "confidence. Results are delivered through a clean, minimal web interface and are "
        "exportable as CSV or JSON.", "body"))
    story.append(sp(4))

    story.append(P("Current Deployment Status", "h2"))
    story.append(note_box(
        "SnipGen v2 is live on Vercel at the production URL connected to the "
        "GitHub repository ldharwal-asu/snipgen (main branch). Auto-deploy is active — "
        "every push to main triggers a Vercel rebuild within ~60 seconds."))
    story.append(sp(8))

    overview_data = [
        ["Property", "Value"],
        ["Platform", "FastAPI (Python 3.11) + Vanilla JS SPA"],
        ["Hosting", "Vercel Serverless (@vercel/python runtime)"],
        ["Repository", "github.com/ldharwal-asu/snipgen"],
        ["PAM Support", "SpCas9 (NGG), SaCas9 (NNGRRT), Cas12a (TTTV), xCas9/Cas9-NG (NG)"],
        ["Guide Length Range", "17–25 bp (default: 20 bp)"],
        ["Scoring Scale", "0–100 (all dimensions)"],
        ["Safety Labels", "HIGH (≥80) · MEDIUM (50–79) · LOW (20–49) · AVOID (<20)"],
        ["Export Formats", "JSON, CSV"],
        ["Max Sequence Scan (off-target)", "5,000 bp (Vercel timeout guard)"],
    ]
    t = Table(overview_data, colWidths=[2.2*inch, 4.48*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("FONTNAME",      (0,1), (0,-1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0,1), (0,-1), TEXT2),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── SECTION 2: ARCHITECTURE ────────────────────────────────────────────────
    story += section_divider("2  System Architecture")
    story.append(P("2.1  Module Map", "h2"))
    story.append(P(
        "SnipGen is organised into four top-level packages. All source lives under "
        "<font face='Courier'>snipgen/</font>, the web layer under "
        "<font face='Courier'>webapp/</font>, and the Vercel entry point is "
        "<font face='Courier'>api/index.py</font>.", "body"))
    story.append(sp(4))

    arch_data = [
        ["Package / File", "Purpose"],
        ["snipgen/io/fasta_reader.py", "Parse FASTA / gzipped FASTA; collect sequence statistics"],
        ["snipgen/models/grna_candidate.py", "GRNACandidate dataclass — v2 field schema"],
        ["snipgen/generation/guide_generator.py", "Slide window over sequence; emit raw candidates"],
        ["snipgen/filters/", "GC filter, homopolymer filter, restriction site filter"],
        ["snipgen/filters/deduplicator.py", "Position-aware clustering (10 bp window); keep best per cluster"],
        ["snipgen/scoring/ontarget_scorer.py", "6-component on-target score (GC, position, Tm, homopolymer, leading base, self-comp)"],
        ["snipgen/scoring/offtarget_scorer.py", "Seed mismatch counter; off-target burden score (0–100)"],
        ["snipgen/scoring/consequence_scorer.py", "Genomic consequence risk tier (Tier 1: returns 85.0 default)"],
        ["snipgen/scoring/confidence_scorer.py", "5-signal confidence score; applies safety label + colour"],
        ["snipgen/scoring/recommendation.py", "Template-based natural language recommendation generator"],
        ["snipgen/scoring/composite_scorer.py", "2-pass composite orchestrator (on=0.30, off=0.25, con=0.30, conf=0.15)"],
        ["snipgen/pipeline.py", "End-to-end orchestrator; returns metadata + ranked candidates"],
        ["webapp/app.py", "FastAPI app; /design POST endpoint; serves index.html"],
        ["webapp/static/index.html", "Single-page UI — upload, dashboard, guide cards, table, export"],
        ["api/index.py", "Vercel entry point; injects project root into sys.path"],
        ["pyproject.toml", "uv-compatible dependency manifest (Vercel ignores requirements.txt)"],
        ["vercel.json", "Routes all traffic to api/index.py"],
    ]
    t2 = Table(arch_data, colWidths=[2.7*inch, 3.98*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("FONTNAME",      (0,1), (0,-1), "Courier"),
        ("TEXTCOLOR",     (0,1), (0,-1), ACCENT),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t2)
    story.append(sp(14))

    story.append(P("2.2  Data Flow Pipeline", "h2"))
    pipeline_steps = [
        ("1", "FASTA Ingestion", "FASTAReader parses .fasta / .fa / .fna / .gz. Collects per-record stats (id, length, gc_content, n_count)."),
        ("2", "Candidate Generation", "GuideGenerator slides a window of guide_length across each strand. Extracts sequence + PAM. Stores chromosome/start/end/strand."),
        ("3", "Filter Chain", "GC range filter → homopolymer run filter (≥4 identical) → restriction site filter. Records pass_rate in metadata."),
        ("4", "Position-Aware Deduplication", "Sort by (chromosome, strand, start). Cluster guides within 10 bp. Keep representative with best gc_content / rule_score. Tag removed guides as DUPLICATE."),
        ("5", "Scoring — On-Target", "OnTargetScorer runs 6 sub-components. Returns (score, breakdown_dict). Weight: 0.30 in composite."),
        ("6", "Scoring — Off-Target", "OffTargetScorer counts 1mm/2mm/3mm near-matches in input sequence (capped 5000 bp). Weight: 0.25."),
        ("7", "Scoring — Consequence", "ConsequenceScorer returns 85.0 default (Tier 1). Will use annotation DB in Tier 2+. Weight: 0.30."),
        ("8", "Scoring — Confidence (Pass 1)", "Preliminary composite computed. Margin between top-2 guides feeds confidence signal."),
        ("9", "Composite + Confidence (Pass 2)", "True composite calculated. ConfidenceScorer annotates confidence_score, safety_label, safety_color."),
        ("10", "Recommendation", "generate_recommendation() produces natural language summary per guide."),
        ("11", "Sort & Return", "Sort by final_score descending. Slice top_n. Attach rank, guide_id to score_breakdown. Return metadata + candidates JSON."),
    ]
    for num, title, desc in pipeline_steps:
        row_data = [[
            Paragraph(num, ParagraphStyle("step_num", fontSize=10,
                fontName="Helvetica-Bold", textColor=SURFACE, leading=12, alignment=TA_CENTER)),
            Paragraph(f"<b>{title}</b>", ParagraphStyle("step_title", fontSize=9,
                fontName="Helvetica-Bold", textColor=ACCENT, leading=13)),
            Paragraph(desc, ParagraphStyle("step_desc", fontSize=8.5,
                fontName="Helvetica", textColor=TEXT2, leading=13)),
        ]]
        step_t = Table(row_data, colWidths=[0.3*inch, 1.5*inch, 4.88*inch])
        step_t.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (0,0), ACCENT),
            ("BACKGROUND",    (1,0), (-1,0), ACCENT_SOFT),
            ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (0,0), 0),
            ("LEFTPADDING",   (1,0), (-1,-1), 8),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ("ALIGN",         (0,0), (0,0), "CENTER"),
        ]))
        story.append(step_t)
        story.append(sp(2))
    story.append(PageBreak())

    # ── SECTION 3: COMPONENT STATUS ────────────────────────────────────────────
    story += section_divider("3  Component Status Register")
    story.append(P("3.1  Backend Modules", "h2"))
    story.append(status_table([
        ["FASTAReader", "DONE", "Handles plain + gzip. Emits sequence_stats per record."],
        ["GuideGenerator", "DONE", "Both strands. Reverse-complement for minus strand."],
        ["GC Filter", "DONE", "Configurable min_gc / max_gc (0.0–1.0 fraction)."],
        ["Homopolymer Filter", "DONE", "Rejects guides with ≥4 consecutive identical bases."],
        ["Restriction Filter", "DONE", "Filters BamHI, EcoRI, HindIII, XhoI sites by default."],
        ["Deduplicator", "DONE", "10 bp window clustering; DUPLICATE rejection code tagged."],
        ["Pipeline Orchestrator", "DONE", "Full metadata block including safety_distribution."],
    ]))
    story.append(sp(10))

    story.append(P("3.2  Scoring Engine", "h2"))
    story.append(status_table([
        ["OnTargetScorer", "DONE", "6 components: GC bell (0.25), Doench pos (0.30), Tm (0.15), homopolymer pen (0.10), leading base (0.10), self-comp (0.10). Rule-based — not ML-trained."],
        ["OffTargetScorer", "PARTIAL", "Seed mismatch within uploaded FASTA only. Capped at 5000 bp. NOT a genome-wide scan — scores are approximate."],
        ["ConsequenceScorer", "STUB", "Returns 85.0 for all guides (Tier 1 constant). No annotation database wired. Tier 2 implementation pending."],
        ["ConfidenceScorer", "DONE", "5-signal heuristic: margin (0.20), sub_agreement (0.30), data_quality (0.25), complexity (0.15), validation (0.10). Applies safety label."],
        ["CompositeScorer", "DONE", "2-pass design. Pass 1: preliminary composite for confidence margin. Pass 2: true composite with confidence weight."],
        ["RecommendationEngine", "DONE", "Template-based natural language. 4 tiers (HIGH/MEDIUM/LOW/AVOID) × safety context."],
        ["ML Scorer", "MISSING", "Constructor kwarg accepted but no model loaded. Entire ML layer is a planned future module."],
    ]))
    story.append(sp(10))

    story.append(P("3.3  API Endpoints", "h2"))
    story.append(status_table([
        ["GET /", "DONE", "Serves index.html (reads file at startup path)."],
        ["POST /design", "DONE", "Accepts multipart FASTA upload + query params. Returns JSON with metadata + candidates array."],
        ["GET /health", "DONE", "Returns {status: ok, version: 2.0.0}."],
        ["GET /static/*", "MISSING", "StaticFiles mount removed (crashes Vercel). CSS/JS are inline in index.html."],
    ]))
    story.append(sp(10))

    story.append(P("3.4  Frontend", "h2"))
    story.append(status_table([
        ["Upload Panel", "DONE", "Drop-zone with drag/drop, file input, preset buttons, parameter controls."],
        ["Loading State", "DONE", "Animated ring + descriptive copy. Shown during fetch."],
        ["Dashboard", "DONE", "Stats row, safety distribution chips, score profile radar, guide cards, full table."],
        ["Guide Cards", "DONE", "Expandable. Shows 4D scores, recommendation, off-target mismatch counts, copy button."],
        ["Radar Chart", "DONE", "SVG polygon — 4 axes (On-Target, Off-Target, Consequence, Confidence)."],
        ["Results Table", "DONE", "All candidates, sticky header, sortable columns (client-side future work)."],
        ["CSV Export", "DONE", "Client-side Blob download."],
        ["JSON Export", "DONE", "Full response payload download."],
        ["show() Bug", "DONE", "Fixed: renamed showEl/hideEl, sets display='block' explicitly."],
    ]))
    story.append(sp(10))

    story.append(P("3.5  Infrastructure", "h2"))
    story.append(status_table([
        ["Vercel Deployment", "LIVE", "Auto-deploy on push to main. Python runtime via @vercel/python."],
        ["Dependency Management", "DONE", "pyproject.toml is the source of truth. Vercel uses uv and ignores requirements.txt."],
        ["Flat-layout Fix", "DONE", "[tool.setuptools.packages.find] include=[\"snipgen*\"] prevents multi-package error."],
        ["Git Identity", "DONE", "lakshya dharwal / 267613132+ldharwal-asu@users.noreply.github.com"],
        ["GitHub Actions / CI", "MISSING", "No CI pipeline. Tests run manually only."],
        ["Test Suite", "MISSING", "Smoke test exists in pipeline.py __main__. No pytest suite."],
        ["Monitoring / Alerting", "MISSING", "No uptime monitoring or error alerting configured."],
    ]))
    story.append(PageBreak())

    # ── SECTION 4: SCORING REFERENCE ──────────────────────────────────────────
    story += section_divider("4  Scoring Engine — Technical Reference")

    story.append(P("4.1  On-Target Scorer  (weight: 0.30 in composite)", "h2"))
    ot_data = [
        ["Sub-Component", "Weight", "Logic"],
        ["GC Bell Curve",       "0.25", "Peak at 55% GC. Score = 100 − 250 × (gc − 0.55)². Penalty symmetric around optimum."],
        ["Position Preferences","0.30", "Doench 2016 weights applied to each base-position pair. Lookup table across 20 positions × 4 bases."],
        ["Thermodynamic Tm",    "0.15", "Wallace rule: Tm = 2(A+T) + 4(G+C). Target 60–65 °C. Score = max(0, 100 − 8 × |Tm − 62|)."],
        ["Homopolymer Penalty", "0.10", "Detects runs of ≥3 identical bases. Each additional base in run subtracts 25 pts."],
        ["Leading Base",        "0.10", "G/C preferred at position 1 (score 100). A/T at position 1 (score 60)."],
        ["Self-Complementarity","0.10", "Palindrome scan: checks 4+ bp inverted repeats. Score decrements per hairpin found."],
    ]
    t_ot = Table(ot_data, colWidths=[1.7*inch, 0.65*inch, 4.33*inch])
    t_ot.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ALIGN",         (1,0), (1,-1), "CENTER"),
    ]))
    story.append(t_ot)
    story.append(sp(12))

    story.append(P("4.2  Off-Target Scorer  (weight: 0.25 in composite)", "h2"))
    story.append(warning_box(
        "Current implementation scans only the uploaded FASTA sequence, capped at 5,000 bp. "
        "This is NOT a genome-wide off-target assessment. For therapeutic applications, "
        "genome-scale scanning (CasOFFinder / CRISPOR) is required."))
    story.append(sp(6))
    for line in [
        "Seed region: PAM-proximal 12 bp (positions 9–20 of guide).",
        "Pre-filter: candidate windows with >2 mismatches in seed are skipped (fast path).",
        "Full mismatch count performed on candidates passing seed filter.",
        "Burden = sum(count<sub>mm</sub> × 1/mm) for mm in {1, 2, 3}.",
        "off_target_score = max(0, 100 − min(burden × 10, 100)).",
        "Annotates: off_targets_1mm, off_targets_2mm, off_targets_3mm, off_target_burden_raw.",
    ]:
        story.append(bullet(line))
    story.append(sp(12))

    story.append(P("4.3  Consequence Scorer  (weight: 0.30 in composite)", "h2"))
    story.append(warning_box(
        "Tier 1 only. ConsequenceScorer returns a fixed default of 85.0 for all guides. "
        "No annotation database is connected. This dimension is a placeholder pending "
        "Tier 2 implementation with a genomic annotation layer."))
    story.append(sp(6))
    story.append(P("Planned Tier 2 risk tiers:", "h3"))
    risk_data = [
        ["Genomic Region", "Risk Score"],
        ["Tumour suppressor exon / Oncogene exon", "10.0  (highest risk)"],
        ["Coding exon", "5.0"],
        ["Splice site", "5.0"],
        ["Promoter", "3.0"],
        ["UTR", "2.5"],
        ["Intron", "1.0"],
        ["Intergenic", "0.2"],
        ["Repeat element", "0.1  (lowest risk)"],
    ]
    t_risk = Table(risk_data, colWidths=[3.5*inch, 3.18*inch])
    t_risk.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
    ]))
    story.append(t_risk)
    story.append(sp(12))

    story.append(P("4.4  Confidence Scorer  (weight: 0.15 in composite)", "h2"))
    conf_data = [
        ["Signal", "Weight", "Source"],
        ["Score Margin",      "0.20", "Difference between guide's composite and 2nd-best guide."],
        ["Sub-score Agreement","0.30", "Variance across the 4 dimension scores. Low variance = high agreement = higher confidence."],
        ["Data Quality",      "0.25", "Fixed by data tier: Tier1=40, Tier2=80, Tier3=100."],
        ["Sequence Complexity","0.15", "Linguistic complexity of the guide sequence (Shannon entropy proxy)."],
        ["Validation Signal", "0.10", "Reserved for future experimental validation data hook-in."],
    ]
    t_conf = Table(conf_data, colWidths=[1.7*inch, 0.65*inch, 4.33*inch])
    t_conf.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("ALIGN",         (1,0), (1,-1), "CENTER"),
    ]))
    story.append(t_conf)
    story.append(sp(12))

    story.append(P("4.5  Composite Scorer — 2-Pass Design", "h2"))
    story.append(info_box(
        "<b>Weights:</b>  On-Target 0.30  ·  Off-Target 0.25  ·  Consequence 0.30  ·  Confidence 0.15<br/>"
        "<b>Scale:</b>  0–100  ·  <b>Passes:</b>  2 (preliminary → confidence margin → true final)"))
    story.append(sp(6))
    for line in [
        "<b>Pass 1:</b> Compute preliminary composite (on+off+consequence only, renormalised). Sort candidates.",
        "<b>Margin extraction:</b> Difference between top-2 preliminary scores fed into ConfidenceScorer as margin signal.",
        "<b>Pass 2:</b> True composite = (on×0.30) + (off×0.25) + (con×0.30) + (confidence×0.15). Scale 0–100. Round to 1 dp.",
        "Safety label applied based on final_score threshold: HIGH ≥80, MEDIUM ≥50, LOW ≥20, AVOID <20.",
    ]:
        story.append(bullet(line))
    story.append(PageBreak())

    # ── SECTION 5: API REFERENCE ──────────────────────────────────────────────
    story += section_divider("5  API Reference")

    story.append(P("POST /design", "h2"))
    story.append(info_box(
        "<b>Content-Type:</b>  multipart/form-data  ·  "
        "<b>Response:</b>  application/json  ·  "
        "<b>Timeout:</b>  Vercel 10s limit (enforce short sequences or async pattern for large inputs)"))
    story.append(sp(6))

    params_data = [
        ["Parameter", "Type", "Default", "Description"],
        ["file", "File (multipart)", "required", "FASTA or gzipped FASTA sequence file."],
        ["cas_variant", "string", "SpCas9", "PAM variant: SpCas9 | SaCas9 | Cpf1 | xCas9 | Cas9-NG"],
        ["guide_length", "int", "20", "Guide RNA length in bp. Range: 17–25."],
        ["min_gc", "float", "0.40", "Minimum GC content fraction (0.0–1.0)."],
        ["max_gc", "float", "0.70", "Maximum GC content fraction (0.0–1.0)."],
        ["top_n", "int", "20", "Number of top guides to return after scoring. Max: 200."],
    ]
    t_params = Table(params_data, colWidths=[1.4*inch, 1.2*inch, 0.75*inch, 3.33*inch])
    t_params.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("FONTNAME",      (0,1), (0,-1), "Courier"),
        ("TEXTCOLOR",     (0,1), (0,-1), ACCENT),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t_params)
    story.append(sp(10))

    story.append(P("Response Schema", "h3"))
    story.append(P(
        "The response is a JSON object with two top-level keys: "
        "<font face='Courier'>metadata</font> and <font face='Courier'>candidates</font>.", "body"))
    story.append(sp(4))

    resp_data = [
        ["Field", "Type", "Description"],
        ["metadata.total_candidates_evaluated", "int", "Raw window count before any filtering."],
        ["metadata.candidates_passed_filters",  "int", "Count after GC + homopolymer + restriction filters."],
        ["metadata.candidates_after_dedup",     "int", "Count after position-aware deduplication."],
        ["metadata.pass_rate",                  "float", "candidates_passed / total_evaluated."],
        ["metadata.safety_distribution",        "dict", "{'HIGH': N, 'MEDIUM': N, 'LOW': N, 'AVOID': N}"],
        ["metadata.sequence_stats",             "list", "Per-record stats: id, length, gc_content, n_count, n_fraction."],
        ["candidates[].sequence",               "str", "20bp (or guide_length) guide sequence."],
        ["candidates[].pam",                    "str", "PAM sequence following the guide."],
        ["candidates[].chromosome",             "str", "FASTA record ID (used as chromosome identifier)."],
        ["candidates[].start / .end",           "int", "0-based genomic coordinates."],
        ["candidates[].strand",                 "str", "+ or −"],
        ["candidates[].gc_content",             "float", "GC fraction 0.0–1.0."],
        ["candidates[].final_score",            "float", "Composite safety score 0–100."],
        ["candidates[].on_target_score",        "float", "On-target efficiency score 0–100."],
        ["candidates[].off_target_score",       "float", "Off-target burden score 0–100."],
        ["candidates[].consequence_score",      "float", "Genomic consequence risk score 0–100."],
        ["candidates[].confidence_score",       "float", "Scoring confidence 0–100."],
        ["candidates[].safety_label",           "str", "HIGH | MEDIUM | LOW | AVOID"],
        ["candidates[].safety_color",           "str", "green | yellow | orange | red"],
        ["candidates[].off_targets_1mm",        "int", "Count of 1-mismatch off-target sites in scan window."],
        ["candidates[].off_targets_2mm",        "int", "Count of 2-mismatch off-target sites in scan window."],
        ["candidates[].off_targets_3mm",        "int", "Count of 3-mismatch off-target sites in scan window."],
        ["candidates[].recommendation",         "str", "Natural language summary of guide safety profile."],
        ["candidates[].score_breakdown",        "dict", "rank, guide_id, per-dimension breakdowns, data tier info."],
    ]
    t_resp = Table(resp_data, colWidths=[2.6*inch, 0.7*inch, 3.38*inch])
    t_resp.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 7.8),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("FONTNAME",      (0,1), (0,-1), "Courier"),
        ("TEXTCOLOR",     (0,1), (0,-1), ACCENT),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t_resp)
    story.append(PageBreak())

    # ── SECTION 6: DEPLOYMENT ─────────────────────────────────────────────────
    story += section_divider("6  Deployment & Operations")

    story.append(P("6.1  Local Development", "h2"))
    for step in [
        "Clone the repository: <font face='Courier'>git clone https://github.com/ldharwal-asu/snipgen</font>",
        "Install dependencies: <font face='Courier'>pip install -e .</font>  or  <font face='Courier'>uv sync</font>",
        "Run the dev server: <font face='Courier'>uvicorn webapp.app:app --reload --port 8000</font>",
        "Open browser: <font face='Courier'>http://localhost:8000</font>",
        "Run smoke test: <font face='Courier'>python -m snipgen.pipeline</font>  (uses built-in synthetic FASTA)",
    ]:
        story.append(bullet(step))
    story.append(sp(10))

    story.append(P("6.2  Vercel Deployment", "h2"))
    story.append(note_box(
        "Every push to the main branch triggers an automatic Vercel rebuild. "
        "No manual deploy steps are required after initial setup."))
    story.append(sp(6))
    for step in [
        "Entry point: <font face='Courier'>api/index.py</font> — imports <font face='Courier'>webapp.app:app</font> after injecting project root into sys.path.",
        "Routing: <font face='Courier'>vercel.json</font> routes all traffic (<font face='Courier'>/(.*)</font>) to <font face='Courier'>api/index.py</font>.",
        "Dependencies: Vercel's <font face='Courier'>uv</font> resolver reads only <font face='Courier'>pyproject.toml</font>. Any package not listed there will not be installed.",
        "StaticFiles: The <font face='Courier'>app.mount(StaticFiles)</font> call is intentionally removed — it crashes at startup in serverless. CSS and JS are inlined in index.html.",
        "Timeout: Vercel functions have a 10-second execution limit. Large FASTA files will trigger timeout. Off-target scan is capped at 5,000 bp as mitigation.",
    ]:
        story.append(bullet(step))
    story.append(sp(10))

    story.append(P("6.3  Environment & Dependencies", "h2"))
    dep_data = [
        ["Package", "Version Constraint", "Purpose"],
        ["fastapi", "≥0.110.0", "Web framework — async ASGI app"],
        ["uvicorn[standard]", "≥0.29.0", "ASGI server for local dev"],
        ["python-multipart", "≥0.0.9", "Required for FastAPI file upload (multipart/form-data)"],
        ["biopython", "(any)", "FASTA parsing utilities (optional path)"],
        ["setuptools", "(any)", "Package discovery — flat-layout fix via pyproject.toml"],
    ]
    t_dep = Table(dep_data, colWidths=[1.7*inch, 1.4*inch, 3.58*inch])
    t_dep.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), DARK_HEADER),
        ("TEXTCOLOR",     (0,0), (-1,0), SURFACE),
        ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8.5),
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [SURFACE, BG]),
        ("FONTNAME",      (0,1), (0,-1), "Courier"),
        ("TEXTCOLOR",     (0,1), (0,-1), ACCENT),
    ]))
    story.append(t_dep)
    story.append(PageBreak())

    # ── SECTION 7: LIMITATIONS ────────────────────────────────────────────────
    story += section_divider("7  Known Limitations & Constraints")

    limitations = [
        ("Off-target scoring is not genome-wide",
         "The OffTargetScorer scans only the uploaded FASTA, capped at 5,000 bp. "
         "For context, the human genome is 3.2 billion bp. Current off-target scores reflect "
         "within-sequence burden only and should not be cited as genome-scale safety evidence."),
        ("ConsequenceScorer is a stub",
         "All guides receive a consequence_score of 85.0. No genomic annotation database "
         "(Ensembl, RefSeq, GENCODE) is integrated. This dimension is non-functional until Tier 2."),
        ("ML Scorer does not exist",
         "The CompositeScorer accepts ml_scorer as a constructor kwarg but immediately discards it. "
         "The on-target scorer is rule-based, not trained on any experimental data."),
        ("Vercel 10-second timeout",
         "Serverless function execution is limited to 10 seconds. Large FASTA files (>50 kb) "
         "or sequences with many PAM sites will hit this limit. No async job queue exists."),
        ("No CI / test suite",
         "There is no automated test pipeline. A smoke test exists in pipeline.py __main__ "
         "but is run manually. No pytest suite, no GitHub Actions workflow."),
        ("No authentication or rate limiting",
         "The /design endpoint is open to the public with no authentication, API key, "
         "or rate limiting. Abuse is possible on the free Vercel tier."),
        ("No experimental validation",
         "No guide RNAs designed by SnipGen have been experimentally tested. "
         "All scores are computational estimates with no empirical correlation established."),
        ("StaticFiles removal impacts asset serving",
         "CSS, JavaScript, and any future assets must be inlined in index.html or served "
         "via a CDN. Additional static assets cannot be added without architectural changes."),
    ]
    for title, desc in limitations:
        story.append(KeepTogether([
            warning_box(f"<b>{title}:</b>  {desc}"),
            sp(5),
        ]))
    story.append(PageBreak())

    # ── SECTION 8: ROADMAP ────────────────────────────────────────────────────
    story += section_divider("8  Development Roadmap")

    phases = [
        ("Phase 1 — Data Integration", "Months 1–2", GREEN, [
            "Download Doench 2016, Sanson 2018 (Brunello), and Hart 2015 experimental datasets (all public).",
            "Train XGBoost / LightGBM on-target efficiency model on merged dataset (~74,000 guides).",
            "Replace hardcoded OnTargetScorer weight arrays with model.predict().",
            "Validate on held-out Hart 2015 test set. Report Spearman correlation and ROC-AUC.",
            "Download gnomAD common variant summary (MAF >1%). Extract SNPs in PAM-proximal 12 bp windows.",
            "Build seed-region SNP lookup table (~200 MB compressed). Wire into ConsequenceScorer.",
        ]),
        ("Phase 2 — Real Genome Scanning", "Months 2–3", YELLOW, [
            "Move off-target computation to an async worker (Render or AWS Lambda).",
            "Wire CRISPOR public API as genome-scale off-target backend (hg38, mm10).",
            "Implement job queue: POST /design-async returns job_id. GET /result/{job_id} polls status.",
            "Store results in Redis with 1-hour TTL.",
            "Update frontend to poll for result and show progress indicator.",
        ]),
        ("Phase 3 — ML Model & Consequence Engine", "Months 3–4", ACCENT, [
            "Integrate Ensembl REST API for gene/exon/splice-site annotation per guide position.",
            "Implement ConsequenceScorer Tier 2 using annotation database.",
            "Train multi-task model jointly optimising on-target + off-target from merged public data.",
            "Establish benchmark: compare SnipGen composite score vs. Doench Rule Set 2 on held-out set.",
        ]),
        ("Phase 4 — IP Filing", "Month 4+", RED, [
            "Engage a biotech patent attorney. Budget: ~$1,500–3,000 for provisional.",
            "File provisional patent on: (1) 2-pass confidence-weighted composite scoring architecture, "
            "(2) population SNP seed-region burden metric, (3) multi-task joint training framework.",
            "Convert to full utility patent within 12 months with wet-lab validation if available.",
            "USPTO filing fee: ~$320 (small entity).",
        ]),
    ]

    for phase_title, timeline, color, tasks in phases:
        story.append(P(f"8.{phases.index((phase_title, timeline, color, tasks))+1}  {phase_title}", "h2"))
        story.append(info_box(f"<b>Timeline:</b>  {timeline}", bg=ACCENT_SOFT, border=color))
        story.append(sp(4))
        for task in tasks:
            story.append(bullet(task))
        story.append(sp(8))
    story.append(PageBreak())

    # ── SECTION 9: FILE STRUCTURE ─────────────────────────────────────────────
    story += section_divider("9  File Structure Reference")

    tree_lines = [
        ("snipgen/",                          "Root package"),
        ("  io/",                             ""),
        ("    fasta_reader.py",               "FASTA + gzip parser, sequence stats"),
        ("  models/",                         ""),
        ("    grna_candidate.py",             "GRNACandidate dataclass (v2 schema)"),
        ("  generation/",                     ""),
        ("    guide_generator.py",            "Sliding window, both strands"),
        ("  filters/",                        ""),
        ("    gc_filter.py",                  "GC content range filter"),
        ("    homopolymer_filter.py",         "Poly-N run rejection"),
        ("    restriction_filter.py",         "Common restriction site filter"),
        ("    deduplicator.py",               "Position-aware 10 bp clustering"),
        ("  scoring/",                        ""),
        ("    ontarget_scorer.py",            "6-component on-target scorer"),
        ("    offtarget_scorer.py",           "Seed mismatch burden scorer"),
        ("    consequence_scorer.py",         "Tier 1 stub — returns 85.0"),
        ("    confidence_scorer.py",          "5-signal confidence + safety label"),
        ("    recommendation.py",             "Natural language recommendation"),
        ("    composite_scorer.py",           "2-pass orchestrator"),
        ("  pipeline.py",                     "End-to-end orchestrator"),
        ("webapp/",                           "Web layer"),
        ("  app.py",                          "FastAPI app, /design endpoint"),
        ("  static/",                         ""),
        ("    index.html",                    "Single-page UI (all CSS + JS inline)"),
        ("api/",                              "Vercel entry"),
        ("  index.py",                        "sys.path inject + import app"),
        ("vercel.json",                       "Route all → api/index.py"),
        ("pyproject.toml",                    "Dependency manifest (uv source of truth)"),
        ("requirements.txt",                  "Ignored by Vercel — kept for local pip"),
    ]

    tree_data = [[
        Paragraph(f"<font face='Courier'>{path}</font>",
            ParagraphStyle("tree_path", fontSize=8,
                fontName="Courier-Bold" if path.endswith("/") else "Courier",
                textColor=DARK_HEADER if path.endswith("/") else ACCENT,
                leading=13)),
        Paragraph(desc, ParagraphStyle("tree_desc", fontSize=8, fontName="Helvetica",
            textColor=MUTED, leading=13)),
    ] for path, desc in tree_lines]

    t_tree = Table(tree_data, colWidths=[2.8*inch, 3.88*inch])
    t_tree.setStyle(TableStyle([
        ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [SURFACE, BG]),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(t_tree)
    story.append(sp(16))
    story.append(hr(ACCENT, 1))
    story.append(sp(6))
    story.append(P(
        f"SnipGen v2.0 — Standard Operating Procedure  ·  "
        f"Generated {date.today().strftime('%B %d, %Y')}  ·  "
        "For internal use only. Not for distribution.",
        "caption"))

    # ── Build ──────────────────────────────────────────────────────────────────
    def first_page(canvas, doc):
        cover_page(canvas, doc)

    def later_pages(canvas, doc):
        on_page(canvas, doc)

    doc.build(story, onFirstPage=first_page, onLaterPages=later_pages)
    print(f"✓ SOP written to: {OUTPUT}")

if __name__ == "__main__":
    build()
