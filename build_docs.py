"""Generate SnipGen_Documentation.pdf using ReportLab."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
import os

OUTPUT = "/Users/lxd/summer project/SnipGen_Documentation.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG        = colors.HexColor("#0d1117")
C_SURFACE   = colors.HexColor("#161b22")
C_ACCENT    = colors.HexColor("#238636")
C_BLUE      = colors.HexColor("#1f6feb")
C_TEXT      = colors.HexColor("#e6edf3")
C_MUTED     = colors.HexColor("#8b949e")
C_BORDER    = colors.HexColor("#30363d")
C_CODE_BG   = colors.HexColor("#1c2128")
C_CODE_TEXT = colors.HexColor("#79c0ff")
C_WARN      = colors.HexColor("#d29922")
C_GOOD      = colors.HexColor("#3fb950")
C_WHITE     = colors.white
C_BLACK     = colors.black
C_DARK_GRAY = colors.HexColor("#21262d")

W, H = letter

# ── Styles ────────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

TITLE_STYLE = S("DocTitle",
    fontName="Helvetica-Bold", fontSize=36, textColor=C_WHITE,
    leading=44, spaceAfter=12, alignment=TA_CENTER)

SUBTITLE_STYLE = S("DocSubtitle",
    fontName="Helvetica", fontSize=16, textColor=C_BLUE,
    leading=22, spaceAfter=8, alignment=TA_CENTER)

META_STYLE = S("DocMeta",
    fontName="Helvetica", fontSize=11, textColor=C_MUTED,
    leading=16, spaceAfter=4, alignment=TA_CENTER)

H1_STYLE = S("H1",
    fontName="Helvetica-Bold", fontSize=18, textColor=C_WHITE,
    leading=24, spaceBefore=20, spaceAfter=8,
    borderPad=(0,0,4,0))

H2_STYLE = S("H2",
    fontName="Helvetica-Bold", fontSize=13, textColor=C_BLUE,
    leading=18, spaceBefore=14, spaceAfter=6)

H3_STYLE = S("H3",
    fontName="Helvetica-Bold", fontSize=11, textColor=C_GOOD,
    leading=15, spaceBefore=10, spaceAfter=4)

BODY_STYLE = S("Body",
    fontName="Helvetica", fontSize=10, textColor=C_TEXT,
    leading=15, spaceAfter=6)

BODY_SMALL = S("BodySmall",
    fontName="Helvetica", fontSize=9, textColor=C_TEXT,
    leading=13, spaceAfter=4)

BULLET_STYLE = S("Bullet",
    fontName="Helvetica", fontSize=10, textColor=C_TEXT,
    leading=14, spaceAfter=3, leftIndent=16, bulletIndent=4)

CODE_STYLE = S("Code",
    fontName="Courier", fontSize=8, textColor=C_CODE_TEXT,
    leading=12, spaceAfter=2,
    backColor=C_CODE_BG, borderPad=6,
    leftIndent=8, rightIndent=8)

CODE_COMMENT = S("CodeComment",
    fontName="Courier", fontSize=8, textColor=C_MUTED,
    leading=12, spaceAfter=2, backColor=C_CODE_BG,
    leftIndent=8, rightIndent=8)

NOTE_STYLE = S("Note",
    fontName="Helvetica-Oblique", fontSize=9, textColor=C_WARN,
    leading=13, spaceAfter=4, leftIndent=12)

TOC_H1 = S("TOC1",
    fontName="Helvetica-Bold", fontSize=11, textColor=C_WHITE,
    leading=16, spaceAfter=2, leftIndent=0)

TOC_H2 = S("TOC2",
    fontName="Helvetica", fontSize=10, textColor=C_MUTED,
    leading=14, spaceAfter=1, leftIndent=16)

# ── Table style helpers ───────────────────────────────────────────────────────
def make_table_style(header_bg=C_SURFACE):
    return TableStyle([
        ('BACKGROUND', (0,0), (-1,0), header_bg),
        ('TEXTCOLOR',  (0,0), (-1,0), C_BLUE),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 9),
        ('FONTNAME',   (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE',   (0,1), (-1,-1), 9),
        ('TEXTCOLOR',  (0,1), (-1,-1), C_TEXT),
        ('BACKGROUND', (0,1), (-1,-1), C_CODE_BG),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [C_CODE_BG, C_DARK_GRAY]),
        ('GRID',       (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
    ])

def code_table(lines):
    """Wrap lines of code in a styled single-cell table."""
    text = "<br/>".join(
        f'<font name="Courier" size="8" color="{C_CODE_TEXT.hexval()}">{escape(l)}</font>'
        for l in lines
    )
    cell = Paragraph(text, CODE_STYLE)
    t = Table([[cell]], colWidths=[6.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_CODE_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    return t

def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def body(text):
    # Replace **bold** with <b> tags and `code` with <font>
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', lambda m: f'<font name="Courier" size="9" color="{C_CODE_TEXT.hexval()}">{escape(m.group(1))}</font>', text)
    return Paragraph(text, BODY_STYLE)

def h1(text):
    return Paragraph(text, H1_STYLE)

def h2(text):
    return Paragraph(text, H2_STYLE)

def h3(text):
    return Paragraph(text, H3_STYLE)

def bullet(text):
    import re
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'`([^`]+)`', lambda m: f'<font name="Courier" size="9" color="{C_CODE_TEXT.hexval()}">{escape(m.group(1))}</font>', text)
    return Paragraph(f"&#8226;  {text}", BULLET_STYLE)

def sp(n=6):
    return Spacer(1, n)

def hr():
    return HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=8, spaceBefore=4)

def code_block(lines):
    """Simple code block as a table."""
    joined = "\n".join(lines)
    para = Paragraph(
        "<font name='Courier' size='8'>" +
        "<br/>".join(escape(l).replace(" ", "&nbsp;") for l in lines) +
        "</font>",
        ParagraphStyle("cb", fontName="Courier", fontSize=8, textColor=C_CODE_TEXT,
                       leading=12, backColor=C_CODE_BG, borderPad=0)
    )
    t = Table([[para]], colWidths=[6.5*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), C_CODE_BG),
        ('BOX', (0,0), (-1,-1), 1, C_BORDER),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    return t

def make_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(make_table_style())
    return t

# ── Page template ─────────────────────────────────────────────────────────────
class DocWithHeader(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id='normal'
        )
        template = PageTemplate(id='main', frames=frame,
                                 onPage=self._draw_page)
        self.addPageTemplates([template])

    def _draw_page(self, canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(C_SURFACE)
        canvas.rect(0, H - 36, W, 36, fill=1, stroke=0)
        canvas.setFillColor(C_BLUE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(0.75*inch, H - 22, "SnipGen v0.1.0")
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(W - 0.75*inch, H - 22,
                               "AI-Driven CRISPR Guide RNA Design Platform")
        # Header line
        canvas.setStrokeColor(C_BORDER)
        canvas.setLineWidth(1)
        canvas.line(0, H - 36, W, H - 36)

        # Footer bar
        canvas.setFillColor(C_SURFACE)
        canvas.rect(0, 0, W, 28, fill=1, stroke=0)
        canvas.setStrokeColor(C_BORDER)
        canvas.line(0, 28, W, 28)
        canvas.setFillColor(C_MUTED)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.75*inch, 10, "github.com/ldharwal-asu/snipgen")
        canvas.drawRightString(W - 0.75*inch, 10, f"Page {doc.page}")

        # Full-page background
        canvas.setFillColor(C_BG)
        canvas.rect(0, 28, W, H - 64, fill=1, stroke=0)
        canvas.restoreState()

# ── Build content ─────────────────────────────────────────────────────────────
def build():
    doc = DocWithHeader(
        OUTPUT,
        pagesize=letter,
        leftMargin=0.75*inch,
        rightMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.55*inch,
        title="SnipGen Documentation",
        author="SnipGen Project",
        subject="CRISPR Guide RNA Design Platform",
    )

    story = []

    # ── TITLE PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.8*inch))
    story.append(Paragraph("✂ &nbsp;SnipGen", TITLE_STYLE))
    story.append(sp(8))
    story.append(Paragraph("AI-Driven CRISPR Guide RNA Design Platform", SUBTITLE_STYLE))
    story.append(sp(20))
    # Version badge table
    badge_data = [["Version", "v0.1.0"], ["Date", "March 2026"], ["Language", "Python 3.11+"], ["License", "Open Source"]]
    bt = Table(badge_data, colWidths=[1.2*inch, 1.8*inch])
    bt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), C_DARK_GRAY),
        ('BACKGROUND', (1,0), (1,-1), C_CODE_BG),
        ('TEXTCOLOR',  (0,0), (0,-1), C_MUTED),
        ('TEXTCOLOR',  (1,0), (1,-1), C_WHITE),
        ('FONTNAME',   (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE',   (0,0), (-1,-1), 10),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('GRID',       (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(Table([[bt]], colWidths=[W - 1.5*inch]))
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("github.com/ldharwal-asu/snipgen", META_STYLE))
    story.append(Paragraph("snipgen.onrender.com", META_STYLE))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────────
    story.append(h1("Table of Contents"))
    story.append(hr())
    story.append(sp(4))
    toc_entries = [
        ("1", "Introduction", "3"),
        ("  1.1", "What is CRISPR?", "3"),
        ("  1.2", "What is a Guide RNA?", "3"),
        ("  1.3", "Why Design Matters", "3"),
        ("  1.4", "What SnipGen Does", "4"),
        ("2", "Architecture Overview", "4"),
        ("  2.1", "System Architecture", "4"),
        ("  2.2", "Module Map", "5"),
        ("  2.3", "Key Design Decisions", "5"),
        ("3", "Data Model — GRNACandidate", "6"),
        ("  3.1", "Overview", "6"),
        ("  3.2", "Field Reference", "6"),
        ("  3.3", "Methods", "7"),
        ("4", "Utility Modules", "7"),
        ("  4.1", "nucleotide.py — Pure DNA Utilities", "7"),
        ("  4.2", "logger.py — Logging Configuration", "8"),
        ("5", "Input and Preprocessing", "8"),
        ("  5.1", "FastaReader", "8"),
        ("  5.2", "SequenceCleaner", "9"),
        ("  5.3", "WindowExtractor", "9"),
        ("6", "Filters", "10"),
        ("  6.1", "Design Philosophy — Annotate, Never Discard", "10"),
        ("  6.2", "GCFilter", "11"),
        ("  6.3", "PAMFilter", "11"),
        ("  6.4", "OffTargetFilter", "12"),
        ("  6.5", "FilterChain", "13"),
        ("7", "Scoring System", "13"),
        ("  7.1", "RuleScorer — Deterministic Scoring", "13"),
        ("  7.2", "ML Integration Hook", "14"),
        ("  7.3", "CompositeScorer", "15"),
        ("8", "Output System", "15"),
        ("  8.1", "OutputWriter", "15"),
        ("  8.2", "CSV Output", "16"),
        ("  8.3", "JSON Output", "16"),
        ("9", "Pipeline Orchestrator", "17"),
        ("  9.1", "PipelineConfig", "17"),
        ("  9.2", "SnipGenPipeline.run() — Step by Step", "17"),
        ("  9.3", "PipelineResult", "18"),
        ("10", "CLI Reference", "18"),
        ("  10.1", "Installation", "18"),
        ("  10.2", "snipgen design", "18"),
        ("  10.3", "snipgen validate", "19"),
        ("  10.4", "snipgen list-variants", "19"),
        ("11", "Web Application", "19"),
        ("  11.1", "FastAPI Backend", "19"),
        ("  11.2", "Frontend UI", "20"),
        ("  11.3", "Deployment on Render", "21"),
        ("12", "Test Suite", "21"),
        ("  12.1", "Test Strategy", "21"),
        ("  12.2", "Test File Summary", "22"),
        ("  12.3", "Running Tests", "22"),
        ("  12.4", "Coverage Summary", "22"),
        ("Appendix A", "Quick Reference", "23"),
    ]

    for num, title, page in toc_entries:
        is_section = not num.startswith(" ") and num != "Appendix A" or num == "Appendix A"
        style = TOC_H1 if is_section else TOC_H2
        dots = "." * max(2, 60 - len(num) - len(title) - len(page))
        story.append(Paragraph(
            f'<font name="Helvetica-Bold">{num}</font>&nbsp;&nbsp;{title}'
            f'<font color="{C_MUTED.hexval()}">&nbsp;{dots}&nbsp;{page}</font>',
            style
        ))
    story.append(PageBreak())

    # ── SECTION 1: INTRODUCTION ───────────────────────────────────────────────
    story.append(h1("1. Introduction"))
    story.append(hr())

    story.append(h2("1.1 What is CRISPR?"))
    story.append(body("CRISPR (Clustered Regularly Interspaced Short Palindromic Repeats) is a revolutionary gene-editing technology derived from a natural bacterial immune system. The CRISPR-Cas system uses a guide RNA (gRNA) molecule to direct the Cas9 nuclease to a specific DNA location in the genome, where it makes a precise double-strand cut."))
    story.append(body("This enables researchers to **knock out genes**, **correct disease-causing mutations**, or **insert new genetic material** with high precision. Since its first use in human cells in 2013, CRISPR has transformed molecular biology, medicine, agriculture, and drug discovery."))

    story.append(h2("1.2 What is a Guide RNA?"))
    story.append(body("A guide RNA (gRNA) is a short synthetic RNA molecule — typically **20 nucleotides (nt)** long — that is complementary to the target DNA sequence. It forms a complex with the Cas9 protein and guides it to the exact genomic location. The gRNA has two main regions:"))
    story.append(bullet("**Spacer sequence (20 nt):** The variable region that base-pairs with the target DNA strand through Watson-Crick complementarity"))
    story.append(bullet("**Scaffold:** The fixed structural backbone that binds the Cas9 protein and maintains the gRNA-Cas9 complex"))
    story.append(sp(4))
    story.append(body("For a gRNA to work, the target DNA must be immediately adjacent to a **Protospacer Adjacent Motif (PAM)**. For the most common system (SpCas9), the PAM is **NGG** on the non-template strand, immediately 3' of the target sequence."))

    story.append(h2("1.3 Why Design Matters"))
    story.append(body("Designing an effective gRNA is not trivial. A poorly designed gRNA can cause serious problems:"))
    story.append(bullet("**Low on-target efficiency:** The guide fails to cut the intended genomic location, wasting experimental resources"))
    story.append(bullet("**Off-target effects:** The guide cuts elsewhere in the genome, causing unintended and potentially harmful mutations"))
    story.append(bullet("**Secondary structure formation:** The spacer sequence folds back on itself or the scaffold, preventing Cas9 from loading properly"))
    story.append(bullet("**Poor transcription:** Certain sequence compositions prevent efficient transcription of the gRNA from its promoter"))
    story.append(sp(4))
    story.append(body("Manual design is slow, inconsistent, and error-prone. For any target gene, there may be hundreds or thousands of possible gRNA positions — each needs to be evaluated against multiple biochemical criteria. **Automation is essential.**"))

    story.append(h2("1.4 What SnipGen Does"))
    story.append(body("SnipGen is a Python-based automated pipeline that takes a target DNA sequence (in FASTA format) and returns a ranked list of optimised gRNA candidates:"))
    story.append(bullet("Reads target DNA sequences from standard FASTA files using BioPython"))
    story.append(bullet("Preprocesses sequences: normalises case, handles ambiguous nucleotides, masks low-complexity repeats"))
    story.append(bullet("Extracts all possible 20-nt gRNA candidates from both DNA strands by sliding a window across the sequence"))
    story.append(bullet("Applies three rule-based filters: GC content, PAM site detection, and off-target heuristics"))
    story.append(bullet("Scores passing candidates using a deterministic 5-component rule scorer, with an optional ML model hook"))
    story.append(bullet("Outputs ranked candidates as CSV and JSON files, plus a full audit log of rejected candidates"))
    story.append(bullet("Provides both a command-line interface (`snipgen design`) and a live web application"))
    story.append(PageBreak())

    # ── SECTION 2: ARCHITECTURE ───────────────────────────────────────────────
    story.append(h1("2. Architecture Overview"))
    story.append(hr())

    story.append(h2("2.1 System Architecture"))
    story.append(body("SnipGen follows a strict linear pipeline architecture where data flows through discrete, independently testable stages. Each stage has a single responsibility:"))
    story.append(sp(4))
    story.append(code_block([
        "FASTA File (input)",
        "     |",
        "     v",
        " FastaReader  ............  BioPython generator, validates records",
        "     |",
        "     v",
        " SequenceCleaner  .......  uppercase, strip non-ACGTN, mask repeats",
        "     |",
        "     v",
        " WindowExtractor  .......  20-nt sliding window, both strands",
        "     |                     yields list[GRNACandidate]",
        "     v",
        " FilterChain:",
        "   +-- GCFilter  ..........  40% <= GC% <= 70%",
        "   +-- PAMFilter  .........  NGG / IUPAC registry lookup",
        "   +-- OffTargetFilter  ...  seed GC, poly-T, homopolymer",
        "     |                    |",
        "     v (passed)           v (rejected) --> rejected_candidates.csv",
        " CompositeScorer:",
        "   +-- RuleScorer  ........  5-component weighted formula",
        "   +-- MLScorer  ..........  Protocol stub / sklearn model",
        "     |",
        "     v",
        " Sort DESC by final_score  ->  top-N cutoff",
        "     |",
        "     v",
        " OutputWriter  ..........  candidates.csv + candidates.json",
    ]))

    story.append(h2("2.2 Module Map"))
    story.append(code_block([
        "snipgen/",
        "  __init__.py              Package version (0.1.0)",
        "  cli.py                   Click CLI: design / validate / list-variants",
        "  pipeline.py              Orchestrator + PipelineConfig + PipelineResult",
        "  models/",
        "    grna_candidate.py      Central dataclass (shared data contract)",
        "  utils/",
        "    nucleotide.py          Pure DNA utilities (GC, revcomp, IUPAC)",
        "    logger.py              Logging configuration",
        "  io/",
        "    fasta_reader.py        BioPython generator-based FASTA reader",
        "    output_writer.py       CSV + JSON output writer",
        "  preprocessing/",
        "    sequence_cleaner.py    Normalise SeqRecord -> clean string",
        "    window_extractor.py    Extract 20-nt candidates from both strands",
        "  filters/",
        "    base_filter.py         Abstract base (annotate, never discard)",
        "    gc_filter.py           GC content 40-70%",
        "    pam_filter.py          PAM site validation (IUPAC registry)",
        "    offtarget_filter.py    Seed GC, poly-T, homopolymer heuristics",
        "    filter_chain.py        Sequential filter composition",
        "  scoring/",
        "    rule_scorer.py         Deterministic 5-component scorer",
        "    ml_scorer.py           MLScorerProtocol + stub + sklearn hook",
        "    composite_scorer.py    Weighted rule + ML aggregation",
        "webapp/",
        "  app.py                   FastAPI web application (3 endpoints)",
        "  static/",
        "    index.html             Single-page UI (drag-and-drop, results table)",
    ]))

    story.append(h2("2.3 Key Design Decisions"))
    design_data = [
        ["Decision", "Rationale"],
        ["Filters annotate, never discard", "Complete audit trail; every candidate has per-filter verdicts in the output"],
        ["GRNACandidate as shared dataclass", "Single source of truth; type-safe across all pipeline stages"],
        ["MLScorerProtocol (structural typing)", "Any ML framework (sklearn/torch/ONNX) plugs in without changing callers"],
        ["PAM registry dict", "Add new Cas variants with one dict entry, zero code changes"],
        ["Generator-based FASTA reading", "Constant memory usage even for chromosome-scale FASTA files (GBs)"],
        ["PipelineConfig decoupled from CLI", "Pipeline fully testable without invoking Click; pure dataclass"],
        ["CompositeScorer graceful degradation", "ml_weight collapsed to 0 when no model loaded — tool works without ML"],
    ]
    story.append(make_table(design_data, col_widths=[2.6*inch, 3.9*inch]))
    story.append(PageBreak())

    # ── SECTION 3: DATA MODEL ─────────────────────────────────────────────────
    story.append(h1("3. Data Model — GRNACandidate"))
    story.append(hr())

    story.append(h2("3.1 Overview"))
    story.append(body("`GRNACandidate` is the central data contract that flows through every stage of the pipeline. It is a Python `dataclass` defined in `snipgen/models/grna_candidate.py`. Every module from `WindowExtractor` to `OutputWriter` receives and returns `GRNACandidate` objects, ensuring type safety and a single source of truth."))

    story.append(h2("3.2 Field Reference"))
    story.append(h3("Core Sequence Fields"))
    core_data = [
        ["Field", "Type", "Description"],
        ["sequence", "str", "20-nt spacer sequence (5'→3') — the actual gRNA targeting region"],
        ["pam", "str", "PAM sequence extracted immediately 3' (or 5' for Cpf1) of the spacer"],
        ["chromosome", "str", "Source record ID from the FASTA header (e.g., chr1, seq1)"],
        ["start", "int", "0-based start position on the original + strand genome coordinates"],
        ["end", "int", "0-based end position (exclusive), consistent with Python slice notation"],
        ["strand", "str", "'+' if from forward strand, '-' if from reverse complement scan"],
        ["gc_content", "float", "Fraction of G+C nucleotides in the spacer, range [0.0-1.0]"],
    ]
    story.append(make_table(core_data, col_widths=[1.4*inch, 0.7*inch, 4.4*inch]))

    story.append(sp(6))
    story.append(h3("Filter Pass/Fail Flags  (default: False, set by filter modules)"))
    flag_data = [
        ["Field", "Type", "Set By"],
        ["gc_pass", "bool", "GCFilter — True if GC content within [min_gc, max_gc]"],
        ["pam_pass", "bool", "PAMFilter — True if PAM matches IUPAC-expanded valid set"],
        ["offtarget_pass", "bool", "OffTargetFilter — True if all three heuristic checks pass"],
    ]
    story.append(make_table(flag_data, col_widths=[1.4*inch, 0.7*inch, 4.4*inch]))

    story.append(sp(6))
    story.append(h3("Off-Target Heuristic Detail  (set by OffTargetFilter)"))
    ot_data = [
        ["Field", "Type", "Description"],
        ["seed_gc", "float", "GC fraction of the 12 nt proximal to the PAM (seed region)"],
        ["has_poly_t", "bool", "True if the spacer contains TTTT (Pol-III termination signal)"],
        ["has_homopolymer", "bool", "True if any 4+ run of identical nucleotides is present"],
    ]
    story.append(make_table(ot_data, col_widths=[1.4*inch, 0.7*inch, 4.4*inch]))

    story.append(sp(6))
    story.append(h3("Score Fields  (set by scoring modules)"))
    score_data = [
        ["Field", "Type", "Description"],
        ["rule_score", "float", "Deterministic rule-based score, range [0.0-1.0]"],
        ["ml_score", "float", "ML model score; defaults to 0.5 (neutral) when no model loaded"],
        ["final_score", "float", "Weighted combination: (rule_w * rule + ml_w * ml) / total_w"],
    ]
    story.append(make_table(score_data, col_widths=[1.4*inch, 0.7*inch, 4.4*inch]))

    story.append(h2("3.3 Methods"))
    story.append(body("**`passes_all_filters() -> bool`** — Returns True if and only if `gc_pass AND pam_pass AND offtarget_pass` are all True. Called by `FilterChain` to separate candidates into passed and rejected lists."))
    story.append(body("**`to_dict() -> dict`** — Converts all 16 fields to a flat dictionary for CSV/JSON export. Rounds floating-point values to 4 decimal places. The key names match the CSV column headers exactly."))
    story.append(PageBreak())

    # ── SECTION 4: UTILITIES ──────────────────────────────────────────────────
    story.append(h1("4. Utility Modules"))
    story.append(hr())

    story.append(h2("4.1 nucleotide.py — Pure DNA Utilities"))
    story.append(body("Location: `snipgen/utils/nucleotide.py` — Pure functions with no external state or side effects. Imported by nearly every other module."))

    story.append(h3("IUPAC_MAP"))
    story.append(body("A dictionary mapping IUPAC ambiguity codes to their concrete nucleotide expansions. Used by `expand_iupac()` to generate all valid PAM sequences:"))
    iupac_data = [
        ["Code", "Bases", "Code", "Bases", "Code", "Bases"],
        ["A", "A", "R", "A, G", "B", "C, G, T"],
        ["C", "C", "Y", "C, T", "D", "A, G, T"],
        ["G", "G", "S", "G, C", "H", "A, C, T"],
        ["T", "T", "W", "A, T", "V", "A, C, G"],
        ["N", "A,C,G,T", "K", "G, T", "M", "A, C"],
    ]
    it = Table(iupac_data, colWidths=[0.5*inch, 1.0*inch, 0.5*inch, 1.0*inch, 0.5*inch, 1.0*inch])
    it.setStyle(make_table_style())
    story.append(it)

    story.append(sp(8))
    story.append(h3("Function Reference"))
    func_data = [
        ["Function", "Signature", "Description"],
        ["reverse_complement", "seq: str -> str", "Returns reverse complement. Uses str.maketrans complement map then reversal."],
        ["gc_content", "seq: str -> float", "Returns G+C fraction [0.0-1.0]. Returns 0.0 for empty input."],
        ["expand_iupac", "pattern: str -> list[str]", "Expands IUPAC pattern to all concrete sequences via itertools.product. 'NGG' -> ['AGG','CGG','GGG','TGG']."],
        ["has_homopolymer", "seq: str, min_run=4 -> bool", "True if any single base repeats min_run+ times. Regex: (.){min_run,}"],
        ["has_poly_t", "seq: str, min_run=4 -> bool", "True if 'T' * min_run appears. Checks Pol-III termination signal (TTTT)."],
        ["is_valid_dna", "seq: str -> bool", "True if sequence contains only [ACGTNacgtn]. Used for validation."],
    ]
    story.append(make_table(func_data, col_widths=[1.4*inch, 1.8*inch, 3.3*inch]))

    story.append(h2("4.2 logger.py — Logging Configuration"))
    story.append(body("Location: `snipgen/utils/logger.py`"))
    story.append(body("**`get_logger(name, verbose=False)`** — Returns a named logger with a stderr StreamHandler. Format: `HH:MM:SS [LEVEL] name: message`. Level is DEBUG if verbose, else WARNING. Prevents duplicate handlers by checking existing handlers first."))
    story.append(body("**`configure_root(verbose=False)`** — Sets the root `snipgen` logger level. Called exactly once at CLI startup from `cli.py`. When verbose=True, all submodule loggers emit DEBUG messages throughout the pipeline."))
    story.append(PageBreak())

    # ── SECTION 5: PREPROCESSING ──────────────────────────────────────────────
    story.append(h1("5. Input and Preprocessing"))
    story.append(hr())

    story.append(h2("5.1 FastaReader — FASTA Parsing"))
    story.append(body("Location: `snipgen/io/fasta_reader.py` — Generator-based FASTA reader using BioPython. Keeps memory constant regardless of input file size by yielding one `SeqRecord` at a time."))

    story.append(h3("Constructor Parameters"))
    fr_data = [
        ["Parameter", "Default", "Description"],
        ["path", "required", "Path to FASTA file (.fasta, .fa, .fna). FileNotFoundError raised immediately if missing."],
        ["min_length", "23", "Minimum sequence length to yield. 23 = 20 nt spacer + 3 nt PAM (smallest possible gRNA window)."],
    ]
    story.append(make_table(fr_data, col_widths=[1.2*inch, 0.8*inch, 4.5*inch]))

    story.append(h3("How it works"))
    story.append(code_block([
        "# Generator pattern — memory constant for chromosome-scale files",
        "with open(self.path) as fh:",
        "    for record in SeqIO.parse(fh, 'fasta'):  # BioPython generator",
        "        if len(str(record.seq)) < self.min_length:",
        "            logger.warning('Skipping short record: %s', record.id)",
        "            continue",
        "        yield record  # one record at a time, constant memory",
    ]))
    story.append(body("BioPython's `SeqIO.parse()` is itself a generator — it does not load the entire file into memory. `FastaReader.__iter__()` wraps it with validation logic while preserving this memory efficiency."))
    story.append(h3("Validation Behavior"))
    story.append(bullet("Sequences below `min_length`: Skipped with WARNING log"))
    story.append(bullet("Non-ACGTN characters: Warning logged, record still yielded (cleaning handled downstream by SequenceCleaner)"))
    story.append(bullet("Missing file: `FileNotFoundError` raised immediately in `__init__()`, before any iteration"))

    story.append(h2("5.2 SequenceCleaner — Sequence Normalization"))
    story.append(body("Location: `snipgen/preprocessing/sequence_cleaner.py` — Converts a raw BioPython `SeqRecord` into a clean uppercase `CleanedSequence` NamedTuple."))
    story.append(h3("Constructor Parameters"))
    sc_data = [
        ["Parameter", "Default", "Description"],
        ["max_n_fraction", "0.05", "Warn if N content exceeds 5% of sequence length. Processing continues regardless."],
        ["mask_homopolymer_run", "10", "Replace homopolymer runs >= this length with N's. Set None to disable masking entirely."],
    ]
    story.append(make_table(sc_data, col_widths=[1.8*inch, 0.8*inch, 3.9*inch]))

    story.append(h3("Five Cleaning Steps (in order)"))
    steps_data = [
        ["Step", "Operation", "Purpose"],
        ["1", "str(record.seq).upper()", "Normalise case — all downstream comparisons use uppercase"],
        ["2", "Strip whitespace", "Remove spaces, newlines, carriage returns from malformed FASTA input"],
        ["3", "Replace non-ACGTN with N", "Convert invalid characters to N; count and log as warning"],
        ["4", "Check N fraction", "Warn if N content > max_n_fraction (5%); indicates low-quality input"],
        ["5", "Mask homopolymers (optional)", "Replace runs >= mask_homopolymer_run nt with N's to avoid candidates in repetitive regions"],
    ]
    story.append(make_table(steps_data, col_widths=[0.4*inch, 2.0*inch, 4.1*inch]))

    story.append(body("**Why mask homopolymers?** Long repeats (e.g., AAAAAAAAAA) are abundant in genomes. CRISPR guides targeting them have high off-target risk because the repetitive context means the same sequence exists at many genomic loci. Masking prevents wasting scoring budget on these near-guaranteed off-target candidates."))

    story.append(h2("5.3 WindowExtractor — Candidate Extraction"))
    story.append(body("Location: `snipgen/preprocessing/window_extractor.py` — Slides a window across both DNA strands to extract all possible gRNA candidates as `GRNACandidate` objects."))
    story.append(h3("Constructor Parameters"))
    we_data = [
        ["Parameter", "Default", "Description"],
        ["guide_length", "20", "Spacer length in nucleotides. Standard for SpCas9."],
        ["pam_length", "3", "PAM window length (3 for SpCas9 NGG, 6 for SaCas9 NNGRRT, 4 for Cpf1)"],
        ["pam_position", "'3prime'", "'3prime' for SpCas9/SaCas9 (PAM after spacer); '5prime' for Cpf1 (PAM before spacer)"],
    ]
    story.append(make_table(we_data, col_widths=[1.3*inch, 0.8*inch, 4.4*inch]))

    story.append(h3("Sliding Window (3' PAM systems)"))
    story.append(code_block([
        "Window size = guide_length + pam_length = 23 nt",
        "",
        "Position i:  [ spacer (20 nt) ][ PAM (3 nt) ]",
        "             i               i+20           i+23",
        "             |_______________|_______________|",
        "             seq[i:i+20]     seq[i+20:i+23]",
    ]))
    story.append(body("The extractor scans both the forward strand and the `reverse_complement()` of the cleaned sequence. For each position, a `GRNACandidate` is created. Candidates with any 'N' in the spacer are skipped (they target masked/ambiguous regions)."))
    story.append(h3("Coordinate Adjustment for Minus Strand"))
    story.append(body("When scanning the reverse complement, coordinates must be converted back to original (+) strand genomic space:"))
    story.append(code_block([
        "# Convert minus-strand scan position back to original coordinates",
        "original_start = seq_len - scan_end    # e.g. 1000 - 43 = 957",
        "original_end   = seq_len - scan_start  # e.g. 1000 - 23 = 977",
        "",
        "# This ensures start < end always holds in original coordinate space",
    ]))
    story.append(PageBreak())

    # ── SECTION 6: FILTERS ────────────────────────────────────────────────────
    story.append(h1("6. Filters"))
    story.append(hr())

    story.append(h2("6.1 Design Philosophy — Annotate, Never Discard"))
    story.append(body("Location: `snipgen/filters/base_filter.py`"))
    story.append(body("All filters follow a critical architectural principle: **they annotate candidates with pass/fail boolean flags rather than removing them from the candidate list.** The abstract base class enforces this contract:"))
    story.append(code_block([
        "class BaseFilter(ABC):",
        "    @abstractmethod",
        "    def apply(self, candidate: GRNACandidate) -> GRNACandidate:",
        "        '''Mutate the candidate's flags in-place and return it.'''",
        "        ...",
        "",
        "    @property",
        "    @abstractmethod",
        "    def name(self) -> str:",
        "        '''Human-readable filter name for logging.'''",
        "        ...",
    ]))
    story.append(body("**Why this matters:**"))
    story.append(bullet("Every candidate ever considered is tracked — even rejected ones retain all their filter verdicts"))
    story.append(bullet("`FilterChain` separates passed and rejected lists *after* all filters have run"))
    story.append(bullet("Rejected candidates are written to `rejected_candidates.csv` with per-filter flags for debugging"))
    story.append(bullet("You can see exactly *which* filter(s) a candidate failed, enabling threshold tuning"))

    story.append(h2("6.2 GCFilter — GC Content Validation"))
    story.append(body("Location: `snipgen/filters/gc_filter.py`"))
    story.append(body("Validates that the GC fraction of the spacer falls within the acceptable range [min_gc, max_gc]. Default: 40% – 70%."))
    story.append(code_block([
        "class GCFilter(BaseFilter):",
        "    def __init__(self, min_gc: float = 0.40, max_gc: float = 0.70):",
        "        self.min_gc = min_gc",
        "        self.max_gc = max_gc",
        "",
        "    def apply(self, candidate: GRNACandidate) -> GRNACandidate:",
        "        candidate.gc_pass = self.min_gc <= candidate.gc_content <= self.max_gc",
        "        return candidate",
    ]))
    story.append(h3("Scientific Rationale for Thresholds"))
    gc_rationale = [
        ["Condition", "Effect", "Mechanism"],
        ["GC < 40%", "Low efficiency (fail)", "Insufficient Tm — gRNA-DNA duplex too unstable for R-loop formation"],
        ["GC 40–70%", "Acceptable range (pass)", "Balanced thermodynamic stability; optimal Cas9 loading and cleavage"],
        ["GC > 70%", "Low efficiency (fail)", "Secondary structures (hairpins, G-quadruplexes) block Cas9 loading"],
    ]
    story.append(make_table(gc_rationale, col_widths=[1.3*inch, 1.7*inch, 3.5*inch]))
    story.append(Paragraph("<i>Sources: Doench et al. 2016 (Nature Biotechnology); Moreno-Mateos et al. 2015 (Nature Methods)</i>", NOTE_STYLE))

    story.append(h2("6.3 PAMFilter — PAM Site Detection"))
    story.append(body("Location: `snipgen/filters/pam_filter.py`"))
    story.append(body("Validates that the PAM sequence extracted alongside the spacer matches the recognition motif for the selected Cas variant. Uses IUPAC expansion to pre-compute all valid PAMs at construction time."))
    story.append(h3("PAM Registry"))
    pam_data = [
        ["Variant", "PAM Pattern", "Position", "Length", "Notes"],
        ["SpCas9", "NGG", "3' end", "3 nt", "Most common; broadest genomic targeting"],
        ["SaCas9", "NNGRRT", "3' end", "6 nt", "Compact protein; preferred for AAV delivery"],
        ["Cpf1 (Cas12a)", "TTTV", "5' end", "4 nt", "AT-rich genomes; cuts both strands with offset"],
        ["xCas9", "NG", "3' end", "2 nt", "Engineered SpCas9; relaxed PAM requirement"],
        ["Cas9-NG", "NG", "3' end", "2 nt", "Alternative SpCas9 variant with NG PAM"],
    ]
    story.append(make_table(pam_data, col_widths=[1.1*inch, 1.0*inch, 0.8*inch, 0.7*inch, 2.9*inch]))
    story.append(h3("IUPAC Expansion and O(1) Lookup"))
    story.append(code_block([
        "# At construction time: expand IUPAC pattern -> frozenset of all valid PAMs",
        "PAMFilter('SpCas9'):",
        "    valid_pams = frozenset(expand_iupac('NGG'))",
        "                = frozenset({'AGG', 'CGG', 'GGG', 'TGG'})",
        "",
        "PAMFilter('SaCas9'):",
        "    valid_pams = frozenset(expand_iupac('NNGRRT'))  # 64 combinations",
        "",
        "# At filter time: O(1) set membership check",
        "def apply(self, candidate):",
        "    pam = candidate.pam.upper()[:self.pam_length].ljust(self.pam_length, 'N')",
        "    candidate.pam_pass = pam in self.valid_pams",
    ]))

    story.append(h2("6.4 OffTargetFilter — Off-Target Risk Heuristics"))
    story.append(body("Location: `snipgen/filters/offtarget_filter.py`"))
    story.append(body("Applies three sequence-composition heuristics to flag candidates with elevated off-target risk. These checks do **not** require genome alignment — they are fast O(n) string operations on the 20-nt spacer."))
    story.append(h3("Constructor Parameters"))
    ot_params = [
        ["Parameter", "Default", "Description"],
        ["seed_length", "12", "Number of PAM-proximal nucleotides forming the seed region"],
        ["max_seed_gc", "0.75", "Reject if seed region GC exceeds this fraction"],
        ["poly_t_run", "4", "Reject if any run of T's is >= this length (TTTT)"],
        ["homopolymer_run", "4", "Reject if any identical-base run is >= this length"],
    ]
    story.append(make_table(ot_params, col_widths=[1.5*inch, 0.8*inch, 4.2*inch]))

    story.append(h3("Check 1: Seed Region GC Content"))
    story.append(body("The seed region is the **12 nucleotides proximal to the PAM** (`spacer[-12:]` for 3' PAM systems). This region is critical — it initiates the RNA-DNA hybrid (R-loop) that enables Cas9 binding."))
    story.append(code_block([
        "seed = candidate.sequence[-self.seed_length:]   # last 12 nt",
        "candidate.seed_gc = gc_content(seed)",
        "seed_ok = candidate.seed_gc <= self.max_seed_gc  # reject if > 75%",
    ]))
    story.append(body("**Why high seed GC is risky:** Stronger base-pairing in the seed region allows more mismatches to be tolerated in the non-seed region. High-GC seed sequences are more promiscuous — they can find partial matches at off-target genomic loci more easily than low-GC seeds."))

    story.append(h3("Check 2: Poly-T Avoidance"))
    story.append(code_block([
        "candidate.has_poly_t = has_poly_t(seq, min_run=self.poly_t_run)",
        "poly_t_ok = not candidate.has_poly_t",
    ]))
    story.append(body("Four or more consecutive T nucleotides (**TTTT**) constitute a **Pol-III transcription termination signal** when the gRNA is expressed from a U6 promoter (the standard promoter for gRNA expression in mammalian cells). If TTTT appears anywhere in the spacer, the transcript is prematurely terminated, producing a truncated non-functional gRNA."))

    story.append(h3("Check 3: Homopolymer Run Detection"))
    story.append(code_block([
        "candidate.has_homopolymer = has_homopolymer(seq, min_run=self.homopolymer_run)",
        "homopolymer_ok = not candidate.has_homopolymer",
        "",
        "# Final verdict: all three must pass",
        "candidate.offtarget_pass = seed_ok and poly_t_ok and homopolymer_ok",
    ]))
    story.append(body("Runs of 4+ identical nucleotides (AAAA, CCCC, GGGG, TTTT) are associated with reduced on-target cleavage efficiency. **G-quartet (GGGG)** runs are especially problematic — they form stable G-quadruplex secondary structures that interfere with gRNA folding and Cas9 loading."))

    story.append(h2("6.5 FilterChain — Sequential Filter Composition"))
    story.append(body("Location: `snipgen/filters/filter_chain.py`"))
    story.append(code_block([
        "def run(self, candidates):",
        "    # Phase 1: annotate every candidate with every filter's verdict",
        "    for filt in self.filters:",
        "        for candidate in candidates:",
        "            filt.apply(candidate)   # mutates flags in-place",
        "",
        "    # Phase 2: separate based on all-pass requirement",
        "    passed   = [c for c in candidates if c.passes_all_filters()]",
        "    rejected = [c for c in candidates if not c.passes_all_filters()]",
        "    return passed, rejected",
    ]))
    story.append(body("Default filter order: GCFilter → PAMFilter → OffTargetFilter. All three must pass for a candidate to proceed to scoring. The `filter_summary()` method returns per-filter rejection counts for pipeline statistics."))
    story.append(PageBreak())

    # ── SECTION 7: SCORING ────────────────────────────────────────────────────
    story.append(h1("7. Scoring System"))
    story.append(hr())

    story.append(h2("7.1 RuleScorer — Deterministic Scoring"))
    story.append(body("Location: `snipgen/scoring/rule_scorer.py`"))
    story.append(body("Assigns a score in [0.0, 1.0] to each candidate based on five independently weighted sequence-quality components. The score is entirely deterministic — same input always produces the same output."))
    story.append(h3("The Five Components"))
    scorer_data = [
        ["Component", "Weight", "Formula", "Rationale"],
        ["GC proximity to 50%", "0.25", "max(0, 1 - |gc-0.5| / 0.3)", "Peaks at 50%; falls off toward 40%/70% bounds"],
        ["Seed region GC", "0.20", "max(0, 1 - seed_gc)", "Lower seed GC = less off-target binding risk"],
        ["G at position 1", "0.15", "1.0 if seq[0]=='G' else 0.0", "U6 promoter most efficient when transcript starts with G"],
        ["No homopolymer", "0.20", "1.0 if clean else 0.0", "Binary: homopolymers strongly reduce on-target efficiency"],
        ["No poly-T", "0.20", "1.0 if clean else 0.0", "Binary: poly-T causes Pol-III premature termination"],
    ]
    story.append(make_table(scorer_data, col_widths=[1.5*inch, 0.65*inch, 1.9*inch, 2.45*inch]))
    story.append(Paragraph("<i>Note: Weights sum to exactly 1.0, so rule_score is always in [0.0, 1.0].</i>", NOTE_STYLE))

    story.append(h3("Example Calculation"))
    story.append(body("For a candidate with gc=0.50, seed_gc=0.42, starts with G, no homopolymer, no poly-T:"))
    story.append(code_block([
        "gc_score    = 1.0 - |0.50 - 0.50| / 0.3 = 1.000",
        "seed_score  = 1.0 - 0.42               = 0.580",
        "g1_score    = 1.0  (starts with G)",
        "homo_score  = 1.0  (no homopolymer)",
        "polyt_score = 1.0  (no poly-T)",
        "",
        "rule_score = 0.25 x 1.000  +  0.20 x 0.580  +  0.15 x 1.0",
        "           + 0.20 x 1.0    +  0.20 x 1.0",
        "           = 0.250 + 0.116 + 0.150 + 0.200 + 0.200",
        "           = 0.916",
    ]))

    story.append(h2("7.2 ML Integration Hook"))
    story.append(body("Location: `snipgen/scoring/ml_scorer.py`"))
    story.append(body("Rather than an abstract base class (which requires explicit inheritance), SnipGen uses Python's `typing.Protocol` for **structural subtyping**. Any class that implements `score()` and `is_available()` satisfies the protocol automatically — no `class MyScorer(MLScorerProtocol)` needed."))
    story.append(code_block([
        "@runtime_checkable",
        "class MLScorerProtocol(Protocol):",
        "    def score(self, candidates: list[GRNACandidate]) -> list[float]:",
        "        '''Batch scoring -- returns parallel list of scores in [0.0, 1.0].'''",
        "        ...",
        "    def is_available(self) -> bool:",
        "        '''True if the model artifact is loaded and ready.'''",
        "        ...",
    ]))
    story.append(body("**Why batch scoring?** Neural networks and sklearn models benefit from vectorized inference. Requiring batch input at the protocol level ensures all implementations can be efficient."))

    story.append(h3("PassthroughMLScorer (v1 default)"))
    story.append(code_block([
        "class PassthroughMLScorer:",
        "    def score(self, candidates): return [0.5] * len(candidates)",
        "    def is_available(self):      return False",
    ]))
    story.append(body("Returns a neutral 0.5 for all candidates. With the default `ml_weight=0.0`, this has zero effect on `final_score`. The tool is fully functional without any ML model."))

    story.append(h3("SklearnMLScorer — Feature Engineering (84 dimensions)"))
    ml_feat = [
        ["Feature Group", "Dimensions", "Description"],
        ["Spacer one-hot encoding", "80", "4 bases x 20 positions: [A,C,G,T] at each position as binary vector"],
        ["gc_content", "1", "GC fraction of the full spacer, float [0.0-1.0]"],
        ["seed_gc", "1", "GC fraction of seed region (last 12 nt), float [0.0-1.0]"],
        ["has_poly_t", "1", "Binary: 1.0 if TTTT present, 0.0 otherwise"],
        ["has_homopolymer", "1", "Binary: 1.0 if 4+ identical bases present, 0.0 otherwise"],
        ["Total", "84", "Compatible with Random Forest, Gradient Boosting, Logistic Regression"],
    ]
    story.append(make_table(ml_feat, col_widths=[1.9*inch, 1.0*inch, 3.6*inch]))

    story.append(h3("load_ml_scorer() Factory"))
    story.append(code_block([
        "def load_ml_scorer(model_path: str | None) -> MLScorerProtocol:",
        "    if model_path:",
        "        try:    return SklearnMLScorer(model_path)  # load model",
        "        except: return PassthroughMLScorer()         # graceful fallback",
        "    return PassthroughMLScorer()                     # default",
    ]))

    story.append(h2("7.3 CompositeScorer — Score Aggregation"))
    story.append(body("Location: `snipgen/scoring/composite_scorer.py`"))
    story.append(code_block([
        "final_score = (rule_weight x rule_score + ml_weight x ml_score)",
        "            / (rule_weight + ml_weight)",
        "",
        "# Graceful degradation: if ML scorer is not available:",
        "#   ml_weight is automatically collapsed to 0",
        "#   final_score = rule_score",
    ]))
    story.append(body("**Graceful degradation:** If `ml_scorer.is_available()` returns False, `ml_weight` is silently set to 0.0 and a log message informs the user. `--ml-weight 0.4` with no `--ml-model` will use rule-only scoring without crashing."))
    story.append(PageBreak())

    # ── SECTION 8: OUTPUT ─────────────────────────────────────────────────────
    story.append(h1("8. Output System"))
    story.append(hr())

    story.append(h2("8.1 OutputWriter"))
    story.append(body("Location: `snipgen/io/output_writer.py`"))
    ow_data = [
        ["Parameter", "Default", "Description"],
        ["output_dir", "required", "Directory for output files. Created with parents if it does not exist."],
        ["formats", '["csv","json"]', "Output formats to write. Both are written by default."],
    ]
    story.append(make_table(ow_data, col_widths=[1.2*inch, 1.3*inch, 4.0*inch]))
    story.append(body("The `write()` method produces up to three files: `candidates.csv`, `candidates.json`, and `rejected_candidates.csv` (only if there are rejected candidates). It returns a dict mapping file type names to their `Path` objects."))

    story.append(h2("8.2 CSV Output — candidates.csv"))
    story.append(body("16-column CSV, sorted by `final_score` descending. A second file `rejected_candidates.csv` uses the same schema for audit purposes."))
    csv_data = [
        ["Column", "Type", "Description"],
        ["sequence", "str", "20-nt spacer sequence"],
        ["pam", "str", "PAM sequence (3 nt for SpCas9)"],
        ["chromosome", "str", "Source FASTA record ID"],
        ["start", "int", "0-based genomic start position"],
        ["end", "int", "0-based genomic end (exclusive)"],
        ["strand", "str", "+ or -"],
        ["gc_content", "float", "GC fraction of spacer [0.0-1.0]"],
        ["seed_gc", "float", "GC fraction of seed region (last 12 nt)"],
        ["has_poly_t", "bool", "True if TTTT present"],
        ["has_homopolymer", "bool", "True if 4+ identical bases present"],
        ["gc_pass", "bool", "Passed GC filter"],
        ["pam_pass", "bool", "Passed PAM filter"],
        ["offtarget_pass", "bool", "Passed off-target filter"],
        ["rule_score", "float", "Deterministic rule-based score [0.0-1.0]"],
        ["ml_score", "float", "ML model score [0.0-1.0] (0.5 if no model)"],
        ["final_score", "float", "Weighted combined score [0.0-1.0]"],
    ]
    story.append(make_table(csv_data, col_widths=[1.4*inch, 0.6*inch, 4.5*inch]))

    story.append(h2("8.3 JSON Output — candidates.json"))
    story.append(code_block([
        '{',
        '  "metadata": {',
        '    "snipgen_version": "0.1.0",',
        '    "run_timestamp": "2026-03-29T20:15:00+00:00",',
        '    "cas_variant": "SpCas9",',
        '    "guide_length": 20,',
        '    "min_gc": 0.4,  "max_gc": 0.7,',
        '    "total_candidates_evaluated": 1842,',
        '    "candidates_passed_filters": 412,',
        '    "top_n_returned": 20',
        '  },',
        '  "candidates": [',
        '    {',
        '      "sequence": "GCATCGATCGATCGATCGAT",',
        '      "pam": "AGG",  "chromosome": "seq1",',
        '      "start": 45,  "end": 65,  "strand": "+",',
        '      "gc_content": 0.45,  "seed_gc": 0.4167,',
        '      "has_poly_t": false,  "has_homopolymer": false,',
        '      "rule_score": 0.8542,  "ml_score": 0.5,',
        '      "final_score": 0.8542',
        '    }',
        '  ]',
        '}',
    ]))
    story.append(PageBreak())

    # ── SECTION 9: PIPELINE ───────────────────────────────────────────────────
    story.append(h1("9. Pipeline Orchestrator"))
    story.append(hr())

    story.append(h2("9.1 PipelineConfig — Configuration Dataclass"))
    story.append(body("Location: `snipgen/pipeline.py` — Pure dataclass, intentionally decoupled from the CLI so the pipeline can be instantiated and tested programmatically."))
    config_data = [
        ["Field", "Default", "Description"],
        ["fasta_path", "required", "Path to input FASTA file"],
        ["output_dir", '"results"', "Output directory"],
        ["output_formats", '["csv","json"]', "Output formats to write"],
        ["cas_variant", '"SpCas9"', "CRISPR system variant (from PAM_REGISTRY)"],
        ["guide_length", "20", "Spacer length in nucleotides"],
        ["min_gc", "0.40", "Minimum GC content fraction"],
        ["max_gc", "0.70", "Maximum GC content fraction"],
        ["top_n", "20", "Number of top candidates to return"],
        ["ml_model_path", "None", "Path to joblib-serialized ML model (optional)"],
        ["rule_weight", "1.0", "Weight for rule-based score in composite scoring"],
        ["ml_weight", "0.0", "Weight for ML score (0.0 = rule-only)"],
        ["max_n_fraction", "0.05", "Max N fraction before warning in SequenceCleaner"],
        ["mask_homopolymer_run", "10", "Homopolymer run length to mask with N's"],
        ["seed_length", "12", "Seed region length for OffTargetFilter"],
        ["max_seed_gc", "0.75", "Max seed GC fraction before rejection"],
    ]
    story.append(make_table(config_data, col_widths=[1.7*inch, 1.2*inch, 3.6*inch]))

    story.append(h2("9.2 SnipGenPipeline.run() — Step by Step"))
    story.append(code_block([
        "Step 1:  for record in FastaReader(config.fasta_path):",
        "             # yields BioPython SeqRecord objects, one at a time",
        "",
        "Step 2:      cleaned = SequenceCleaner.clean(record)",
        "             # -> CleanedSequence(record_id, sequence, warnings)",
        "",
        "Step 3:      candidates = WindowExtractor.extract(cleaned)",
        "             # -> list[GRNACandidate] (raw, flags=False, score=0)",
        "",
        "Step 4:  all_candidates.extend(candidates)  # accumulate all records",
        "",
        "Step 5:  passed, rejected = FilterChain.run(all_candidates)",
        "         # passed:   gc_pass AND pam_pass AND offtarget_pass == True",
        "         # rejected: at least one flag False",
        "",
        "Step 6:  scored = CompositeScorer.score_all(passed)",
        "         # sets rule_score, ml_score, final_score on each candidate",
        "",
        "Step 7:  ranked = sorted(scored, key=lambda c: c.final_score, reverse=True)",
        "         top_n  = ranked[:config.top_n]",
        "",
        "Step 8:  stats = { total, passed, rejected, pass_rate, top_n_returned }",
        "",
        "Step 9:  written_files = OutputWriter.write(top_n, rejected, metadata)",
        "",
        "Step 10: return PipelineResult(top_n, rejected, stats, written_files)",
    ]))

    story.append(h2("9.3 PipelineResult"))
    story.append(code_block([
        "@dataclass",
        "class PipelineResult:",
        "    top_candidates: list[GRNACandidate]  # Top-N ranked candidates",
        "    rejected:       list[GRNACandidate]  # All filter-rejected candidates",
        "    stats:          dict                 # Pipeline statistics",
        "    written_files:  dict[str, Path]      # Paths of output files",
    ]))
    story.append(PageBreak())

    # ── SECTION 10: CLI ───────────────────────────────────────────────────────
    story.append(h1("10. CLI Reference"))
    story.append(hr())

    story.append(h2("10.1 Installation"))
    story.append(code_block([
        "pip install biopython",
        "pip install -e '.[dev]'   # from project root (installs snipgen + dev deps)",
        "",
        "# After installation, the snipgen command is available system-wide:",
        "snipgen --help",
    ]))

    story.append(h2("10.2 snipgen design"))
    story.append(body("The primary command. Runs the full gRNA design pipeline on a FASTA file."))
    design_data = [
        ["Option", "Default", "Description"],
        ["--input PATH", "required", "Input FASTA file path (.fasta, .fa, .fna)"],
        ["--output-dir DIR", "results", "Output directory (created if absent)"],
        ["--format [csv|json]...", "csv json", "Output formats; specify multiple"],
        ["--cas-variant TEXT", "SpCas9", "Cas variant: SpCas9, SaCas9, Cpf1, xCas9, Cas9-NG"],
        ["--guide-length INT", "20", "Spacer length in nt (range 17-21)"],
        ["--min-gc FLOAT", "0.40", "Minimum GC fraction [0.0-1.0]"],
        ["--max-gc FLOAT", "0.70", "Maximum GC fraction [0.0-1.0]"],
        ["--top-n INT", "20", "Number of top candidates to return"],
        ["--ml-model PATH", "None", "Path to joblib-serialized sklearn model (optional)"],
        ["--ml-weight FLOAT", "0.0", "ML score weight (0.0 = rule-only scoring)"],
        ["--verbose", "False", "Enable DEBUG logging throughout the pipeline"],
    ]
    story.append(make_table(design_data, col_widths=[1.8*inch, 0.9*inch, 3.8*inch]))

    story.append(h3("Example Usage"))
    story.append(code_block([
        "# Basic usage",
        "snipgen design --input target.fasta --output-dir results/",
        "",
        "# With Cpf1 and custom GC range",
        "snipgen design --input target.fasta --cas-variant Cpf1 --min-gc 0.35 --max-gc 0.65",
        "",
        "# With ML model",
        "snipgen design --input target.fasta --ml-model model.joblib --ml-weight 0.4",
        "",
        "# CSV only, top 50 candidates",
        "snipgen design --input target.fasta --format csv --top-n 50",
    ]))

    story.append(h2("10.3 snipgen validate"))
    story.append(body("Parse and validate a FASTA file without running the pipeline or writing output files. Useful for checking input quality before a long run."))
    story.append(code_block([
        "snipgen validate --input target.fasta",
        "",
        "# Output:",
        "Records: 3",
        "Total nucleotides: 1,248",
        "No warnings.",
    ]))

    story.append(h2("10.4 snipgen list-variants"))
    story.append(body("Print all supported Cas variants with their PAM patterns and positions."))
    story.append(code_block([
        "snipgen list-variants",
        "",
        "Variant      PAM Pattern  Position",
        "------------------------------------",
        "SpCas9       NGG          3prime",
        "SaCas9       NNGRRT       3prime",
        "Cpf1         TTTV         5prime",
        "xCas9        NG           3prime",
        "Cas9-NG      NG           3prime",
    ]))
    story.append(PageBreak())

    # ── SECTION 11: WEB APP ───────────────────────────────────────────────────
    story.append(h1("11. Web Application"))
    story.append(hr())

    story.append(h2("11.1 FastAPI Backend"))
    story.append(body("Location: `webapp/app.py` — The web application wraps the same `SnipGenPipeline` used by the CLI. FastAPI was chosen for automatic OpenAPI docs, Pydantic type validation, and async file upload support."))

    story.append(h3("Endpoint Reference"))
    ep_data = [
        ["Method", "Path", "Description"],
        ["GET", "/", "Serves index.html — the single-page web application"],
        ["GET", "/variants", "Returns all Cas variants as JSON for the frontend dropdown"],
        ["POST", "/design", "Accepts FASTA upload + query params, runs pipeline, returns JSON"],
    ]
    story.append(make_table(ep_data, col_widths=[0.7*inch, 1.0*inch, 4.8*inch]))

    story.append(h3("POST /design Parameters"))
    api_data = [
        ["Parameter", "Type", "Default", "Range"],
        ["file", "UploadFile", "required", "Any .fasta file"],
        ["cas_variant", "str", "SpCas9", "Must be in PAM_REGISTRY"],
        ["guide_length", "int", "20", "17 – 25"],
        ["min_gc", "float", "0.40", "0.0 – 1.0"],
        ["max_gc", "float", "0.70", "0.0 – 1.0"],
        ["top_n", "int", "20", "1 – 200"],
    ]
    story.append(make_table(api_data, col_widths=[1.2*inch, 0.8*inch, 0.8*inch, 3.7*inch]))

    story.append(h3("File Handling and Privacy"))
    story.append(body("Uploaded FASTA files are written to a `tempfile.NamedTemporaryFile` for processing. The temp file is always deleted after the request completes (even on error, via `try/finally`). **No user data is persisted on the server.**"))

    story.append(h2("11.2 Frontend UI"))
    story.append(body("Location: `webapp/static/index.html` — A single-page application built with vanilla JavaScript and CSS (no framework). Uses a GitHub-inspired dark theme with CSS custom properties for consistent theming."))
    story.append(h3("Left Panel — Design Parameters"))
    story.append(bullet("**FASTA upload zone:** Drag-and-drop or click-to-browse. Visual feedback on hover and after file selection."))
    story.append(bullet("**Cas variant dropdown:** Populated dynamically from `/variants` API on page load"))
    story.append(bullet("**Guide length selector:** 17–21 nt dropdown"))
    story.append(bullet("**GC range inputs:** Min/Max numeric inputs with step 5"))
    story.append(bullet("**Top-N slider:** Range 1–100 with live label update"))
    story.append(bullet("**Run button:** Disabled until a file is selected; shows spinner during API call"))

    story.append(h3("Right Panel — Results"))
    story.append(bullet("**Stats strip (4 columns):** Candidates evaluated, Passed (with %), Rejected, Top score"))
    story.append(bullet("**Tab 1 — Top candidates table:** Rank, Spacer sequence (monospace, coloured), PAM, Strand, GC%, Score with visual bar. Tooltips show genomic coordinates."))
    story.append(bullet("**Tab 2 — Run metadata:** All pipeline configuration and statistics from the JSON response"))
    story.append(bullet("**Download buttons:** CSV and JSON client-side download via Blob API — no server round-trip required"))

    story.append(h2("11.3 Deployment on Render"))
    story.append(body("SnipGen is configured for zero-configuration deployment on Render.com (free tier). Every push to GitHub triggers an automatic redeploy."))
    story.append(code_block([
        "# render.yaml — Blueprint configuration",
        "services:",
        "  - type: web",
        "    name: snipgen",
        "    runtime: python",
        "    plan: free",
        "    buildCommand: pip install -r requirements.txt && pip install -e .",
        "    startCommand: uvicorn webapp.app:app --host 0.0.0.0 --port $PORT",
        "    envVars:",
        "      - key: PYTHON_VERSION",
        "        value: 3.11.0",
        "",
        "# Procfile — fallback start command",
        "web: uvicorn webapp.app:app --host 0.0.0.0 --port $PORT",
    ]))
    story.append(h3("Deployment Workflow"))
    story.append(bullet("**Push to GitHub:** `git push origin main`"))
    story.append(bullet("**Render detects push** via webhook and triggers auto-deploy"))
    story.append(bullet("**Build phase:** Installs all packages from `requirements.txt`, then installs snipgen package in editable mode (`pip install -e .`)"))
    story.append(bullet("**Start phase:** uvicorn binds to `0.0.0.0:$PORT` (Render injects the `PORT` environment variable)"))
    story.append(bullet("**Live URL:** `https://snipgen.onrender.com`"))
    story.append(PageBreak())

    # ── SECTION 12: TESTS ─────────────────────────────────────────────────────
    story.append(h1("12. Test Suite"))
    story.append(hr())

    story.append(h2("12.1 Test Strategy"))
    story.append(body("The test suite uses pytest with pytest-cov and covers all pipeline stages. **47 tests, 89% code coverage.**"))
    strategy_data = [
        ["Category", "Files", "Description"],
        ["Unit tests", "test_gc_filter, test_pam_filter, test_offtarget_filter, test_rule_scorer, test_ml_scorer, test_fasta_reader", "Each component tested in isolation with synthetic inputs"],
        ["Integration tests", "test_pipeline", "Full end-to-end pipeline run on sample_target.fasta fixture"],
        ["CLI tests", "test_cli", "Click CliRunner invokes commands and checks exit codes and output"],
    ]
    story.append(make_table(strategy_data, col_widths=[1.1*inch, 2.5*inch, 2.9*inch]))

    story.append(h2("12.2 Test File Summary"))
    test_data = [
        ["Test File", "Tests", "What is covered"],
        ["test_fasta_reader.py", "4", "Record counting, missing file error, short-sequence skipping, ID preservation"],
        ["test_gc_filter.py", "7", "Boundary values (39/40/55/70/71%), custom thresholds, name format"],
        ["test_pam_filter.py", "10", "SpCas9 PAM matching (4 valid, 3 invalid), unknown variant error, all 5 registry variants"],
        ["test_offtarget_filter.py", "5", "Clean pass, poly-T rejection, homopolymer rejection, high seed GC, seed GC computation"],
        ["test_rule_scorer.py", "5", "Score range, high-quality candidate score, poly-T penalty, homopolymer penalty, weights sum"],
        ["test_ml_scorer.py", "6", "Passthrough value, availability flag, Protocol compliance, empty input, factory function"],
        ["test_pipeline.py", "5", "End-to-end run, CSV/JSON output files, top-N limit, descending score ordering"],
        ["test_cli.py", "5", "design command, validate command, list-variants, missing input error, csv-only format"],
    ]
    story.append(make_table(test_data, col_widths=[1.8*inch, 0.55*inch, 4.15*inch]))

    story.append(h2("12.3 Running Tests"))
    story.append(code_block([
        "# Run all tests with coverage report",
        "pytest tests/ -v --cov=snipgen --cov-report=term-missing",
        "",
        "# Run a specific test file",
        "pytest tests/test_pipeline.py -v",
        "",
        "# Run a single test by name",
        "pytest tests/test_gc_filter.py::test_gc_filter_boundaries -v",
    ]))

    story.append(h2("12.4 Coverage Summary"))
    cov_data = [
        ["Module", "Stmts", "Miss", "Cover"],
        ["snipgen/__init__.py", "1", "0", "100%"],
        ["snipgen/cli.py", "75", "6", "92%"],
        ["snipgen/filters/base_filter.py", "8", "0", "100%"],
        ["snipgen/filters/filter_chain.py", "17", "1", "94%"],
        ["snipgen/filters/gc_filter.py", "12", "0", "100%"],
        ["snipgen/filters/offtarget_filter.py", "23", "1", "96%"],
        ["snipgen/filters/pam_filter.py", "22", "0", "100%"],
        ["snipgen/io/fasta_reader.py", "36", "5", "86%"],
        ["snipgen/io/output_writer.py", "35", "0", "100%"],
        ["snipgen/models/grna_candidate.py", "16", "0", "100%"],
        ["snipgen/pipeline.py", "69", "0", "100%"],
        ["snipgen/preprocessing/sequence_cleaner.py", "40", "8", "80%"],
        ["snipgen/preprocessing/window_extractor.py", "44", "9", "80%"],
        ["snipgen/scoring/composite_scorer.py", "23", "2", "91%"],
        ["snipgen/scoring/ml_scorer.py", "47", "18", "62%"],
        ["snipgen/scoring/rule_scorer.py", "15", "0", "100%"],
        ["snipgen/utils/nucleotide.py", "21", "1", "95%"],
        ["TOTAL", "516", "58", "89%"],
    ]
    ct = Table(cov_data, colWidths=[3.5*inch, 0.8*inch, 0.7*inch, 1.5*inch], repeatRows=1)
    ct.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), C_SURFACE),
        ('TEXTCOLOR',  (0,0), (-1,0), C_BLUE),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('FONTNAME',   (0,1), (-1,-2), 'Helvetica'),
        ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), C_SURFACE),
        ('TEXTCOLOR',  (0,1), (-1,-2), C_TEXT),
        ('TEXTCOLOR',  (0,-1), (-1,-1), C_GOOD),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [C_CODE_BG, C_DARK_GRAY]),
        ('GRID',       (0,0), (-1,-1), 0.5, C_BORDER),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
    ]))
    story.append(ct)
    story.append(PageBreak())

    # ── APPENDIX A ────────────────────────────────────────────────────────────
    story.append(h1("Appendix A: Quick Reference"))
    story.append(hr())

    story.append(h2("Filter Decision Matrix"))
    fdm = [
        ["Condition", "Filter", "Flag Set"],
        ["GC < 40% or GC > 70%", "GCFilter", "gc_pass = False"],
        ["PAM not in variant's valid set", "PAMFilter", "pam_pass = False"],
        ["Seed GC > 75%", "OffTargetFilter", "offtarget_pass = False"],
        ["TTTT in spacer", "OffTargetFilter", "offtarget_pass = False"],
        ["4+ identical consecutive bases", "OffTargetFilter", "offtarget_pass = False"],
    ]
    story.append(make_table(fdm, col_widths=[2.5*inch, 1.5*inch, 2.5*inch]))

    story.append(h2("Scoring Formula Summary"))
    story.append(code_block([
        "# Component scores",
        "gc_score    = max(0.0, 1.0 - abs(gc_content - 0.5) / 0.3)",
        "seed_score  = max(0.0, 1.0 - seed_gc)",
        "g1_score    = 1.0 if sequence[0] == 'G' else 0.0",
        "homo_score  = 0.0 if has_homopolymer else 1.0",
        "polyt_score = 0.0 if has_poly_t else 1.0",
        "",
        "# Rule score (weights sum to 1.0)",
        "rule_score = 0.25*gc_score + 0.20*seed_score + 0.15*g1_score",
        "           + 0.20*homo_score + 0.20*polyt_score",
        "",
        "# ML score (default 0.5 when no model loaded)",
        "ml_score = model.predict_proba(features)[:,1]  # or 0.5",
        "",
        "# Final composite score",
        "final_score = (rule_weight*rule_score + ml_weight*ml_score)",
        "            / (rule_weight + ml_weight)",
    ]))

    story.append(h2("Key Files Quick Reference"))
    kf_data = [
        ["File", "Purpose"],
        ["snipgen/models/grna_candidate.py", "Central data contract — all candidate fields"],
        ["snipgen/pipeline.py", "Pipeline orchestrator + PipelineConfig dataclass"],
        ["snipgen/filters/pam_filter.py", "PAM registry for all 5 Cas variants"],
        ["snipgen/scoring/ml_scorer.py", "MLScorerProtocol + passthrough + sklearn hook"],
        ["snipgen/cli.py", "CLI entrypoint (design / validate / list-variants)"],
        ["webapp/app.py", "FastAPI web application (3 endpoints)"],
        ["webapp/static/index.html", "Single-page web UI"],
        ["render.yaml", "Render.com deployment configuration"],
        ["Procfile", "Web process start command"],
        ["requirements.txt", "Runtime dependencies for deployment"],
        ["pyproject.toml", "Package metadata + dev dependencies"],
        ["tests/", "47-test suite, 89% coverage"],
    ]
    story.append(make_table(kf_data, col_widths=[3.0*inch, 3.5*inch]))

    story.append(sp(20))
    story.append(HRFlowable(width="100%", thickness=2, color=C_ACCENT, spaceAfter=12))
    story.append(Paragraph("End of Document", META_STYLE))
    story.append(Paragraph("SnipGen v0.1.0  ·  github.com/ldharwal-asu/snipgen", META_STYLE))

    doc.build(story)
    print(f"PDF written to: {OUTPUT}")

if __name__ == "__main__":
    build()
