"""Parse SnpEff ANN field from annotated VCFs."""


def parse_ann_field(ann_raw: str) -> dict:
    """Parse first (most severe) SnpEff ANN entry.

    Returns dict with keys: gene, effect, impact, transcript, hgvs_c, hgvs_p.
    Returns empty dict if ann_raw is '.' or empty.
    """
    if not ann_raw or ann_raw == ".":
        return {}
    first = ann_raw.split(",")[0]
    parts = first.split("|")
    if len(parts) < 11:
        return {"raw": ann_raw}
    return {
        "gene": parts[3],
        "effect": parts[1],
        "impact": parts[2],
        "transcript": parts[6],
        "hgvs_c": parts[9],
        "hgvs_p": parts[10],
    }
