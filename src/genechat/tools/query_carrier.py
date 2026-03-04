"""Carrier screening — check for pathogenic variants in carrier panel genes."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_carrier(
        condition: str | None = None,
        acmg_only: bool = True,
        max_results: int = 50,
    ) -> str:
        """Screen your genome for carrier status of recessive genetic conditions.

        Checks for ClinVar pathogenic/likely pathogenic variants in carrier panel genes.
        Use when a user asks about carrier status, reproductive genetics, or inherited conditions.
        Set acmg_only=false to include expanded panel beyond ACMG recommendations.
        """
        carrier_genes = db.get_carrier_genes(
            condition=condition, acmg_only=acmg_only
        )
        if not carrier_genes:
            scope = "ACMG-recommended" if acmg_only else "expanded"
            return f"No carrier genes found in {scope} panel" + (
                f" matching '{condition}'" if condition else ""
            ) + "."

        positive = []
        negative = []

        for cg in carrier_genes[:max_results]:
            gene = cg["gene"]
            region = db.get_gene_region(gene)
            if not region:
                negative.append({**cg, "note": "gene coordinates not available"})
                continue

            try:
                variants = engine.query_clinvar("athogenic", region=region)
                # Filter to Pathogenic or Likely_pathogenic
                path_variants = [
                    v for v in variants
                    if v.get("clinvar", {}).get("significance", "")
                    and "athogenic" in v["clinvar"]["significance"]
                ]
                if path_variants:
                    positive.append({**cg, "variants": path_variants})
                else:
                    negative.append({**cg, "note": "no pathogenic variants found"})
            except (ValueError, VCFEngineError):
                negative.append({**cg, "note": "query error"})

        scope = "ACMG-Recommended" if acmg_only else "Expanded"
        lines = [f"## Carrier Screening Results ({scope} Panel)"]
        lines.append(
            f"Genes screened: {len(carrier_genes)} | "
            f"Positive: {len(positive)} | Clear: {len(negative)}"
        )

        if positive:
            lines.append("\n### Carrier Positive")
            for p in positive:
                lines.append(
                    f"\n**{p['gene']}** — {p['condition_name']} "
                    f"({p['inheritance']}, carrier freq: {p.get('carrier_frequency', 'unknown')})"
                )
                for v in p["variants"]:
                    rsid = v["rsid"] or "."
                    gt = v["genotype"]["display"]
                    sig = v.get("clinvar", {}).get("significance", "")
                    cond = v.get("clinvar", {}).get("condition", "")
                    lines.append(f"- {rsid}: {gt} — {sig}" + (f" ({cond})" if cond else ""))

        if negative:
            lines.append("\n### No Pathogenic Variants Found")
            lines.append("| Gene | Condition | Inheritance |")
            lines.append("|------|-----------|-------------|")
            for n in negative:
                lines.append(f"| {n['gene']} | {n['condition_name']} | {n['inheritance']} |")

        lines.append(
            "\n**Important:** Absence of known pathogenic variants does not guarantee "
            "non-carrier status. This screen covers only variants catalogued in ClinVar "
            "and may miss rare or novel mutations. Consider professional genetic counseling "
            "for comprehensive carrier testing."
        )

        return "\n".join(lines) + DISCLAIMER
