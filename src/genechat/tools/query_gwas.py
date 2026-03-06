"""Search GWAS Catalog for trait-variant associations."""

from genechat.vcf_engine import VCFEngineError

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def _short_zygosity(zygosity: str) -> str:
    """Abbreviate zygosity for table display."""
    return {
        "homozygous_ref": "ref",
        "heterozygous": "het",
        "homozygous_alt": "hom alt",
        "no_call": "no call",
    }.get(zygosity, zygosity)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_gwas(
        trait: str | None = None,
        gene: str | None = None,
        rsid: str | None = None,
        max_results: int = 30,
        deduplicate: bool = True,
        check_vcf: bool = False,
    ) -> str:
        """Search the GWAS Catalog for genome-wide association study findings.

        Use this when a user asks about genetic associations with a disease or trait,
        or to discover what conditions are linked to a gene or variant.
        Provide at least one of: trait (e.g. "type 2 diabetes"), gene (e.g. "FTO"),
        or rsid (e.g. "rs9939609").
        Results are ordered by statistical significance (lowest p-value first).
        """
        if not trait and not gene and not rsid:
            return "Please provide at least one of: trait, gene, or rsid."

        if not db.has_gwas_table():
            return (
                "GWAS Catalog not loaded. Run: "
                "`uv run python scripts/build_gwas_db.py` to build the GWAS database."
            )

        # Clamp max_results to a safe range
        max_results = max(1, min(max_results, 200))

        # Fetch extra rows if deduplicating, to have enough after dedup
        fetch_limit = max_results * 3 if deduplicate else max_results

        try:
            results = db.search_gwas(
                trait=trait, gene=gene, rsid=rsid, max_results=fetch_limit
            )
        except Exception:
            return (
                "Failed to query the GWAS Catalog due to an internal database error. "
                "Try rebuilding the GWAS database with "
                "`uv run python scripts/build_gwas_db.py`."
            )

        # Deduplicate: keep first occurrence per rsid (best p-value)
        if deduplicate and results:
            seen_rsids: set[str] = set()
            deduped = []
            for r in results:
                rs = r.get("rsid") or ""
                if rs and rs in seen_rsids:
                    continue
                if rs:
                    seen_rsids.add(rs)
                deduped.append(r)
                if len(deduped) >= max_results:
                    break
            results = deduped
        else:
            results = results[:max_results]

        if not results:
            parts = []
            if trait:
                parts.append(f"trait='{trait}'")
            if gene:
                parts.append(f"gene='{gene}'")
            if rsid:
                parts.append(f"rsid='{rsid}'")
            return f"No GWAS associations found for {', '.join(parts)}."

        # VCF cross-reference: look up genotypes for result rsIDs
        genotype_map: dict[str, str] = {}
        if check_vcf:
            rsids_to_check = [
                r["rsid"]
                for r in results
                if r.get("rsid") and r["rsid"].startswith("rs")
            ]
            if rsids_to_check:
                try:
                    vcf_results = engine.query_rsids(rsids_to_check)
                    vcf_results.pop("_truncated", None)
                    for rs, vlist in vcf_results.items():
                        if vlist:
                            gt = vlist[0]["genotype"]
                            zyg = _short_zygosity(gt["zygosity"])
                            genotype_map[rs] = f"{gt['display']} ({zyg})"
                except (ValueError, VCFEngineError):
                    pass  # Graceful degradation — just omit genotypes

        # Build header
        search_desc = []
        if trait:
            search_desc.append(f"trait: {trait}")
        if gene:
            search_desc.append(f"gene: {gene}")
        if rsid:
            search_desc.append(f"variant: {rsid}")

        lines = [
            f"## GWAS Catalog Results ({' | '.join(search_desc)})",
            f"Showing {len(results)} association(s), ordered by significance\n",
        ]

        if check_vcf:
            lines.append(
                "| rsID | Gene | Trait | Risk Allele | P-value | OR/Beta | Your Genotype |"
            )
            lines.append(
                "|------|------|-------|-------------|---------|---------|---------------|"
            )
        else:
            lines.append(
                "| rsID | Gene | Trait | Risk Allele | P-value | OR/Beta | Author |"
            )
            lines.append(
                "|------|------|-------|-------------|---------|---------|--------|"
            )

        for r in results:
            rs = r.get("rsid") or "."
            g = r.get("mapped_gene") or "."
            t = r.get("trait") or "."
            # Truncate long trait names
            if len(t) > 50:
                t = t[:47] + "..."
            ra = r.get("risk_allele") or "."
            pv = r.get("p_value")
            pv_str = f"{pv:.1e}" if pv is not None else "."
            ob = r.get("or_beta")
            ob_str = f"{ob:.2f}" if ob is not None else "."

            if check_vcf:
                gt = genotype_map.get(rs, "—")
                lines.append(
                    f"| {rs} | {g} | {t} | {ra} | {pv_str} | {ob_str} | {gt} |"
                )
            else:
                author = r.get("first_author") or "."
                lines.append(
                    f"| {rs} | {g} | {t} | {ra} | {pv_str} | {ob_str} | {author} |"
                )

        return "\n".join(lines) + DISCLAIMER
