"""MCP tool modules for GeneChat."""

from genechat.tools import (
    calculate_prs,
    genome_summary,
    query_carrier,
    query_clinvar,
    query_gene,
    query_pgx,
    query_trait,
    query_variant,
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
]


def register_all(mcp, engine, db, config):
    """Register all tools with the MCP server."""
    for module in ALL_TOOLS:
        module.register(mcp, engine, db, config)
