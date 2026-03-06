"""Batch query of variants across multiple genes."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_genes(
        genes: str,
        impact_filter: str = "HIGH,MODERATE",
        max_results_per_gene: int = 20,
    ) -> str:
        """Query variants across multiple genes in a single call.

        Accepts a comma-separated list of gene symbols (e.g. "BRCA1,BRCA2,TP53").
        Much more efficient than calling query_gene repeatedly — opens the VCF once.
        Use this when investigating a pathway, gene panel, or related group of genes.
        For example: "Check APOB,LDLR,PCSK9 for cardiovascular risk" or
        "Look at CYP2D6,CYP2C19,CYP2C9 for drug metabolism".
        """
        gene_list = [g.strip().upper() for g in genes.split(",") if g.strip()]
        if not gene_list:
            return "Please provide comma-separated gene symbols (e.g. BRCA1,BRCA2)."

        if len(gene_list) > 20:
            return "Too many genes (max 20). Please split into smaller batches."

        impacts = {i.strip().upper() for i in impact_filter.split(",")}

        # Resolve gene coordinates
        gene_regions: list[tuple[str, dict, str]] = []
        not_found = []
        for symbol in gene_list:
            gene_info = db.get_gene(symbol)
            if not gene_info:
                not_found.append(symbol)
                continue
            region = db.get_gene_region(symbol)
            if region:
                gene_regions.append((symbol, gene_info, region))
            else:
                not_found.append(symbol)

        if not gene_regions:
            return f"None of the genes found: {', '.join(not_found)}"

        # Query all regions at once
        regions = [r for _, _, r in gene_regions]
        try:
            all_variants = engine.query_regions(regions)
        except (ValueError, VCFEngineError) as e:
            return f"Error querying genes: {e}"

        # Assign variants to genes by region overlap
        gene_variants: dict[str, list[dict]] = {s: [] for s, _, _ in gene_regions}
        for symbol, gene_info, region in gene_regions:
            chrom = gene_info["chrom"]
            start = gene_info["start"]
            end = gene_info["end"]
            for v in all_variants:
                if v["chrom"] == chrom and start <= v["pos"] <= end:
                    gene_variants[symbol].append(v)

        lines = [f"## Multi-Gene Query ({len(gene_regions)} genes)"]

        if not_found:
            lines.append(f"*Not found: {', '.join(not_found)}*\n")

        total_notable = 0
        for symbol, gene_info, _ in gene_regions:
            variants = gene_variants[symbol]

            # Filter by impact
            if impact_filter:
                variants = [
                    v
                    for v in variants
                    if not v.get("annotation", {}).get("impact")
                    or v["annotation"]["impact"].upper() in impacts
                ]

            # Further filter: for unannotated variants, only keep those with
            # rsID or ClinVar to reduce noise
            filtered = []
            for v in variants:
                has_ann = bool(v.get("annotation", {}).get("impact"))
                has_clinvar = bool(v.get("clinvar", {}))
                has_rsid = bool(v.get("rsid"))
                if has_ann or has_clinvar or has_rsid:
                    filtered.append(v)
            variants = filtered[:max_results_per_gene]

            lines.append(f"\n### {symbol} ({gene_info['name']})")
            if not variants:
                lines.append("No notable variants found.")
                continue

            total_notable += len(variants)
            lines.append("| rsID | Genotype | Effect | Impact | ClinVar |")
            lines.append("|------|----------|--------|--------|---------|")
            for v in variants:
                rsid = v["rsid"] or "."
                gt = v["genotype"]["display"]
                ann = v.get("annotation", {})
                effect = ann.get("effect", ".") or "."
                impact = ann.get("impact", ".") or "."
                clin = v.get("clinvar", {})
                sig = clin.get("significance", ".") if clin else "."
                lines.append(f"| {rsid} | {gt} | {effect} | {impact} | {sig} |")

        lines.insert(1, f"Total notable variants: {total_notable}")

        return "\n".join(lines) + DISCLAIMER
