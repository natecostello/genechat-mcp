"""GeneChat MCP Server entry point."""

import os
import sys

from mcp.server.fastmcp import FastMCP

from genechat.config import load_config
from genechat.lookup import LookupDB
from genechat.tools import register_all
from genechat.vcf_engine import VCFEngine


def run_server():
    """Initialize and run the MCP server."""
    config_path = os.environ.get("GENECHAT_CONFIG")
    config = load_config(config_path)

    genome_labels = list(config.genomes.keys()) if config.genomes else []
    label_hint = f" ({', '.join(genome_labels)})" if len(genome_labels) > 1 else ""
    mcp = FastMCP(
        "genechat",
        instructions=(
            "GeneChat provides tools to query your whole-genome sequencing data. "
            "Ask about specific variants (rsIDs), genes, drug interactions (pharmacogenomics), "
            "trait associations, carrier status, or get a genome overview. "
            "Always start with genome_summary for a high-level view."
            + (
                f" Multiple genomes are registered{label_hint}. "
                "Use the 'genome' parameter on any tool to select which genome to query, "
                "and 'genome2' for paired comparisons (e.g. carrier screening for couples)."
                if len(genome_labels) > 1
                else ""
            )
        ),
    )

    # Build engines dict — one VCFEngine per registered genome
    max_variants = config.server.max_variants_per_response
    engines: dict[str, VCFEngine] = {}
    if not config.genomes:
        print(
            "Error: No genomes configured. Run 'genechat init <vcf>' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    for label, genome_cfg in config.genomes.items():
        if not genome_cfg.vcf_path:
            print(
                f"Warning: Genome '{label}' has no vcf_path, skipping.",
                file=sys.stderr,
            )
            continue
        try:
            engines[label] = VCFEngine(genome_cfg, max_variants=max_variants)
        except Exception as e:
            print(
                f"Error initializing genome '{label}': {e}",
                file=sys.stderr,
            )
            sys.exit(1)

    if not engines:
        print(
            "Error: No valid genomes could be loaded.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        db = LookupDB(config)
    except FileNotFoundError as e:
        print(f"Error loading lookup database: {e}", file=sys.stderr)
        sys.exit(1)

    # Register all tools
    register_all(mcp, engines, db, config)

    # Run server
    transport = config.server.transport
    if transport == "sse":
        mcp.run(transport="sse", host=config.server.host, port=config.server.port)
    else:
        mcp.run(transport="stdio")


def main():
    from genechat.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
