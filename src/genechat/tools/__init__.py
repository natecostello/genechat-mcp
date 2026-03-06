"""MCP tool modules for GeneChat."""

from genechat.tools import (
    add_carrier_gene,
    add_pgx_drug,
    add_trait_variant,
    calculate_prs,
    compile_findings,
    genome_summary,
    query_carrier,
    query_clinvar,
    query_gene,
    query_genes,
    query_gwas,
    query_pgx,
    query_trait,
    query_variant,
    query_variants,
    rebuild_database,
)

ALL_TOOLS = [
    query_variant,
    query_variants,
    query_gene,
    query_genes,
    query_clinvar,
    query_gwas,
    query_pgx,
    query_trait,
    query_carrier,
    calculate_prs,
    genome_summary,
    compile_findings,
    add_trait_variant,
    add_carrier_gene,
    add_pgx_drug,
    rebuild_database,
]


def register_all(mcp, engine, db, config):
    """Register all tools with the MCP server."""
    for module in ALL_TOOLS:
        module.register(mcp, engine, db, config)
