"""Search GWAS Catalog for trait-variant associations."""

DISCLAIMER = (
    "\n\n---\n*NOTE: This is informational only and not a medical diagnosis. "
    "Discuss findings with a healthcare provider before making health decisions.*"
)


def register(mcp, engine, db, config):
    @mcp.tool()
    def query_gwas(
        trait: str | None = None,
        gene: str | None = None,
        rsid: str | None = None,
        max_results: int = 30,
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

        results = db.search_gwas(
            trait=trait, gene=gene, rsid=rsid, max_results=max_results
        )

        if not results:
            parts = []
            if trait:
                parts.append(f"trait='{trait}'")
            if gene:
                parts.append(f"gene='{gene}'")
            if rsid:
                parts.append(f"rsid='{rsid}'")
            return f"No GWAS associations found for {', '.join(parts)}."

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
            author = r.get("first_author") or "."
            lines.append(
                f"| {rs} | {g} | {t} | {ra} | {pv_str} | {ob_str} | {author} |"
            )

        return "\n".join(lines) + DISCLAIMER
