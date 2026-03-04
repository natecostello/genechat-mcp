"""GeneChat MCP Server entry point."""

import os
import sys

from mcp.server.fastmcp import FastMCP

from genechat.config import load_config
from genechat.lookup import LookupDB
from genechat.tools import register_all
from genechat.vcf_engine import VCFEngine


def main():
    config_path = os.environ.get("GENECHAT_CONFIG")
    config = load_config(config_path)

    mcp = FastMCP(
        "genechat",
        instructions=(
            "GeneChat provides tools to query your whole-genome sequencing data. "
            "Ask about specific variants (rsIDs), genes, drug interactions (pharmacogenomics), "
            "trait associations, carrier status, or get a genome overview. "
            "Always start with genome_summary for a high-level view."
        ),
    )

    # Initialize engine and database
    try:
        engine = VCFEngine(config)
    except (FileNotFoundError, Exception) as e:
        print(f"Error initializing VCF engine: {e}", file=sys.stderr)
        print("Set genome.vcf_path in your config to a valid annotated VCF.", file=sys.stderr)
        sys.exit(1)

    try:
        db = LookupDB(config)
    except FileNotFoundError as e:
        print(f"Error loading lookup database: {e}", file=sys.stderr)
        sys.exit(1)

    # Register all tools
    register_all(mcp, engine, db, config)

    # Run server
    transport = config.server.transport
    if transport == "sse":
        mcp.run(transport="sse", host=config.server.host, port=config.server.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
