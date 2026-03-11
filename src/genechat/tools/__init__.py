"""MCP tool modules for GeneChat."""

from genechat.tools import (
    calculate_prs,
    genome_summary,
    list_genomes,
    query_clinvar,
    query_gene,
    query_genes,
    query_gwas,
    query_pgx,
    query_variant,
    query_variants,
)

ALL_TOOLS = [
    list_genomes,
    query_variant,
    query_variants,
    query_gene,
    query_genes,
    query_clinvar,
    query_gwas,
    query_pgx,
    calculate_prs,
    genome_summary,
]


def register_all(mcp, engines, db, config):
    """Register all tools with the MCP server.

    ``engines`` is a dict mapping genome labels to VCFEngine instances.
    """
    for module in ALL_TOOLS:
        module.register(mcp, engines, db, config)
