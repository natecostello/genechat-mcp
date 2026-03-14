"""Query all variants in a gene region."""

from genechat.tools.common import resolve_engine
from genechat.tools.formatting import enhanced_warning_for_genes
from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)

# ClinVar significance values that should never be suppressed by smart_filter
_PROTECTED_CLINVAR = {
    "pathogenic",
    "likely_pathogenic",
    "likely pathogenic",
    "risk_factor",
    "risk factor",
    "drug_response",
    "drug response",
    "conflicting_interpretations_of_pathogenicity",
    "conflicting interpretations of pathogenicity",
}


def _should_suppress(variant: dict, protected_rsids: set[str]) -> bool:
    """Determine if a variant should be suppressed by smart_filter.

    Never suppresses:
    - HIGH impact variants
    - ClinVar Pathogenic/Likely_pathogenic/risk_factor/drug_response/conflicting
    - Known PGx rsIDs (protected_rsids)

    Suppresses when AF available:
    - AF > 0.05 AND (no ClinVar OR ClinVar Benign/Likely_benign) AND not HIGH

    Suppresses when AF unavailable:
    - No ClinVar AND impact is not HIGH
    """
    rsid = variant.get("rsid")
    if rsid and rsid in protected_rsids:
        return False

    ann = variant.get("annotation", {})
    impact = (ann.get("impact") or "").upper()
    if impact == "HIGH":
        return False

    clinvar = variant.get("clinvar", {})
    sig_raw = (clinvar.get("significance") or "").lower()

    # Tokenize multi-valued ClinVar significance (e.g. "pathogenic/likely_pathogenic"
    # or "conflicting_interpretations_of_pathogenicity, benign")
    sig_terms = {t.strip() for t in sig_raw.replace("/", ",").split(",") if t.strip()}

    # Never suppress if any term is protected
    if sig_terms & _PROTECTED_CLINVAR:
        return False

    freq = variant.get("population_freq", {})
    af = freq.get("global")

    # Only treat as benign if ALL terms are benign/likely_benign
    all_benign = sig_terms and all("benign" in t for t in sig_terms)

    if af is not None:
        # AF available: suppress common variants that are benign or unannotated
        return af > 0.05 and (not sig_terms or all_benign)
    else:
        # AF unavailable: suppress unannotated (no ClinVar) non-HIGH variants
        return not sig_terms


def register(mcp, engines, db, config):
    @mcp.tool()
    def query_gene(
        gene: str,
        impact_filter: str = "HIGH,MODERATE",
        max_results: int = 50,
        smart_filter: bool = True,
        genome: str | None = None,
        genome2: str | None = None,
    ) -> str:
        """Query variants in a specific gene from your genome.

        Use this when a user asks about variants in a gene (e.g. "What variants do I have in BRCA1?").
        Filters by SnpEff impact level (HIGH, MODERATE, LOW, MODIFIER) by default.
        If functional annotation is not available, all variants are included regardless
        of impact filter.

        Optional: 'genome' selects which registered genome to query (default: primary genome).
        'genome2' queries a second genome for side-by-side comparison.
        """
        try:
            label, engine = resolve_engine(engines, genome, config)
        except ValueError as e:
            return str(e)

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

        # Smart filter: suppress common benign variants
        suppressed_count = 0
        has_af_data = False
        if smart_filter:
            # Build protected rsID set from PGx variants
            protected_rsids: set[str] = set()
            for pv in db.get_pgx_variants(gene.upper()):
                if pv.get("rsid"):
                    protected_rsids.add(pv["rsid"])

            # Check if any variant has AF data
            has_af_data = any(
                v.get("population_freq", {}).get("global") is not None for v in variants
            )

            kept = []
            for v in variants:
                if _should_suppress(v, protected_rsids):
                    suppressed_count += 1
                else:
                    kept.append(v)
            variants = kept

        # Cap results
        truncated = len(variants) > max_results
        variants = variants[:max_results]

        warning = enhanced_warning_for_genes(db, {gene.upper()})

        show_label = len(engines) > 1
        header = f"## Variants in {gene} ({gene_info['name']})"
        if show_label:
            header += f" — {label}"
        lines = [
            header,
            f"Region: {region} | Filter: {impact_filter} | Found: {len(variants)}",
            "",
        ]

        if truncated:
            lines.append(
                f"*Showing first {max_results} variants. Narrow your query for complete results.*\n"
            )

        if suppressed_count > 0:
            if has_af_data:
                lines.append(
                    f"*{suppressed_count} common/benign variant(s) suppressed by smart filter. "
                    "Use smart_filter=false to see all.*\n"
                )
            else:
                lines.append(
                    f"*{suppressed_count} unannotated variant(s) suppressed by smart filter. "
                    "Population frequency data not available — filtered by ClinVar only. "
                    "Use smart_filter=false to see all.*\n"
                )

        if variants:
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
        elif suppressed_count == 0:
            lines.append(
                f"No {'/'.join(impacts)} impact variants found in the returned results "
                "for this region. Try broadening the impact filter "
                "(e.g. impact_filter='HIGH,MODERATE,LOW,MODIFIER') to see more variants. "
                "Note: unannotated variants without rsID or ClinVar data are excluded "
                "by default."
            )
        else:
            lines.append("No clinically notable variants remain after filtering.")

        # Paired genome query
        if genome2:
            try:
                label2, engine2 = resolve_engine(engines, genome2, config)
            except ValueError as e:
                lines.append(f"\n---\n\n**Genome '{genome2}': {e}**")
                return warning + "\n".join(lines) + DISCLAIMER

            try:
                variants2 = engine2.query_region(region)
            except (ValueError, VCFEngineError) as e:
                lines.append(f"\n---\n\n**Genome '{label2}' error: {e}**")
                return warning + "\n".join(lines) + DISCLAIMER

            # Apply same filters
            if impact_filter:
                variants2 = [
                    v
                    for v in variants2
                    if not v.get("annotation", {}).get("impact")
                    or v["annotation"]["impact"].upper() in impacts
                ]
            variants2 = [
                v
                for v in variants2
                if v.get("annotation", {}).get("impact")
                or v.get("clinvar", {})
                or v.get("rsid")
            ]
            if smart_filter:
                variants2 = [
                    v for v in variants2 if not _should_suppress(v, protected_rsids)
                ]
            variants2 = variants2[:max_results]

            lines.append(
                f"\n---\n\n## Variants in {gene} ({gene_info['name']}) — {label2}"
            )
            lines.append(f"Found: {len(variants2)}\n")
            if variants2:
                lines.append(
                    "| rsID | Position | Genotype | Effect | Impact | ClinVar |"
                )
                lines.append(
                    "|------|----------|----------|--------|--------|---------|"
                )
                for v in variants2:
                    rsid_v = v["rsid"] or "."
                    pos_v = f"{v['chrom']}:{v['pos']}"
                    gt_v = v["genotype"]["display"]
                    ann_v = v.get("annotation", {})
                    effect_v = ann_v.get("effect", ".") or "."
                    impact_v = ann_v.get("impact", ".") or "."
                    clin_v = v.get("clinvar", {})
                    sig_v = clin_v.get("significance", ".") if clin_v else "."
                    lines.append(
                        f"| {rsid_v} | {pos_v} | {gt_v} | {effect_v} | {impact_v} | {sig_v} |"
                    )
            else:
                lines.append("No notable variants found.")

        return warning + "\n".join(lines) + DISCLAIMER
