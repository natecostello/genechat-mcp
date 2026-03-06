"""Compile a structured summary of genomic findings from a session."""

from genechat.vcf_engine import VCFEngineError


def register(mcp, engine, db, config):
    @mcp.tool()
    def compile_findings(
        variants: str = "",
        genes: str = "",
        include_pgx: bool = True,
        include_traits: bool = True,
        include_clinvar: bool = True,
    ) -> str:
        """Compile a structured report of genomic findings for discussion with a provider.

        Call this at the end of an exploration session to create an organized summary.
        Provide comma-separated rsIDs and/or gene symbols that were discussed.
        The report pulls together variant details, PGx implications, trait associations,
        and ClinVar findings into a single reference document.

        Example: compile_findings(variants="rs4149056,rs1801133", genes="CYP2D6,BRCA1")
        """
        rsid_list = [r.strip() for r in variants.split(",") if r.strip()]
        gene_list = [g.strip().upper() for g in genes.split(",") if g.strip()]

        if not rsid_list and not gene_list:
            return (
                "Please provide at least one variant (rsID) or gene to compile.\n"
                "Example: compile_findings(variants='rs4149056', genes='CYP2D6')"
            )

        lines = ["# Genomic Findings Summary", ""]

        # --- Variant Details ---
        if rsid_list:
            lines.append("## Variant Details")
            try:
                results = engine.query_rsids(rsid_list)
            except (ValueError, VCFEngineError) as e:
                lines.append(f"\n*Error querying variants: {e}*")
                results = {}

            results.pop("_truncated", None)

            for rsid in rsid_list:
                variant_list = results.get(rsid, [])
                if not variant_list:
                    lines.append(f"\n### {rsid}")
                    lines.append(
                        "Not found in your genome (homozygous reference or not covered)."
                    )
                    continue

                for v in variant_list:
                    lines.append(f"\n### {rsid}")
                    gt = v["genotype"]
                    lines.append(f"- **Position:** {v['chrom']}:{v['pos']}")
                    lines.append(
                        f"- **Genotype:** {gt['display']} ({gt['zygosity'].replace('_', ' ')})"
                    )
                    ann = v.get("annotation", {})
                    if ann.get("gene"):
                        lines.append(f"- **Gene:** {ann['gene']}")
                    if ann.get("effect"):
                        impact = f" ({ann['impact']})" if ann.get("impact") else ""
                        lines.append(f"- **Effect:** {ann['effect']}{impact}")
                    if ann.get("hgvs_p"):
                        lines.append(f"- **Protein:** {ann['hgvs_p']}")
                    if include_clinvar:
                        clin = v.get("clinvar", {})
                        if clin:
                            sig = clin.get("significance", "")
                            cond = clin.get("condition", "")
                            if sig:
                                clin_str = sig
                                if cond:
                                    clin_str += f" — {cond}"
                                lines.append(f"- **ClinVar:** {clin_str}")
                    freq = v.get("population_freq", {})
                    if freq:
                        freq_parts = []
                        if "global" in freq:
                            freq_parts.append(f"Global: {freq['global'] * 100:.1f}%")
                        if "popmax" in freq:
                            freq_parts.append(f"Popmax: {freq['popmax'] * 100:.1f}%")
                        if freq_parts:
                            lines.append(f"- **Frequency:** {' | '.join(freq_parts)}")

                    # Cross-reference: trait associations for this rsID
                    if include_traits and ann.get("gene"):
                        traits = db.get_trait_variants(gene=ann["gene"])
                        rsid_traits = [t for t in traits if t.get("rsid") == rsid]
                        if rsid_traits:
                            for t in rsid_traits:
                                lines.append(
                                    f"- **Trait:** {t['trait']} — {t['effect_description']} "
                                    f"(evidence: {t.get('evidence_level', 'unknown')})"
                                )

        # --- Gene Summaries ---
        if gene_list:
            lines.append("\n## Gene Summaries")

            # Load carrier info once for all genes
            carrier_lookup = {}
            for cg in db.get_carrier_genes():
                carrier_lookup[cg["gene"].upper()] = cg

            for symbol in gene_list:
                gene_info = db.get_gene(symbol)
                if not gene_info:
                    lines.append(f"\n### {symbol}")
                    lines.append("Gene not found in database.")
                    continue

                lines.append(f"\n### {symbol} ({gene_info['name']})")
                lines.append(
                    f"- **Location:** {gene_info['chrom']}:{gene_info['start']}-{gene_info['end']}"
                )

                # PGx associations
                if include_pgx:
                    pgx_drugs = db.search_pgx_by_gene(symbol)
                    if pgx_drugs:
                        drug_names = [d["drug_name"] for d in pgx_drugs]
                        lines.append(f"- **PGx drugs:** {', '.join(drug_names)}")

                # Carrier screening
                cg = carrier_lookup.get(symbol)
                if cg:
                    lines.append(
                        f"- **Carrier screening:** {cg['condition_name']} "
                        f"({cg['inheritance']})"
                    )

                # Trait associations
                if include_traits:
                    traits = db.get_trait_variants(gene=symbol)
                    if traits:
                        lines.append("- **Trait associations:**")
                        for t in traits[:5]:
                            lines.append(
                                f"  - {t['rsid']}: {t['trait']} — "
                                f"{t['effect_description']}"
                            )
                        if len(traits) > 5:
                            lines.append(f"  - ... and {len(traits) - 5} more")

        # --- Disclaimer ---
        lines.append("\n---")
        lines.append(
            "*This summary is informational only and not a medical diagnosis. "
            "Discuss findings with a qualified healthcare provider before making "
            "health decisions. Genetic variants are one factor among many that "
            "influence health outcomes.*"
        )

        return "\n".join(lines)
