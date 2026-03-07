"""Pharmacogenomics query — look up drug-gene interactions and your genotypes."""

from genechat.tools.formatting import short_zygosity
from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_pgx(
        drug: str | None = None,
        gene: str | None = None,
        include_all_variants: bool = False,
    ) -> str:
        """Look up pharmacogenomic information for a drug or gene.

        Use this when a user asks about drug interactions, medication safety, or
        how their genetics affect drug metabolism. Provide either a drug name
        (e.g. "simvastatin") or a gene symbol (e.g. "CYP2D6").
        """
        if not drug and not gene:
            return "Please provide either a drug name or a gene symbol."

        # Find drug-gene entries
        if drug:
            entries = db.search_pgx_by_drug(drug)
            if not entries:
                return (
                    f"No pharmacogenomic data found for '{drug}'.\n"
                    "This drug may not have CPIC guidelines, or check the spelling."
                )
        else:
            entries = db.search_pgx_by_gene(gene)
            if not entries:
                return (
                    f"No pharmacogenomic drug entries found for gene '{gene}'.\n"
                    "This gene may not have CPIC guidelines."
                )

        sections = []
        for entry in entries:
            section = _format_pgx_entry(entry, engine, db, config, include_all_variants)
            sections.append(section)

        return "\n\n---\n\n".join(sections) + DISCLAIMER


def _format_pgx_entry(entry, engine, db, config, include_all_variants):
    """Format a single PGx drug-gene entry with user genotypes."""
    gene = entry["gene"]
    drug_name = entry["drug_name"]

    lines = [f"## Pharmacogenomics: {drug_name.title()}"]
    lines.append(f"**Related gene:** {gene}")
    if entry.get("guideline_source"):
        lines.append(f"**Guideline:** {entry['guideline_source']}")

    # Get known PGx variants for this gene
    pgx_variants = db.get_pgx_variants(gene)

    if pgx_variants:
        lines.append(f"\n### Your {gene} Variants")
        lines.append("| Variant | Star Allele | Your Genotype | Function Impact |")
        lines.append("|---------|------------|---------------|-----------------|")

        # Batch VCF lookup for all PGx variant positions
        pv_regions = []
        pv_region_idx = []
        for pi, pv in enumerate(pgx_variants):
            if pv.get("chrom") and pv.get("pos"):
                pv_regions.append(f"{pv['chrom']}:{pv['pos']}-{pv['pos'] + 1}")
                pv_region_idx.append(pi)

        pv_vcf_map: dict[int, list[dict]] = {}
        batch_query_ok = False
        if pv_regions:
            try:
                all_pv = engine.query_regions(pv_regions)
                pos_map: dict[str, list[dict]] = {}
                for v in all_pv:
                    key = f"{v['chrom']}:{v['pos']}"
                    pos_map.setdefault(key, []).append(v)
                for ri, pi in enumerate(pv_region_idx):
                    pv = pgx_variants[pi]
                    key = f"{pv['chrom']}:{pv['pos']}"
                    if key in pos_map:
                        pv_vcf_map[pi] = pos_map[key]
                batch_query_ok = not (all_pv and all_pv[-1].get("_truncated"))
            except (ValueError, VCFEngineError):
                pass

        for pi, pv in enumerate(pgx_variants):
            rsid = pv["rsid"] or "."
            star = pv.get("star_allele") or "."
            impact = pv.get("function_impact") or "."

            gt_display = "not found"
            if pv.get("chrom") and pv.get("pos"):
                pv_results = pv_vcf_map.get(pi)
                if pv_results:
                    gt = pv_results[0]["genotype"]
                    zyg_short = short_zygosity(gt["zygosity"])
                    gt_display = f"{gt['display']} ({zyg_short})"
                elif batch_query_ok:
                    gt_display = "ref or not covered"
                elif pv_regions:
                    gt_display = "query error"

            lines.append(f"| {rsid} | {star} | {gt_display} | {impact} |")

    # Include all variants in gene region if requested
    if include_all_variants:
        gene_region = db.get_gene_region(gene)
        if gene_region:
            try:
                all_vars = engine.query_region(gene_region)
                non_ref = [
                    v for v in all_vars if v["genotype"]["zygosity"] != "homozygous_ref"
                ]
                if non_ref:
                    lines.append(f"\n### All non-reference variants in {gene}")
                    lines.append("| rsID | Position | Genotype | Effect |")
                    lines.append("|------|----------|----------|--------|")
                    for v in non_ref[:20]:
                        rsid = v["rsid"] or "."
                        pos = f"{v['chrom']}:{v['pos']}"
                        gt = v["genotype"]["display"]
                        effect = v.get("annotation", {}).get("effect", ".") or "."
                        lines.append(f"| {rsid} | {pos} | {gt} | {effect} |")
            except (ValueError, VCFEngineError):
                pass

    if entry.get("clinical_summary"):
        lines.append(f"\n### Clinical Summary\n{entry['clinical_summary']}")

    if entry.get("guideline_url") and entry["guideline_url"] != ".":
        lines.append(f"\n[CPIC Guideline]({entry['guideline_url']})")

    return "\n".join(lines)
