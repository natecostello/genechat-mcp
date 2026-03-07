"""Genome summary — overview of variant counts and key findings."""

import pysam

from genechat.vcf_engine import VCFEngineError


def _read_annotation_versions(vcf_path: str) -> dict[str, str]:
    """Read ##GeneChat_* header lines from a VCF file."""
    versions = {}
    try:
        with pysam.VariantFile(vcf_path) as vcf:
            for rec in vcf.header.records:
                if rec.type == "GENERIC":
                    key = rec.key
                    if key.startswith("GeneChat_"):
                        label = key.replace("GeneChat_", "")
                        versions[label] = rec.value
    except Exception:
        pass
    return versions


def register(mcp, engine, db, config):
    _cache: dict[str, str] = {}

    @mcp.tool()
    def genome_summary() -> str:
        """Get a high-level summary of your genome data.

        Returns variant counts, ClinVar annotation summary, and pharmacogenomics overview.
        Use this as a starting point when a user wants a general overview of their genome.
        """
        if "result" in _cache:
            return _cache["result"]

        lines = ["## Genome Summary"]
        lines.append(f"**Build:** {config.genome.genome_build}")
        lines.append(f"**VCF:** {config.genome.vcf_path}")

        # Annotation versions from VCF headers
        versions = _read_annotation_versions(config.genome.vcf_path)
        if versions:
            lines.append("\n### Annotation Versions")
            for label, value in sorted(versions.items()):
                lines.append(f"- **{label}:** {value}")

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

        lines.append(
            "\n---\n*Use specific tools (query_variant, query_gene, query_pgx, "
            "query_clinvar, query_gwas, calculate_prs) for detailed analysis.*"
        )

        result = "\n".join(lines)
        _cache["result"] = result
        return result
