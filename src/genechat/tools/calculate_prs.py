"""Calculate polygenic risk scores (PRS) from genome data."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def calculate_prs(
        trait: str | None = None,
        prs_id: str | None = None,
    ) -> str:
        """Calculate a polygenic risk score (PRS) for a trait.

        PRS aggregates the effects of many common genetic variants to estimate
        genetic predisposition to a trait. Currently available: coronary artery disease.
        Provide either a trait name or a PGS Catalog ID.
        """
        if not trait and not prs_id:
            return "Please provide either a trait name or a PRS/PGS ID."

        weights = db.get_prs_weights(trait=trait, prs_id=prs_id)
        if not weights:
            query = trait or prs_id
            return (
                f"No PRS data found for '{query}'.\n"
                "Currently available: 'coronary artery disease' (PGS000013)."
            )

        prs_name = weights[0]["trait"]
        prs_id_display = weights[0]["prs_id"]
        total_variants = len(weights)

        score = 0.0
        found = 0
        details = []

        for w in weights:
            rsid = w["rsid"]
            effect_allele = w["effect_allele"]
            weight = w["weight"]

            # Query user genotype
            try:
                region = f"{w['chrom']}:{w['pos']}-{w['pos'] + 1}"
                user_variants = engine.query_region(region)
            except (ValueError, VCFEngineError):
                details.append((rsid, "query error", 0, weight))
                continue

            if user_variants:
                gt = user_variants[0]["genotype"]
                alleles = gt["display"].split("/")
                dosage = sum(1 for a in alleles if a == effect_allele)
                contribution = dosage * weight
                score += contribution
                found += 1
                details.append((rsid, gt["display"], dosage, weight))
            else:
                # Assume reference (0 dosage) for missing variants
                details.append((rsid, "ref/ref", 0, weight))

        lines = [
            f"## Polygenic Risk Score: {prs_name}",
            f"**PGS ID:** {prs_id_display}",
            f"**Raw score:** {score:.4f}",
            f"**Variants scored:** {found}/{total_variants}",
            "",
        ]

        # Show top contributing variants
        details_sorted = sorted(details, key=lambda x: abs(x[2] * x[3]), reverse=True)
        lines.append("### Top Contributing Variants")
        lines.append(
            "| rsID | Your Genotype | Effect Allele Dosage | Weight | Contribution |"
        )
        lines.append(
            "|------|--------------|---------------------|--------|-------------|"
        )
        for rsid, gt_display, dosage, weight in details_sorted[:15]:
            contrib = dosage * weight
            if contrib != 0:
                lines.append(
                    f"| {rsid} | {gt_display} | {dosage} | {weight:.3f} | {contrib:+.4f} |"
                )

        lines.append("\n### Important Caveats")
        lines.append(
            "- PRS captures only common variant risk and does not account for "
            "rare high-impact mutations"
        )
        lines.append(
            "- Performance varies significantly by genetic ancestry — most PRS were "
            "developed in European populations"
        )
        lines.append(
            "- PRS is one factor among many (lifestyle, family history, environment) "
            "that influence disease risk"
        )
        lines.append(
            "- Raw scores are not directly interpretable as absolute risk — "
            "percentile ranking requires a reference population"
        )
        if found < total_variants:
            lines.append(
                f"- Only {found} of {total_variants} variants were found in your VCF; "
                "missing variants reduce score accuracy"
            )

        return "\n".join(lines) + DISCLAIMER
