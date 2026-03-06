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
        If functional annotation is not available, all variants are included regardless
        of impact filter.
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

        # Filter by impact — pass through variants with no annotation data
        if impact_filter:
            variants = [
                v
                for v in variants
                if not v.get("annotation", {}).get("impact")
                or v["annotation"]["impact"].upper() in impacts
            ]

        # Quality filter: for unannotated variants, only keep those with
        # rsID or ClinVar to reduce noise from novel/unknown variants
        filtered = []
        for v in variants:
            has_ann = bool(v.get("annotation", {}).get("impact"))
            has_clinvar = bool(v.get("clinvar", {}))
            has_rsid = bool(v.get("rsid"))
            if has_ann or has_clinvar or has_rsid:
                filtered.append(v)
        variants = filtered

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

        # Trait overlay: show known trait associations for this gene
        trait_variants = db.get_trait_variants(gene=gene.upper())
        if trait_variants:
            lines.append("")
            lines.append(f"### Known Trait Associations for {gene.upper()}")
            lines.append("| rsID | Trait | Effect Allele | Description | Evidence |")
            lines.append("|------|-------|---------------|-------------|----------|")
            for tv in trait_variants:
                tv_rsid = tv.get("rsid", ".")
                trait = tv.get("trait", ".")
                ea = tv.get("effect_allele", ".")
                desc = tv.get("effect_description", ".")
                evid = tv.get("evidence_level", ".")
                lines.append(f"| {tv_rsid} | {trait} | {ea} | {desc} | {evid} |")

        return "\n".join(lines) + DISCLAIMER
