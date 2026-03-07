"""Query all variants in a gene region."""

from genechat.tools.formatting import short_zygosity
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
    - Known trait or PGx rsIDs (protected_rsids)

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


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_gene(
        gene: str,
        impact_filter: str = "HIGH,MODERATE",
        max_results: int = 50,
        smart_filter: bool = True,
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

        # Smart filter: suppress common benign variants
        suppressed_count = 0
        has_af_data = False
        if smart_filter:
            # Build protected rsID set from trait + PGx variants
            protected_rsids: set[str] = set()
            for tv in db.get_trait_variants(gene=gene.upper()):
                if tv.get("rsid"):
                    protected_rsids.add(tv["rsid"])
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

        if not variants and suppressed_count == 0:
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

        if not variants:
            lines.append("No clinically notable variants remain after filtering.")
            return "\n".join(lines) + DISCLAIMER

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

        # Trait overlay: show known trait associations for this gene with genotypes
        trait_variants = db.get_trait_variants(gene=gene.upper())
        if trait_variants:
            lines.append("")
            lines.append(f"### Known Trait Associations for {gene.upper()}")
            lines.append(
                "| rsID | Trait | Your Genotype | Effect Allele | Description | Evidence |"
            )
            lines.append(
                "|------|-------|---------------|---------------|-------------|----------|"
            )

            # Batch VCF lookup: collect all regions, query once
            tv_regions = []
            tv_region_idx = []  # maps region index → trait_variant index
            for i, tv in enumerate(trait_variants):
                if tv.get("chrom") and tv.get("pos"):
                    tv_regions.append(f"{tv['chrom']}:{tv['pos']}-{tv['pos'] + 1}")
                    tv_region_idx.append(i)

            # Query all trait variant positions in one VCF open
            vcf_results_by_region: dict[int, list[dict]] = {}
            batch_query_ok = False
            if tv_regions:
                try:
                    all_results = engine.query_regions(tv_regions)
                    # Map results back by position
                    pos_map: dict[str, list[dict]] = {}
                    for v in all_results:
                        key = f"{v['chrom']}:{v['pos']}"
                        pos_map.setdefault(key, []).append(v)
                    for ri, ti in enumerate(tv_region_idx):
                        tv = trait_variants[ti]
                        key = f"{tv['chrom']}:{tv['pos']}"
                        if key in pos_map:
                            vcf_results_by_region[ti] = pos_map[key]
                    batch_query_ok = True
                except (ValueError, VCFEngineError):
                    pass  # Graceful degradation

            for i, tv in enumerate(trait_variants):
                tv_rsid = tv.get("rsid", ".")
                trait = tv.get("trait", ".")
                ea = tv.get("effect_allele", ".")
                desc = tv.get("effect_description", ".")
                evid = tv.get("evidence_level", ".")

                gt_display = "—"
                if tv.get("chrom") and tv.get("pos"):
                    tv_results = vcf_results_by_region.get(i)
                    if tv_results:
                        gt = tv_results[0]["genotype"]
                        gt_display = (
                            f"{gt['display']} ({short_zygosity(gt['zygosity'])})"
                        )
                    elif batch_query_ok:
                        gt_display = "ref or not covered"
                    elif tv_regions and not batch_query_ok:
                        gt_display = "query error"

                lines.append(
                    f"| {tv_rsid} | {trait} | {gt_display} | {ea} | {desc} | {evid} |"
                )

        return "\n".join(lines) + DISCLAIMER
