"""Calculate polygenic risk scores (PRS) from genome data."""

from genechat.tools.common import resolve_engine
from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engines, db, config):
    @mcp.tool()
    def calculate_prs(
        trait: str | None = None,
        prs_id: str | None = None,
        genome: str | None = None,
        genome2: str | None = None,
    ) -> str:
        """Calculate a polygenic risk score (PRS) for a trait.

        PRS aggregates the effects of many common genetic variants to estimate
        genetic predisposition to a trait. Provide either a trait name or a PGS Catalog ID.

        Optional: 'genome' selects which registered genome to query (default: primary genome).
        'genome2' calculates the score for a second genome for comparison.
        """
        if not trait and not prs_id:
            return "Please provide either a trait name or a PRS/PGS ID."

        try:
            label, engine = resolve_engine(engines, genome, config)
        except ValueError as e:
            return str(e)

        weights = db.get_prs_weights(trait=trait, prs_id=prs_id)
        if not weights:
            query = trait or prs_id
            available = db.list_prs_traits()
            if available:
                avail_str = ", ".join(
                    f"'{t['trait']}' ({t['prs_id']})" for t in available
                )
            else:
                avail_str = "none loaded"
            return (
                f"No PRS data found for '{query}'.\nCurrently available: {avail_str}."
            )

        prs_name = weights[0]["trait"]
        prs_id_display = weights[0]["prs_id"]
        total_variants = len(weights)

        show_label = len(engines) > 1
        lines = _score_and_format(
            engine,
            weights,
            prs_name,
            prs_id_display,
            total_variants,
            label=label if show_label else None,
        )

        # Paired genome query
        if genome2:
            try:
                label2, engine2 = resolve_engine(engines, genome2, config)
            except ValueError as e:
                lines.append(f"\n---\n\n**Genome '{genome2}': {e}**")
                return "\n".join(lines) + DISCLAIMER

            lines.append("\n---\n")
            lines.extend(
                _score_and_format(
                    engine2,
                    weights,
                    prs_name,
                    prs_id_display,
                    total_variants,
                    label=label2,
                )
            )

        lines.extend(_prs_caveats())

        return "\n".join(lines) + DISCLAIMER


def _score_and_format(
    engine, weights, prs_name, prs_id_display, total_variants, *, label=None
):
    """Score variants and return formatted markdown lines."""
    score = 0.0
    found = 0
    details = []

    for w in weights:
        rsid = w["rsid"]
        effect_allele = w["effect_allele"]
        weight = w["weight"]

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
            details.append((rsid, "ref/ref", 0, weight))

    header = f"## Polygenic Risk Score: {prs_name}"
    if label:
        header += f" — {label}"
    lines = [
        header,
        f"**PGS ID:** {prs_id_display}",
        f"**Raw score:** {score:.4f}",
        f"**Variants scored:** {found}/{total_variants}",
        "",
    ]

    details_sorted = sorted(details, key=lambda x: abs(x[2] * x[3]), reverse=True)
    lines.append("### Top Contributing Variants")
    lines.append(
        "| rsID | Your Genotype | Effect Allele Dosage | Weight | Contribution |"
    )
    lines.append("|------|--------------|---------------------|--------|-------------|")
    for rsid, gt_display, dosage, weight in details_sorted[:15]:
        contrib = dosage * weight
        if contrib != 0:
            lines.append(
                f"| {rsid} | {gt_display} | {dosage} | {weight:.3f} | {contrib:+.4f} |"
            )

    if found < total_variants:
        lines.append(
            f"\n*Only {found} of {total_variants} variants were found; "
            "missing variants reduce score accuracy.*"
        )

    return lines


def _prs_caveats():
    """Return standard PRS caveats as markdown lines."""
    return [
        "\n### Important Caveats",
        "- PRS captures only common variant risk and does not account for "
        "rare high-impact mutations",
        "- Performance varies significantly by genetic ancestry — most PRS were "
        "developed in European populations",
        "- PRS is one factor among many (lifestyle, family history, environment) "
        "that influence disease risk",
        "- Raw scores are not directly interpretable as absolute risk — "
        "percentile ranking requires a reference population",
    ]
