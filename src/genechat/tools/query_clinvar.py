"""Query variants by ClinVar clinical significance."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_clinvar(
        significance: str,
        gene: str | None = None,
        condition: str | None = None,
        max_results: int = 50,
    ) -> str:
        """Search your genome for variants with a specific ClinVar clinical significance.

        Use this when a user asks about pathogenic variants, disease risk, or clinical findings.
        Significance values: Pathogenic, Likely_pathogenic, Benign, Likely_benign,
        Uncertain_significance, risk_factor, drug_response, protective.
        """
        region = None
        gene_info = None
        if gene:
            gene_info = db.get_gene(gene)
            if not gene_info:
                return f"Gene '{gene}' not found in the database."
            region = db.get_gene_region(gene)

        try:
            variants = engine.query_clinvar(significance, region=region)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying ClinVar: {e}"

        # Post-filter by condition if specified
        if condition:
            condition_upper = condition.upper()
            variants = [
                v for v in variants
                if v.get("clinvar", {}).get("condition", "")
                and condition_upper in v["clinvar"]["condition"].upper()
            ]

        # Cap results
        cap = min(max_results, 100)
        truncated = len(variants) > cap
        variants = variants[:cap]

        if not variants:
            scope = f" in {gene}" if gene else " genome-wide"
            cond_note = f" for condition '{condition}'" if condition else ""
            return (
                f"No **{significance.replace('_', ' ')}** variants found{scope}{cond_note}.\n\n"
                "This is generally reassuring, but absence of known pathogenic variants "
                "does not guarantee absence of risk — not all variants are catalogued in ClinVar."
            )

        # Group by gene
        by_gene: dict[str, list] = {}
        for v in variants:
            g = v.get("annotation", {}).get("gene", "Unknown") or "Unknown"
            by_gene.setdefault(g, []).append(v)

        title_scope = f" in {gene}" if gene else ""
        lines = [
            f"## ClinVar {significance.replace('_', ' ')} variants{title_scope}",
            f"Found: {len(variants)} variant(s) across {len(by_gene)} gene(s)",
            "",
        ]

        if truncated:
            lines.append(f"*Results capped at {cap}. Narrow your query for complete results.*\n")

        for gene_name, gene_variants in sorted(by_gene.items()):
            lines.append(f"### {gene_name}")
            lines.append("| rsID | Position | Genotype | Significance | Condition |")
            lines.append("|------|----------|----------|-------------|-----------|")
            for v in gene_variants:
                rsid = v["rsid"] or "."
                pos = f"{v['chrom']}:{v['pos']}"
                gt = v["genotype"]["display"]
                clin = v.get("clinvar", {})
                sig = clin.get("significance", ".") if clin else "."
                cond = clin.get("condition", ".") if clin else "."
                lines.append(f"| {rsid} | {pos} | {gt} | {sig} | {cond} |")
            lines.append("")

        return "\n".join(lines) + DISCLAIMER
