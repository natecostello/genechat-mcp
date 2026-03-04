"""Look up a specific variant by rsID or genomic position."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_variant(
        rsid: str | None = None,
        position: str | None = None,
    ) -> str:
        """Look up a specific genetic variant by rsID (e.g. rs4149056) or genomic position (e.g. chr22:42127941).

        Use this when a user asks about a specific SNP, rsID, or genomic coordinate.
        Returns genotype, functional annotation, ClinVar significance, and population frequency.
        """
        if not rsid and not position:
            return "Please provide either an rsID (e.g. rs4149056) or a position (e.g. chr22:42127941)."

        try:
            if rsid:
                variants = engine.query_rsid(rsid)
            else:
                # Parse position into a tiny region
                if ":" not in position:
                    return f"Invalid position format: {position}. Expected chr<N>:<pos> (e.g. chr22:42127941)"
                chrom, pos_str = position.split(":", 1)
                try:
                    pos = int(pos_str)
                except ValueError:
                    return f"Invalid position: {pos_str}. Must be a number."
                region = f"{chrom}:{pos}-{pos + 1}"
                variants = engine.query_region(region)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying variant: {e}"

        if not variants:
            query_desc = rsid if rsid else position
            return (
                f"No variant found for {query_desc} in your genome.\n"
                "This position may be homozygous reference (matching the reference genome) "
                "or not covered by your sequencing."
            )

        lines = []
        for v in variants:
            lines.append(_format_variant(v, config))

        return "\n\n---\n\n".join(lines) + DISCLAIMER


def _format_variant(v: dict, config) -> str:
    """Format a variant dict as markdown."""
    rsid_display = v["rsid"] or "."
    gt = v["genotype"]
    ann = v["annotation"]
    clin = v["clinvar"]
    freq = v["population_freq"]

    lines = [f"## Variant: {rsid_display}"]
    lines.append(
        f"**Position:** {v['chrom']}:{v['pos']} ({config.genome.genome_build})"
    )
    lines.append(
        f"**Your genotype:** {gt['display']} ({gt['zygosity'].replace('_', ' ')})"
    )
    lines.append(f"**Alleles:** REF={v['ref']} ALT={v['alt']}")

    if ann:
        lines.append("\n### Functional Annotation")
        if ann.get("gene"):
            lines.append(f"**Gene:** {ann['gene']}")
        if ann.get("effect"):
            impact = f" ({ann['impact']} impact)" if ann.get("impact") else ""
            lines.append(f"**Effect:** {ann['effect']}{impact}")
        if ann.get("hgvs_p") or ann.get("hgvs_c"):
            parts = []
            if ann.get("hgvs_p"):
                parts.append(ann["hgvs_p"])
            if ann.get("hgvs_c"):
                parts.append(ann["hgvs_c"])
            lines.append(f"**Change:** {' / '.join(parts)}")

    if clin:
        lines.append("\n### Clinical Significance")
        lines.append(f"**ClinVar:** {clin['significance']}")
        if clin.get("condition"):
            lines.append(f"**Condition:** {clin['condition']}")
        if clin.get("review_status"):
            lines.append(f"**Review:** {clin['review_status']}")

    if freq and config.display.include_population_freq:
        lines.append("\n### Population Frequency")
        parts = []
        if "global" in freq:
            parts.append(f"Global: {freq['global'] * 100:.1f}%")
        if "popmax" in freq:
            parts.append(f"Popmax: {freq['popmax'] * 100:.1f}%")
        if parts:
            lines.append(" | ".join(parts))

    return "\n".join(lines)
