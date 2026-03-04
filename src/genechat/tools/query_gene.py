"""Query all variants in a gene region."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_gene(
        gene: str,
        impact_filter: str = "HIGH,MODERATE",
        max_results: int = 50,
    ) -> str:
        """Query variants in a specific gene from your genome.

        Use this when a user asks about variants in a gene (e.g. "What variants do I have in BRCA1?").
        Filters by SnpEff impact level (HIGH, MODERATE, LOW, MODIFIER) by default.
        """
        gene_info = db.get_gene(gene)
        if not gene_info:
            return f"Gene '{gene}' not found in the database. Check the gene symbol and try again."

        region = db.get_gene_region(gene)
        if not region:
            return f"Could not determine coordinates for gene '{gene}'."

        impacts = [i.strip().upper() for i in impact_filter.split(",")]
        valid_impacts = {"HIGH", "MODERATE", "LOW", "MODIFIER"}
        invalid = set(impacts) - valid_impacts
        if invalid:
            return f"Invalid impact levels: {invalid}. Valid: {valid_impacts}"

        try:
            variants = engine.query_region(region)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying gene {gene}: {e}"

        # Filter by impact
        if impact_filter:
            variants = [
                v
                for v in variants
                if v.get("annotation", {}).get("impact", "").upper() in impacts
            ]

        # Cap results
        truncated = len(variants) > max_results
        variants = variants[:max_results]

        if not variants:
            return (
                f"No {'/'.join(impacts)} impact variants found in **{gene}** "
                f"({gene_info['name']}).\n\n"
                f"Region searched: {region}\n"
                "This means your sequence matches the reference genome in this region "
                "for the impact levels queried. Try broadening the impact filter "
                "(e.g. impact_filter='HIGH,MODERATE,LOW,MODIFIER') to see all variants."
            )

        lines = [
            f"## Variants in {gene} ({gene_info['name']})",
            f"Region: {region} | Filter: {impact_filter} | Found: {len(variants)}",
            "",
        ]

        if truncated:
            lines.append(
                f"*Showing first {max_results} variants. Narrow your query for complete results.*\n"
            )

        lines.append("| rsID | Position | Genotype | Effect | Impact | ClinVar |")
        lines.append("|------|----------|----------|--------|--------|---------|")

        for v in variants:
            rsid = v["rsid"] or "."
            pos = f"{v['chrom']}:{v['pos']}"
            gt = v["genotype"]["display"]
            ann = v.get("annotation", {})
            effect = ann.get("effect", ".") or "."
            impact = ann.get("impact", ".") or "."
            clin = v.get("clinvar", {})
            sig = clin.get("significance", ".") if clin else "."
            lines.append(f"| {rsid} | {pos} | {gt} | {effect} | {impact} | {sig} |")

        return "\n".join(lines) + DISCLAIMER
