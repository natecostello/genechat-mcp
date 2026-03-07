"""MCP tool modules for GeneChat."""

from genechat.tools import (
    calculate_prs,
    genome_summary,
    query_clinvar,
    query_gene,
    query_genes,
    query_gwas,
    query_pgx,
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
    calculate_prs,
    genome_summary,
    rebuild_database,
]


def register_all(mcp, engine, db, config):
    """Register all tools with the MCP server."""
    for module in ALL_TOOLS:
        module.register(mcp, engine, db, config)
