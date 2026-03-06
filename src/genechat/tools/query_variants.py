"""Batch lookup of multiple variants by rsID."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_variants(
        rsids: str,
    ) -> str:
        """Look up multiple genetic variants by rsID in a single query.

        Accepts a comma-separated list of rsIDs (e.g. "rs4149056,rs1801133,rs762551").
        Much more efficient than calling query_variant repeatedly — scans the VCF once
        for all requested variants.
        Use this when a user asks about multiple specific SNPs at once, or when you
        need to check several variants for a comprehensive answer.
        """
        raw_ids = [r.strip() for r in rsids.split(",") if r.strip()]
        if not raw_ids:
            return "Please provide comma-separated rsIDs (e.g. rs4149056,rs1801133)."

        if len(raw_ids) > 50:
            return "Too many rsIDs (max 50). Please split into smaller batches."

        try:
            results = engine.query_rsids(raw_ids)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying variants: {e}"

        found = {rsid for rsid, variants in results.items() if variants}
        missing = [r for r in raw_ids if r not in found]

        lines = [f"## Batch Variant Lookup ({len(found)}/{len(raw_ids)} found)"]

        for rsid in raw_ids:
            variants = results.get(rsid, [])
            if not variants:
                continue
            for v in variants:
                lines.append(f"\n### {rsid}")
                lines.append(
                    f"**Position:** {v['chrom']}:{v['pos']} | "
                    f"**Genotype:** {v['genotype']['display']} "
                    f"({v['genotype']['zygosity'].replace('_', ' ')})"
                )
                ann = v.get("annotation", {})
                if ann:
                    parts = []
                    if ann.get("gene"):
                        parts.append(ann["gene"])
                    if ann.get("effect"):
                        parts.append(ann["effect"])
                    if ann.get("impact"):
                        parts.append(ann["impact"])
                    if parts:
                        lines.append(f"**Annotation:** {' | '.join(parts)}")
                clin = v.get("clinvar", {})
                if clin:
                    clin_parts = [clin["significance"]]
                    if clin.get("condition"):
                        clin_parts.append(clin["condition"])
                    lines.append(f"**ClinVar:** {' — '.join(clin_parts)}")
                freq = v.get("population_freq", {})
                if freq and config.display.include_population_freq:
                    freq_parts = []
                    if "global" in freq:
                        freq_parts.append(f"Global: {freq['global'] * 100:.1f}%")
                    if "popmax" in freq:
                        freq_parts.append(f"Popmax: {freq['popmax'] * 100:.1f}%")
                    if freq_parts:
                        lines.append(f"**Frequency:** {' | '.join(freq_parts)}")

        if missing:
            lines.append(f"\n### Not Found ({len(missing)})")
            lines.append(
                "These variants were not found in your genome (homozygous reference "
                "or not covered by sequencing):"
            )
            lines.append(", ".join(missing))

        return "\n".join(lines) + DISCLAIMER
