"""Genome summary — overview of variant counts and key findings."""

from genechat.tools.common import resolve_engine
from genechat.vcf_engine import VCFEngineError


def register(mcp, engines, db, config):
    @mcp.tool()
    def genome_summary(
        genome: str | None = None,
        genome2: str | None = None,
    ) -> str:
        """Get a high-level summary of your genome data.

        Returns variant counts, ClinVar annotation summary, and pharmacogenomics overview.
        Use this as a starting point when a user wants a general overview of their genome.

        Optional: 'genome' selects which registered genome to query (default: primary genome).
        'genome2' produces a side-by-side summary of a second genome.
        """
        try:
            label, engine = resolve_engine(engines, genome, config)
        except ValueError as e:
            return str(e)

        genome_cfg = config.genomes.get(label, config.genome)
        show_label = len(engines) > 1

        lines = _format_summary(
            engine, db, config, genome_cfg, label if show_label else None
        )

        # Paired genome
        if genome2:
            try:
                label2, engine2 = resolve_engine(engines, genome2, config)
            except ValueError as e:
                lines.append(f"\n---\n\n**Genome '{genome2}': {e}**")
                return "\n".join(lines)

            genome_cfg2 = config.genomes.get(label2, config.genome)
            lines.append("\n---\n")
            lines.extend(_format_summary(engine2, db, config, genome_cfg2, label2))

        lines.append(
            "\n---\n*Use specific tools (query_variant, query_gene, query_pgx, "
            "query_clinvar, query_gwas, calculate_prs) for detailed analysis.*"
        )

        return "\n".join(lines)


def _format_summary(engine, db, config, genome_cfg, label):
    """Build genome summary markdown lines for a single engine."""
    header = "## Genome Summary"
    if label:
        header += f": {label}"
    lines = [header]
    lines.append(f"**Build:** {genome_cfg.genome_build}")
    lines.append(f"**VCF:** {genome_cfg.vcf_path}")

    # Annotation versions from VCF headers
    try:
        versions = engine.annotation_versions()
        if versions:
            lines.append("\n### Annotation Versions")
            for ver_label, value in sorted(versions.items()):
                lines.append(f"- **{ver_label}:** {value}")
    except VCFEngineError:
        pass

    # Variant stats
    try:
        stats_info = engine.stats()
        lines.append("\n### Variant Counts")
        for key, val in stats_info.items():
            lines.append(
                f"- **{key}:** {val:,}"
                if isinstance(val, int)
                else f"- **{key}:** {val}"
            )
    except VCFEngineError as e:
        lines.append(f"\n*Could not retrieve stats: {e}*")

    # ClinVar summary — count pathogenic variants
    try:
        pathogenic = engine.query_clinvar("athogenic")
        lines.append("\n### ClinVar Pathogenic/Likely Pathogenic")
        lines.append(
            f"Found **{len(pathogenic)}** pathogenic or likely pathogenic variant(s)"
        )
        if pathogenic:
            genes = set()
            for v in pathogenic[:50]:
                g = v.get("annotation", {}).get("gene")
                if g:
                    genes.add(g)
            if genes:
                lines.append(f"Affected genes: {', '.join(sorted(genes))}")
    except VCFEngineError:
        lines.append("\n*ClinVar query not available*")

    # PGx summary — count non-ref PGx variants
    try:
        pgx_genes = [
            "CYP2D6",
            "CYP2C19",
            "CYP2C9",
            "SLCO1B1",
            "DPYD",
            "VKORC1",
            "TPMT",
        ]
        pgx_findings = []
        for gene in pgx_genes:
            variants = db.get_pgx_variants(gene)
            non_ref = 0
            for pv in variants:
                try:
                    region = f"{pv['chrom']}:{pv['pos']}-{pv['pos'] + 1}"
                    user_vars = engine.query_region(region)
                    if (
                        user_vars
                        and user_vars[0]["genotype"]["zygosity"] != "homozygous_ref"
                    ):
                        non_ref += 1
                except (ValueError, VCFEngineError):
                    pass
            if non_ref > 0:
                pgx_findings.append(f"{gene}: {non_ref} non-reference variant(s)")

        lines.append("\n### Pharmacogenomics Quick Check")
        if pgx_findings:
            for f in pgx_findings:
                lines.append(f"- {f}")
            lines.append("\nUse `query_pgx` for detailed drug-gene information.")
        else:
            lines.append("No non-reference PGx variants detected in key genes.")
    except Exception:
        lines.append("\n*PGx quick check not available*")

    return lines
