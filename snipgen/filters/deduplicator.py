"""Position-aware guide RNA deduplication."""

from snipgen.models.grna_candidate import GRNACandidate


def deduplicate_guides(
    candidates: list[GRNACandidate], window: int = 10
) -> tuple[list[GRNACandidate], list[GRNACandidate]]:
    """Cluster guides by position overlap and keep the best per cluster.

    Two guides are in the same cluster when they share chromosome, strand,
    and their start positions are within `window` bp of each other.

    Returns:
        (kept, removed) — removed guides get rejection code 'DUPLICATE'.
    """
    if not candidates:
        return [], []

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

    kept: list[GRNACandidate] = []
    removed: list[GRNACandidate] = []

    for cluster in clusters:
        # Pre-scoring: use rule_score if available, else gc_content as proxy
        best = max(cluster, key=lambda g: g.rule_score if g.rule_score > 0 else g.gc_content)
        kept.append(best)
        for g in cluster:
            if g is not best:
                g.rejection_codes.append("DUPLICATE")
                removed.append(g)

    return kept, removed
