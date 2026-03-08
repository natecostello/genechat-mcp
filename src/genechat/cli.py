"""CLI entry point for GeneChat — dispatches init, serve, and default MCP server."""

import argparse
import json
import shlex
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


def _find_project_root() -> Path | None:
    """Walk up from this file's location to find a pyproject.toml (source checkout)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # src/genechat → src → repo root (up to 5 levels)
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return None


def _run_serve():
    from genechat.server import run_server

    run_server()


def _run_init(vcf_path_str: str):
    vcf_path = Path(vcf_path_str).expanduser().resolve()

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
        print(f"Run: tabix -p vcf {shlex.quote(str(vcf_path))}", file=sys.stderr)
        sys.exit(1)

    # 3. Try to open the VCF to verify it's valid
    try:
        import pysam

        with pysam.VariantFile(str(vcf_path)) as _vf:
            pass
    except Exception as exc:
        print(f"Error: Cannot read VCF: {exc}", file=sys.stderr)
        print(
            "Ensure the file is bgzip-compressed and the index matches.",
            file=sys.stderr,
        )
        sys.exit(1)

    # 4. Ensure lookup_tables.db exists; build automatically if in source checkout
    db_ref = resources.files("genechat") / "data" / "lookup_tables.db"
    with resources.as_file(db_ref) as db_path:
        if not db_path.exists():
            project_root = _find_project_root()
            build_script = (
                project_root / "scripts" / "build_lookup_db.py"
                if project_root
                else None
            )
            seed_dir = project_root / "data" / "seed" if project_root else None

            if (
                build_script
                and build_script.exists()
                and seed_dir
                and seed_dir.exists()
            ):
                print("Building lookup_tables.db from seed data...")
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "build_lookup_db", str(build_script)
                )
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                mod.build_db(seed_dir=seed_dir, db_path=db_path)
                print(f"  Built: {db_path}")
            else:
                print(
                    "Error: lookup_tables.db not found. The server cannot start without it.",
                    file=sys.stderr,
                )
                print("Build it with:", file=sys.stderr)
                print("  uv run python scripts/build_lookup_db.py", file=sys.stderr)
                sys.exit(1)

    # 5. Write config.toml
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir)

    # 6. Print results
    print(f"\nConfig written to: {config_path}")
    print(f"  Permissions: {oct(config_path.stat().st_mode & 0o777)}")

    # Determine MCP config: use uv run --directory if in a source checkout,
    # otherwise use the installed entrypoint directly
    project_dir = _find_project_root()
    if project_dir:
        mcp_config = {
            "mcpServers": {
                "genechat": {
                    "command": "uv",
                    "args": ["run", "--directory", str(project_dir), "genechat"],
                    "env": {"GENECHAT_CONFIG": str(config_path)},
                }
            }
        }
    else:
        mcp_config = {
            "mcpServers": {
                "genechat": {
                    "command": "genechat",
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
