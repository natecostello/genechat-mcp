"""Batch lookup of multiple variants by rsID."""

from genechat.tools.common import resolve_engine
from genechat.tools.formatting import enhanced_warning_for_genes
from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engines, db, config):
    @mcp.tool()
    def query_variants(
        rsids: str,
        genome: str | None = None,
        genome2: str | None = None,
    ) -> str:
        """Look up multiple genetic variants by rsID in a single query.

        Accepts a comma-separated list of rsIDs (e.g. "rs4149056,rs1801133,rs762551").
        Much more efficient than calling query_variant repeatedly — scans the VCF once
        for all requested variants.
        Use this when a user asks about multiple specific SNPs at once, or when you
        need to check several variants for a comprehensive answer.

        Optional: 'genome' selects which registered genome to query (default: primary genome).
        'genome2' queries a second genome for side-by-side comparison.
        """
        raw_ids = [r.strip() for r in rsids.split(",") if r.strip()]
        if not raw_ids:
            return "Please provide comma-separated rsIDs (e.g. rs4149056,rs1801133)."

        if len(raw_ids) > 50:
            return "Too many rsIDs (max 50). Please split into smaller batches."

        try:
            label, engine = resolve_engine(engines, genome, config)
        except ValueError as e:
            return str(e)

        try:
            results = engine.query_rsids(raw_ids)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying variants: {e}"

        # Collect genes from results for warning check
        all_genes = set()
        for rsid_key, variants in results.items():
            if rsid_key == "_truncated":
                continue
            for v in variants:
                g = v.get("annotation", {}).get("gene")
                if g:
                    all_genes.add(g)

        show_label = len(engines) > 1

        output = _format_batch_results(
            results, raw_ids, config, label if show_label else None
        )

        # Paired genome
        if genome2:
            try:
                label2, engine2 = resolve_engine(engines, genome2, config)
            except ValueError as e:
                output.append(f"\n---\n\n**Genome '{genome2}': {e}**")
                warning = enhanced_warning_for_genes(db, all_genes)
                return warning + "\n".join(output) + DISCLAIMER

            try:
                results2 = engine2.query_rsids(raw_ids)
            except (ValueError, VCFEngineError) as e:
                output.append(f"\n---\n\n**Genome '{label2}' error: {e}**")
                warning = enhanced_warning_for_genes(db, all_genes)
                return warning + "\n".join(output) + DISCLAIMER

            for rsid_key, variants in results2.items():
                if rsid_key == "_truncated":
                    continue
                for v in variants:
                    g = v.get("annotation", {}).get("gene")
                    if g:
                        all_genes.add(g)

            output.append("\n---\n")
            output.extend(_format_batch_results(results2, raw_ids, config, label2))

        warning = enhanced_warning_for_genes(db, all_genes)
        return warning + "\n".join(output) + DISCLAIMER


def _format_batch_results(
    results: dict, raw_ids: list[str], config, label: str | None
) -> list[str]:
    """Format batch variant results into markdown lines."""
    truncated = "_truncated" in results
    results.pop("_truncated", None)

    found = {rsid for rsid, variants in results.items() if variants}
    missing = [r for r in raw_ids if r not in found]

    header = f"## Batch Variant Lookup ({len(found)}/{len(raw_ids)} found)"
    if label:
        header += f" — {label}"
    lines = [header]

    if truncated:
        lines.append(
            "*Warning: VCF scan was truncated due to variant cap. "
            "Some variants may not have been reached — 'not found' results below "
            "may be incomplete.*\n"
        )

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

    return lines
