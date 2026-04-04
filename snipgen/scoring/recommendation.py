"""Natural language recommendation generator for guide cards."""

from snipgen.models.grna_candidate import GRNACandidate


def generate_recommendation(c: GRNACandidate) -> str:
    """Return a human-readable recommendation string for this guide."""
    on = c.on_target_score
    label = c.safety_label

    total_ot = c.off_targets_1mm + c.off_targets_2mm + c.off_targets_3mm
    if total_ot == 0:
        off_note = "no within-sequence off-targets detected"
    elif c.off_targets_1mm > 0:
        off_note = f"{c.off_targets_1mm} near-perfect off-target(s) — review carefully"
    else:
        off_note = f"{total_ot} low-similarity off-target site(s) in input sequence"

    gc_pct = round(c.gc_content * 100)
    if on >= 80:
        on_note = f"excellent on-target profile (GC {gc_pct}%, strong position scores)"
    elif on >= 60:
        on_note = f"good on-target profile (GC {gc_pct}%)"
    else:
        on_note = f"moderate on-target efficiency (GC {gc_pct}%)"

    if label == "HIGH":
        return (
            f"Strong candidate. {on_note.capitalize()}. "
            f"Off-target burden: {off_note}. High confidence recommendation."
        )
    elif label == "MEDIUM":
        return (
            f"Acceptable guide. {on_note.capitalize()}. "
            f"Off-target burden: {off_note}. "
            "Validate experimentally before clinical use."
        )
    elif label == "LOW":
        return (
            f"Use with caution. {on_note.capitalize()}. "
            f"Off-target burden: {off_note}. "
            "Conflicting signals — manual review strongly advised."
        )
    else:
        return (
            f"NOT RECOMMENDED. {on_note.capitalize()}. "
            f"Off-target burden: {off_note}. "
            "High off-target risk detected. Seek alternative guides."
        )
