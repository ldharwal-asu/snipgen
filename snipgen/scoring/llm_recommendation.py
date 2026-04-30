"""
LLM-powered guide RNA recommendation text generator.

Uses the Anthropic Claude API (claude-haiku-3 by default for speed/cost)
to generate concise, scientifically accurate natural language summaries
of each guide RNA candidate's safety profile.

Falls back to template-based text if:
  - ANTHROPIC_API_KEY is not set
  - The API call fails or times out
  - The anthropic package is not installed

Environment
───────────
  ANTHROPIC_API_KEY  — set this in Vercel dashboard or local .env
  SNIPGEN_LLM_MODEL  — override model (default: claude-haiku-4-5)
  SNIPGEN_LLM_OFF    — set to "1" to force template fallback (useful in tests)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from snipgen.models.grna_candidate import GRNACandidate

logger = logging.getLogger("snipgen.scoring.llm")

_DEFAULT_MODEL = "claude-haiku-4-5"

# ── Template fallback ─────────────────────────────────────────────────────────

_TEMPLATES: dict[str, str] = {
    "HIGH": (
        "This guide RNA demonstrates strong on-target efficiency with low predicted off-target "
        "burden. GC content and thermodynamic properties are within optimal ranges. "
        "Recommended for experimental validation as a primary candidate."
    ),
    "MEDIUM": (
        "This guide RNA shows acceptable on-target scores with moderate confidence. "
        "Some sub-optimal features detected — review the score breakdown before proceeding. "
        "Suitable for initial screening; validate experimentally before therapeutic use."
    ),
    "LOW": (
        "This guide RNA has suboptimal predicted efficiency or elevated off-target risk. "
        "Use only if higher-ranked alternatives are unavailable. Additional computational "
        "analysis or experimental validation strongly recommended before use."
    ),
    "AVOID": (
        "This guide RNA has poor predicted efficiency and/or significant off-target burden. "
        "Not recommended. Select a higher-ranked alternative from the candidate list."
    ),
}


def template_recommendation(candidate: GRNACandidate) -> str:
    return _TEMPLATES.get(candidate.safety_label, _TEMPLATES["MEDIUM"])


# ── LLM recommendation ────────────────────────────────────────────────────────

def _build_prompt(c: GRNACandidate) -> str:
    bd = c.score_breakdown or {}
    return f"""You are a CRISPR bioinformatics assistant. Write a concise (2-3 sentence) \
scientific recommendation for this guide RNA candidate. Be specific about the scores. \
Do not use bullet points. Write in plain prose for a molecular biology researcher audience.

Guide RNA: {c.sequence}
PAM: {c.pam}
Safety classification: {c.safety_label}
Composite score: {c.final_score}/100
On-target score: {c.on_target_score}/100  (GC={bd.get('gc_pct', '?')}%, \
rule sub-scores: GC={bd.get('on_gc', '?')}, position={bd.get('on_position', '?')}, \
thermodynamic={bd.get('on_thermodynamic', '?')})
Off-target score: {c.off_target_score}/100  \
(1mm={c.off_targets_1mm}, 2mm={c.off_targets_2mm}, 3mm={c.off_targets_3mm})
Consequence score: {c.consequence_score}/100
Confidence score: {c.confidence_score}/100
Scorer: {bd.get('scorer', 'rule_based')}

Recommendation:"""


def generate_recommendation(
    candidate: GRNACandidate,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """
    Generate a natural language recommendation for a single guide RNA.

    Tries the Claude API first; falls back to templates on any failure.
    """
    # Check kill-switch
    if os.environ.get("SNIPGEN_LLM_OFF", "0") == "1":
        return template_recommendation(candidate)

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        logger.debug("ANTHROPIC_API_KEY not set — using template recommendation.")
        return template_recommendation(candidate)

    try:
        import anthropic  # type: ignore
    except ImportError:
        logger.warning("anthropic package not installed — using template recommendation.")
        return template_recommendation(candidate)

    chosen_model = model or os.environ.get("SNIPGEN_LLM_MODEL", _DEFAULT_MODEL)

    try:
        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            model=chosen_model,
            max_tokens=180,
            messages=[{"role": "user", "content": _build_prompt(candidate)}],
        )
        text = message.content[0].text.strip()
        logger.debug("LLM recommendation generated for %s (model=%s)", candidate.sequence, chosen_model)
        return text
    except Exception as exc:
        logger.warning("LLM recommendation failed (%s) — using template.", exc)
        return template_recommendation(candidate)


def generate_recommendations_batch(
    candidates: list[GRNACandidate],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_llm_calls: int = 5,
) -> None:
    """
    Generate recommendations for a list of candidates in-place.

    To control cost and latency, only the top `max_llm_calls` guides
    (by current final_score) get LLM recommendations. The rest get templates.

    This caps API cost at ~$0.002 per analysis (5 × claude-haiku-4-5 at 200 tokens).
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    llm_available = bool(key) and os.environ.get("SNIPGEN_LLM_OFF", "0") != "1"

    # Sort by score to identify top candidates
    ranked = sorted(enumerate(candidates), key=lambda x: x[1].final_score, reverse=True)

    for rank_idx, (orig_idx, candidate) in enumerate(ranked):
        if llm_available and rank_idx < max_llm_calls:
            candidates[orig_idx].recommendation = generate_recommendation(
                candidate, api_key=key, model=model
            )
        else:
            candidates[orig_idx].recommendation = template_recommendation(candidate)
