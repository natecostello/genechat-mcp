"""Search GWAS Catalog for trait-variant associations."""

import re

from genechat.tools.common import resolve_engine
from genechat.tools.formatting import short_zygosity
from genechat.vcf_engine import VCFEngineError

_RSID_RE = re.compile(r"^rs\d+$")

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engines, db, config):
    @mcp.tool()
    def query_gwas(
        trait: str | None = None,
        gene: str | None = None,
        rsid: str | None = None,
        max_results: int = 30,
        deduplicate: bool = True,
        check_vcf: bool = False,
        genome: str | None = None,
    ) -> str:
        """Search the GWAS Catalog for genome-wide association study findings.

        Use this when a user asks about genetic associations with a disease or trait,
        or to discover what conditions are linked to a gene or variant.
        Provide at least one of: trait (e.g. "type 2 diabetes"), gene (e.g. "FTO"),
        or rsid (e.g. "rs9939609").
        Results are ordered by statistical significance (lowest p-value first).

        Optional: 'genome' selects which registered genome to use for VCF cross-reference
        when check_vcf=true (default: primary genome).
        """
        if not trait and not gene and not rsid:
            return "Please provide at least one of: trait, gene, or rsid."

        try:
            _label, engine = resolve_engine(engines, genome, config)
        except ValueError as e:
            return str(e)

        if not db.has_gwas_table():
            return (
                "GWAS Catalog not loaded. Run: "
                "`genechat install --gwas` to download and build the GWAS database."
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
                "`genechat install --gwas`."
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
        vcf_truncated = None
        vcf_lookup_failed = False
        if check_vcf:
            rsids_to_check = [
                r["rsid"]
                for r in results
                if r.get("rsid") and _RSID_RE.match(r["rsid"])
            ]
            if rsids_to_check:
                try:
                    vcf_results = engine.query_rsids(rsids_to_check)
                    vcf_truncated = vcf_results.pop("_truncated", None)
                    for rs, vlist in vcf_results.items():
                        if vlist:
                            gt = vlist[0]["genotype"]
                            zyg = short_zygosity(gt["zygosity"])
                            genotype_map[rs] = f"{gt['display']} ({zyg})"
                except (ValueError, VCFEngineError):
                    vcf_lookup_failed = True

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

        if check_vcf and vcf_lookup_failed:
            lines.append(
                "*Warning: VCF genotype lookup failed — genotype column will show '—'.*\n"
            )
        elif check_vcf and vcf_truncated:
            lines.append(
                "*Note: VCF genotype lookup was truncated — some variants may show '—' "
                "due to query limits.*\n"
            )

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
