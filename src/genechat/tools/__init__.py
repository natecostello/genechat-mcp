"""MCP tool modules for GeneChat."""

from genechat.tools import (
    add_carrier_gene,
    add_pgx_drug,
    add_trait_variant,
    calculate_prs,
    genome_summary,
    query_carrier,
    query_clinvar,
    query_gene,
    query_pgx,
    query_trait,
    query_variant,
    rebuild_database,
)

ALL_TOOLS = [
    query_variant,
    query_gene,
    query_clinvar,
    query_pgx,
    query_trait,
    query_carrier,
    calculate_prs,
    genome_summary,
    add_trait_variant,
    add_carrier_gene,
    add_pgx_drug,
    rebuild_database,
]


def register_all(mcp, engine, db, config):
    """Register all tools with the MCP server."""
    for module in ALL_TOOLS:
        module.register(mcp, engine, db, config)
