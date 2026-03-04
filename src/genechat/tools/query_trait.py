"""Query trait-associated variants (nutrigenomics, exercise, metabolism, etc.)."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_trait(
        category: str | None = None,
        trait: str | None = None,
        gene: str | None = None,
    ) -> str:
        """Look up trait-associated genetic variants in your genome.

        Categories: nutrigenomics, exercise, metabolism, caffeine, alcohol,
        cardiovascular, inflammation, sleep, other.
        Use when a user asks about diet, exercise, caffeine metabolism, etc.
        """
        if not category and not trait and not gene:
            return (
                "Please provide at least one filter: category, trait, or gene.\n"
                "Available categories: nutrigenomics, exercise, metabolism, "
                "cardiovascular, other."
            )

        trait_entries = db.get_trait_variants(category=category, trait=trait, gene=gene)
        if not trait_entries:
            filters = []
            if category:
                filters.append(f"category='{category}'")
            if trait:
                filters.append(f"trait='{trait}'")
            if gene:
                filters.append(f"gene='{gene}'")
            return f"No trait variants found for {', '.join(filters)}."

        # Query VCF for each trait variant and group by trait
        by_trait: dict[str, list] = {}
        for entry in trait_entries:
            rsid = entry["rsid"]
            trait_name = entry["trait"]

            # Query user genotype
            gt_info = None
            try:
                region = f"{entry['chrom']}:{entry['pos']}-{entry['pos'] + 1}"
                user_variants = engine.query_region(region)
                if user_variants:
                    gt_info = user_variants[0]["genotype"]
                else:
                    gt_info = {
                        "display": f"{entry['ref']}/{entry['ref']}",
                        "zygosity": "homozygous_ref",
                    }
            except (ValueError, VCFEngineError):
                gt_info = {"display": "query error", "zygosity": "unknown"}

            by_trait.setdefault(trait_name, []).append(
                {
                    **entry,
                    "user_genotype": gt_info,
                }
            )

        cat_display = category.title() if category else "Selected"
        lines = [f"## {cat_display} Trait Variants"]

        for trait_name, entries in by_trait.items():
            lines.append(f"\n### {trait_name}")
            for e in entries:
                gt = e["user_genotype"]
                rsid = e["rsid"]
                gene_name = e.get("gene", "")
                effect_allele = e["effect_allele"]
                evidence = e.get("evidence_level", "unknown")
                pmid = e.get("pmid", "")

                lines.append(f"**{rsid}** ({gene_name})")
                lines.append(
                    f"- Your genotype: **{gt['display']}** ({gt['zygosity'].replace('_', ' ')})"
                )
                lines.append(f"- Effect allele: {effect_allele}")
                lines.append(f"- {e['effect_description']}")
                lines.append(f"- Evidence: {evidence}")
                if pmid and pmid != ".":
                    lines.append(f"- Reference: PMID {pmid}")
                lines.append("")

        return "\n".join(lines) + DISCLAIMER
