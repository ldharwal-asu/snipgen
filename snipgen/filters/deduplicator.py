"""Position-aware + sequence-level guide RNA deduplication."""

from snipgen.models.grna_candidate import GRNACandidate


def deduplicate_guides(
    candidates: list[GRNACandidate], window: int = 10
) -> tuple[list[GRNACandidate], list[GRNACandidate]]:
    """Two-pass deduplication.

    Pass 1 — Position clustering:
        Cluster guides that share chromosome+strand and whose start positions
        are within `window` bp of each other. Keep the highest-scoring
        representative per cluster.

    Pass 2 — Sequence-level deduplication:
        After position dedup, identical guide sequences that survived (e.g.
        the same conserved exon appearing in multiple FASTA isoforms) are
        collapsed to a single representative. The first occurrence (highest
        position-cluster score) is kept.

    Returns:
        (kept, removed) — removed guides get rejection code 'DUPLICATE'
        or 'SEQ_DUPLICATE' appended to rejection_codes.
    """
    if not candidates:
        return [], []

    # ── Pass 1: position clustering ──────────────────────────────────────────
    sorted_guides = sorted(
        candidates, key=lambda g: (g.chromosome, g.strand, g.start)
    )

    clusters: list[list[GRNACandidate]] = []
    current: list[GRNACandidate] = [sorted_guides[0]]

    for guide in sorted_guides[1:]:
        prev = current[-1]
        if (
            guide.chromosome == prev.chromosome
            and guide.strand == prev.strand
            and guide.start - prev.start <= window
        ):
            current.append(guide)
        else:
            clusters.append(current)
            current = [guide]
    clusters.append(current)

    pos_kept: list[GRNACandidate] = []
    removed: list[GRNACandidate] = []

    for cluster in clusters:
        best = max(cluster, key=lambda g: g.rule_score if g.rule_score > 0 else g.gc_content)
        pos_kept.append(best)
        for g in cluster:
            if g is not best:
                g.rejection_codes.append("DUPLICATE")
                removed.append(g)

    # ── Pass 2: sequence-level deduplication ─────────────────────────────────
    # Handles identical guides from conserved exons across multi-isoform FASTAs.
    # The pass-1 representative with the best score is retained; all others
    # with the same 20-mer sequence are marked SEQ_DUPLICATE.
    seen_sequences: dict[str, GRNACandidate] = {}
    kept: list[GRNACandidate] = []

    for guide in pos_kept:
        seq_key = guide.sequence.upper()
        if seq_key not in seen_sequences:
            seen_sequences[seq_key] = guide
            kept.append(guide)
        else:
            guide.rejection_codes.append("SEQ_DUPLICATE")
            removed.append(guide)

    return kept, removed
