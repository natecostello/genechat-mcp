"""CLI entry point for GeneChat — dispatches init, serve, and default MCP server."""

import argparse
import json
import sys
from importlib import resources
from pathlib import Path

from platformdirs import user_config_dir

from genechat.config import write_config


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="genechat",
        description="GeneChat MCP server for conversational personal genomics",
    )
    sub = parser.add_subparsers(dest="command")

    # genechat init
    init_p = sub.add_parser("init", help="Set up GeneChat for a VCF file")
    init_p.add_argument("vcf_path", help="Path to your annotated VCF (.vcf.gz)")

    # genechat serve (explicit alias)
    sub.add_parser("serve", help="Start the MCP server")

    args = parser.parse_args(argv)

    if args.command == "init":
        _run_init(args.vcf_path)
    else:
        # No subcommand or "serve" → start MCP server
        _run_serve()


def _run_serve():
    from genechat.server import run_server

    run_server()


def _run_init(vcf_path_str: str):
    vcf_path = Path(vcf_path_str).resolve()

    # 1. Validate VCF exists
    if not vcf_path.exists():
        print(f"Error: VCF file not found: {vcf_path}", file=sys.stderr)
        sys.exit(1)

    # 2. Validate index exists
    tbi = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
    csi = vcf_path.with_suffix(vcf_path.suffix + ".csi")
    if not tbi.exists() and not csi.exists():
        print(
            f"Error: No index file found. Expected {tbi.name} or {csi.name}",
            file=sys.stderr,
        )
        print("Run: tabix -p vcf " + str(vcf_path), file=sys.stderr)
        sys.exit(1)

    # 3. Write config.toml
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir)

    # 4. Ensure lookup_tables.db exists
    db_ref = resources.files("genechat") / "data" / "lookup_tables.db"
    with resources.as_file(db_ref) as db_path:
        if not db_path.exists():
            print("Building lookup database...")
            from scripts.build_lookup_db import build_db

            build_db()

    # 5. Print results
    print(f"\nConfig written to: {config_path}")
    print(f"  Permissions: {oct(config_path.stat().st_mode & 0o777)}")

    # Determine the project directory for MCP config
    project_dir = str(Path(__file__).resolve().parent.parent.parent)

    mcp_config = {
        "mcpServers": {
            "genechat": {
                "command": "uv",
                "args": ["run", "--directory", project_dir, "genechat"],
                "env": {"GENECHAT_CONFIG": str(config_path)},
            }
        }
    }

    print("\nAdd this to your Claude Desktop or Claude Code MCP config:\n")
    print(json.dumps(mcp_config, indent=2))

    # Optional GWAS note
    print(
        "\n(Optional) To enable GWAS trait search, run:\n"
        "  uv run python scripts/build_gwas_db.py"
    )
