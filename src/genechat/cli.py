"""CLI entry point for GeneChat — dispatches subcommands.

Commands:
  genechat init <vcf>           Full first-time setup (add + annotate)
  genechat add <vcf>            Register a VCF file
  genechat annotate [options]   Build/update patch.db (auto-downloads references)
  genechat install [options]    Install genome-independent reference databases
  genechat update [--apply]     Check for newer references
  genechat status               Show genome + annotation state
  genechat serve / genechat     Start the MCP server
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from enum import IntEnum
from pathlib import Path

from platformdirs import user_config_dir

from genechat import __version__
from genechat.config import load_config, write_config


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class ExitCode(IntEnum):
    """Named exit codes for distinct failure modes."""

    SUCCESS = 0
    GENERAL_ERROR = 1
    USAGE_ERROR = 2
    CONFIG_ERROR = 3
    VCF_ERROR = 4
    TOOL_ERROR = 5
    NETWORK_ERROR = 6


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_COLOR_ENABLED: bool | None = None


def _color_enabled() -> bool:
    """Check if color output is enabled (respects NO_COLOR, TERM, TTY).

    Checks both stdout and stderr since styled output may be written to either.
    """
    global _COLOR_ENABLED
    if _COLOR_ENABLED is not None:
        return _COLOR_ENABLED
    if os.environ.get("NO_COLOR") is not None:
        _COLOR_ENABLED = False
    elif os.environ.get("TERM") == "dumb":
        _COLOR_ENABLED = False
    elif not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        _COLOR_ENABLED = False
    elif not hasattr(sys.stderr, "isatty") or not sys.stderr.isatty():
        _COLOR_ENABLED = False
    else:
        _COLOR_ENABLED = True
    return _COLOR_ENABLED


def _style(text: str, code: str) -> str:
    """Wrap text in ANSI escape codes if color is enabled."""
    if not _color_enabled():
        return text
    return f"\033[{code}m{text}\033[0m"


def _red(text: str) -> str:
    return _style(text, "31")


def _green(text: str) -> str:
    return _style(text, "32")


def _yellow(text: str) -> str:
    return _style(text, "33")


def _dim(text: str) -> str:
    return _style(text, "2")


# ---------------------------------------------------------------------------
# Concise help text for interactive use with no subcommand
# ---------------------------------------------------------------------------

_INTERACTIVE_HELP = """\
GeneChat — MCP server for conversational personal genomics

Commands:
  genechat init <vcf>       Full first-time setup (register + annotate)
  genechat add <vcf>        Register a VCF file
  genechat annotate         Build/update annotation database
  genechat install --gwas   Install GWAS Catalog
  genechat update           Check for newer references
  genechat status           Show genome info and annotation state
  genechat serve            Start the MCP server

Quick start:
  genechat init /path/to/your/raw.vcf.gz

Run 'genechat <command> --help' for details on each command.

Docs:  https://github.com/natecostello/genechat-mcp#readme
Issues: https://github.com/natecostello/genechat-mcp/issues
"""


def main(argv: list[str] | None = None):
    # Reset color cache for testability
    global _COLOR_ENABLED
    _COLOR_ENABLED = None

    parser = argparse.ArgumentParser(
        prog="genechat",
        description="GeneChat MCP server for conversational personal genomics",
        epilog=(
            "Docs:   https://github.com/natecostello/genechat-mcp#readme\n"
            "Issues: https://github.com/natecostello/genechat-mcp/issues"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable color output",
    )
    sub = parser.add_subparsers(dest="command")

    # genechat init
    init_p = sub.add_parser(
        "init",
        help="Full first-time setup for a VCF file",
        description=(
            "Full first-time setup for a VCF file.\n\n"
            "Examples:\n"
            "  genechat init /path/to/raw.vcf.gz\n"
            "  genechat init /path/to/raw.vcf.gz --label personal --gnomad"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    init_p.add_argument("vcf_path", help="Path to your raw VCF (.vcf.gz)")
    init_p.add_argument("--label", help="Name for this genome (default: from filename)")
    init_p.add_argument(
        "--gnomad",
        action="store_true",
        help="Also annotate gnomAD population frequencies (~17 GB peak disk)",
    )
    init_p.add_argument(
        "--dbsnp", action="store_true", help="Also download dbSNP (~20 GB)"
    )
    init_p.add_argument(
        "--gwas", action="store_true", help="Also download GWAS Catalog (~58 MB)"
    )

    # genechat add
    add_p = sub.add_parser("add", help="Register a VCF file")
    add_p.add_argument("vcf_path", help="Path to your VCF (.vcf.gz)")
    add_p.add_argument("--label", help="Name for this genome")

    # genechat install
    inst_p = sub.add_parser(
        "install", help="Install genome-independent reference databases"
    )
    inst_p.add_argument(
        "--gwas", action="store_true", help="Install GWAS Catalog (~58 MB download)"
    )
    inst_p.add_argument(
        "--force",
        action="store_true",
        help="Re-download source files even if already present (DB is always rebuilt)",
    )

    # genechat annotate
    ann_p = sub.add_parser(
        "annotate",
        help="Build or update patch.db",
        description=(
            "Build or update the annotation database (patch.db).\n\n"
            "Examples:\n"
            "  genechat annotate              # show status or build if new\n"
            "  genechat annotate --all        # re-annotate all layers\n"
            "  genechat annotate --gnomad     # add gnomAD frequencies"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ann_p.add_argument(
        "--clinvar", action="store_true", help="Re-annotate ClinVar layer"
    )
    ann_p.add_argument(
        "--gnomad",
        action="store_true",
        help="Re-annotate gnomAD layer (downloads incrementally if not present)",
    )
    ann_p.add_argument("--snpeff", action="store_true", help="Re-annotate SnpEff layer")
    ann_p.add_argument("--dbsnp", action="store_true", help="Re-annotate dbSNP layer")
    ann_p.add_argument("--all", action="store_true", help="Re-annotate all layers")
    ann_p.add_argument("--genome", help="Which genome to annotate (default: primary)")

    # genechat update
    upd_p = sub.add_parser("update", help="Check for newer reference versions")
    upd_p.add_argument(
        "--apply", action="store_true", help="Download + re-annotate stale sources"
    )
    upd_p.add_argument("--genome", help="Which genome to update (default: primary)")
    upd_p.add_argument(
        "--seeds",
        action="store_true",
        help="Fetch latest seed data from APIs and rebuild lookup_tables.db",
    )

    # genechat status
    status_p = sub.add_parser(
        "status",
        help="Show genome info and annotation state",
        description=(
            "Show genome registration, annotation state, and reference versions.\n\n"
            "Examples:\n"
            "  genechat status          # human-readable summary\n"
            "  genechat status --json   # machine-readable JSON output"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    status_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output status as JSON",
    )

    # genechat serve
    sub.add_parser("serve", help="Start the MCP server")

    args = parser.parse_args(argv)

    # Handle --no-color
    if getattr(args, "no_color", False):
        _COLOR_ENABLED = False

    try:
        if args.command == "init":
            _run_init(args)
        elif args.command == "add":
            _run_add(args.vcf_path, args.label)
        elif args.command == "install":
            _run_install(args)
        elif args.command == "annotate":
            _run_annotate(args)
        elif args.command == "update":
            _run_update(args)
        elif args.command == "status":
            _run_status(json_output=getattr(args, "json_output", False))
        else:
            # No subcommand or "serve"
            if args.command is None and sys.stdin.isatty():
                print(_INTERACTIVE_HELP, end="")
            else:
                _run_serve()
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\n{_red('Unexpected error:')} {exc}", file=sys.stderr)
        print(
            "Please report this at https://github.com/natecostello/genechat-mcp/issues",
            file=sys.stderr,
        )
        sys.exit(ExitCode.GENERAL_ERROR)


def _find_project_root() -> Path | None:
    """Walk up from this file's location to find a pyproject.toml (source checkout)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return None


def _ensure_lookup_db() -> bool:
    """Ensure lookup_tables.db exists. Auto-build if in a source checkout.

    Returns True if DB is available, False if not.
    """
    from importlib import resources

    data_dir_ref = resources.files("genechat") / "data"
    with resources.as_file(data_dir_ref) as data_dir:
        db_path = data_dir / "lookup_tables.db"
        if db_path.exists():
            return True

        project_root = _find_project_root()
        build_script = (
            project_root / "scripts" / "build_lookup_db.py" if project_root else None
        )
        seed_dir = project_root / "data" / "seed" if project_root else None

        if build_script and build_script.exists() and seed_dir and seed_dir.exists():
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "genechat_build_lookup_db", str(build_script)
            )
            if spec is not None and spec.loader is not None:
                try:
                    build_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(build_mod)
                    print("Building lookup_tables.db from seed data...")
                    build_mod.build_db(seed_dir=seed_dir, db_path=db_path)
                    print(f"  Built: {db_path}")
                    return True
                except Exception as exc:
                    print(f"Error building lookup_tables.db: {exc}", file=sys.stderr)
                    return False

        print(
            "Error: lookup_tables.db not found.",
            file=sys.stderr,
        )
        if project_root:
            print("Build it with:", file=sys.stderr)
            print("  uv run python scripts/build_lookup_db.py", file=sys.stderr)
        else:
            print(
                "The built-in lookup database should have been installed with the package.",
                file=sys.stderr,
            )
            print(
                "Try reinstalling: uv tool install genechat-mcp",
                file=sys.stderr,
            )
        return False


def _run_serve():
    from genechat.server import run_server

    run_server()


# ---------------------------------------------------------------------------
# genechat add <vcf>
# ---------------------------------------------------------------------------


def _validate_vcf(vcf_path: Path) -> bool:
    """Validate VCF exists, has index, and is readable.

    Prints errors and returns False on failure.
    """
    if not vcf_path.exists():
        print(
            f"{_red('Error:')} VCF file not found: {_dim(str(vcf_path))}",
            file=sys.stderr,
        )
        return False

    # Check for index
    tbi = vcf_path.with_suffix(vcf_path.suffix + ".tbi")
    csi = vcf_path.with_suffix(vcf_path.suffix + ".csi")
    if not tbi.exists() and not csi.exists():
        # Try to create index
        print("  No index found. Creating tabix index...")
        try:
            import pysam

            pysam.tabix_index(str(vcf_path), preset="vcf", force=True)
            print("  Index created.")
        except Exception as exc:
            print(f"Error: Cannot create index: {exc}", file=sys.stderr)
            print(
                f"Run manually: tabix -p vcf {shlex.quote(str(vcf_path))}",
                file=sys.stderr,
            )
            return False

    # Verify readable
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
        return False

    return True


def _run_add(vcf_path_str: str, label: str | None = None):
    """Register a VCF: validate, ensure index, write config."""
    vcf_path = Path(vcf_path_str).expanduser().resolve()

    if not _validate_vcf(vcf_path):
        sys.exit(ExitCode.VCF_ERROR)

    # Write config
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir, label=label or "")
    genome_label = label or "default"
    print(f"VCF registered as '{genome_label}'. Config: {config_path}")
    return config_path


# ---------------------------------------------------------------------------
# genechat install [options]
# ---------------------------------------------------------------------------


def _run_install(args):
    """Install genome-independent reference databases."""
    from genechat.gwas import gwas_db_path

    print(f"Data directory: {gwas_db_path().parent}\n")

    if args.gwas:
        from genechat.gwas import gwas_installed

        if gwas_installed() and not args.force:
            print("GWAS Catalog already installed. Use --force to rebuild.")
        else:
            _download_and_build_gwas(force=args.force)
    else:
        print("Available databases:")
        print(
            "  --gwas    GWAS Catalog associations (~58 MB download, ~300 MB on disk)"
        )
        print("\nRun: genechat install --gwas")
        return

    print("\nInstall complete.")


# ---------------------------------------------------------------------------
# genechat annotate [options]
# ---------------------------------------------------------------------------


def _resolve_genome_label(config, genome_arg: str | None) -> tuple[str, object]:
    """Resolve a --genome arg to (label, GenomeConfig). Exits on error."""
    if not config.genomes:
        print(
            f"{_red('Error:')} No VCF registered. Run: genechat add <vcf>",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CONFIG_ERROR)

    label = genome_arg or config.default_genome
    if label not in config.genomes:
        available = ", ".join(config.genomes.keys())
        print(
            f"{_red('Error:')} Unknown genome '{label}'. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CONFIG_ERROR)

    return label, config.genomes[label]


def _run_annotate(args):
    """Build or update patch.db for the registered VCF."""
    config = load_config()
    genome_arg = getattr(args, "genome", None)
    label, genome_cfg = _resolve_genome_label(config, genome_arg)

    vcf_path_str = genome_cfg.vcf_path
    if not vcf_path_str:
        print(
            f"{_red('Error:')} Genome '{label}' has no vcf_path. Run: genechat add <vcf>",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CONFIG_ERROR)

    vcf_path = Path(vcf_path_str)
    if not vcf_path.exists():
        print(
            f"{_red('Error:')} VCF not found: {_dim(str(vcf_path))}",
            file=sys.stderr,
        )
        sys.exit(ExitCode.VCF_ERROR)

    # Determine patch.db path
    patch_db_path = _patch_db_path_for(vcf_path, genome_cfg)

    from genechat.download import (
        clinvar_installed,
        dbsnp_installed,
        download_clinvar,
        download_dbsnp,
        download_snpeff_db,
        gnomad_installed,
        snpeff_installed,
    )
    from genechat.patch import PatchDB

    # Determine which layers to run
    any_flag = args.clinvar or args.gnomad or args.snpeff or args.dbsnp or args.all
    first_run = not patch_db_path.exists()

    if not any_flag and not first_run:
        # No flags and patch.db exists -> show status
        _print_annotation_status(patch_db_path)
        return

    # On first run or --all, run everything available
    run_snpeff = first_run or args.snpeff or args.all
    run_clinvar = first_run or args.clinvar or args.all
    # gnomAD/dbSNP: run when explicitly requested, or on first run if already available
    run_gnomad = args.gnomad or args.all or (first_run and gnomad_installed())
    gnomad_incremental = run_gnomad and not gnomad_installed()
    run_dbsnp = args.dbsnp or args.all or (first_run and dbsnp_installed())

    # Check tool prerequisites (can't auto-install system packages)
    if run_snpeff and not snpeff_installed():
        print(
            f"{_red('Error:')} snpEff not found in PATH. Required for functional annotation.",
            file=sys.stderr,
        )
        print("  Install: brew install brewsci/bio/snpeff (macOS)", file=sys.stderr)
        sys.exit(ExitCode.TOOL_ERROR)

    if not shutil.which("bcftools"):
        print(f"{_red('Error:')} bcftools not found in PATH.", file=sys.stderr)
        print("  Install: brew install bcftools (macOS)", file=sys.stderr)
        sys.exit(ExitCode.TOOL_ERROR)

    needs_tabix = run_clinvar or (run_dbsnp and not dbsnp_installed())
    if needs_tabix and not shutil.which("tabix"):
        print(
            f"{_red('Error:')} tabix not found in PATH (needed for contig rename).",
            file=sys.stderr,
        )
        print("  Install: brew install htslib (macOS)", file=sys.stderr)
        sys.exit(ExitCode.TOOL_ERROR)

    # Auto-download references if not present
    if run_clinvar and not clinvar_installed():
        print("  Downloading ClinVar reference...")
        download_clinvar()

    if run_snpeff:
        if download_snpeff_db() is None:
            print(f"{_red('Error:')} SnpEff database download failed.", file=sys.stderr)
            sys.exit(ExitCode.NETWORK_ERROR)

    if run_dbsnp and not dbsnp_installed():
        print("  Downloading dbSNP reference...")
        result = download_dbsnp()
        if result is None:
            print(
                f"{_red('Error:')} dbSNP download/processing failed.", file=sys.stderr
            )
            sys.exit(ExitCode.NETWORK_ERROR)

    # Create or open patch.db
    if first_run:
        patch = PatchDB.create(patch_db_path)
        print(f"Building patch.db for {vcf_path.name}...")
    else:
        patch = PatchDB(patch_db_path)
        print(f"Updating patch.db for {vcf_path.name}...")

    step = 0
    total_steps = sum([run_snpeff, run_clinvar, run_gnomad, run_dbsnp])

    try:
        if run_snpeff:
            step += 1
            _annotate_snpeff(patch, vcf_path, step, total_steps, not first_run)

        if run_clinvar:
            step += 1
            _annotate_clinvar(patch, vcf_path, step, total_steps, not first_run)

        if run_gnomad:
            step += 1
            _annotate_gnomad(
                patch,
                vcf_path,
                step,
                total_steps,
                not first_run,
                incremental=gnomad_incremental,
            )

        if run_dbsnp:
            step += 1
            _annotate_dbsnp(patch, vcf_path, step, total_steps, not first_run)

        # Store VCF fingerprint
        patch.store_vcf_fingerprint(vcf_path)

        # Update config with patch_db path
        _update_config_patch_db(patch_db_path, label)

    finally:
        patch.close()

    size_mb = patch_db_path.stat().st_size / 1024 / 1024
    print(f"\nPatch database: {patch_db_path} ({size_mb:.0f} MB)")


def _patch_db_path_for(vcf_path: Path, genome_cfg) -> Path:
    """Determine the patch.db path for a VCF.

    Accepts either a GenomeConfig or an AppConfig (for backward compat).
    """
    from genechat.config import AppConfig, GenomeConfig

    if isinstance(genome_cfg, AppConfig):
        genome_cfg = genome_cfg.genome
    if isinstance(genome_cfg, GenomeConfig) and genome_cfg.patch_db:
        return Path(genome_cfg.patch_db)
    # Convention: same directory as VCF, <stem>.patch.db
    return vcf_path.parent / f"{vcf_path.stem.replace('.vcf', '')}.patch.db"


def _contig_rename_clinvar(clinvar_vcf: Path, work_dir: Path) -> Path:
    """If ClinVar uses bare contig names, rename to chr prefix.

    Returns path to the ClinVar VCF to use (original or renamed copy).
    """
    import re

    result = subprocess.run(
        ["bcftools", "view", "-h", str(clinvar_vcf)],
        capture_output=True,
        text=True,
        check=True,
    )
    # Check if first contig uses bare names (e.g., ID=1 not ID=chr1)
    for line in result.stdout.split("\n"):
        if line.startswith("##contig"):
            if re.search(r"ID=\d", line):
                print("    Renaming ClinVar contigs to chr prefix...")
                chr_map = work_dir / "chr_rename.txt"
                with open(chr_map, "w") as f:
                    for i in range(1, 23):
                        f.write(f"{i} chr{i}\n")
                    f.write("X chrX\nY chrY\nMT chrMT\n")
                fixed = work_dir / "clinvar_chrfixed.vcf.gz"
                subprocess.run(
                    [
                        "bcftools",
                        "annotate",
                        "--rename-chrs",
                        str(chr_map),
                        str(clinvar_vcf),
                        "-Oz",
                        "-o",
                        str(fixed),
                    ],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["tabix", "-p", "vcf", str(fixed)],
                    check=True,
                    capture_output=True,
                )
                chr_map.unlink()
                return fixed
            break  # Only check the first contig line
    return clinvar_vcf


def _annotate_snpeff(patch, vcf_path: Path, step: int, total: int, is_update: bool):
    """Step 1: SnpEff functional annotation."""
    from genechat.download import _detect_snpeff_db

    db_name = _detect_snpeff_db()
    print(f"  [{step}/{total}] SnpEff functional annotation ({db_name})...")

    if is_update:
        patch.clear_layer("snpeff")

    patch.set_metadata("snpeff", db_name, status="pending")

    try:
        # Get chromosome list from VCF
        import pysam

        with pysam.VariantFile(str(vcf_path)) as vf:
            chroms = list(vf.header.contigs)

        total_rows = 0
        print(
            "    Starting SnpEff (JVM startup may take a few seconds)...",
            flush=True,
        )
        for i, chrom in enumerate(chroms, 1):
            print(f"    {chrom} ({i}/{len(chroms)})...", end="", flush=True)
            # Per-chromosome to avoid SnpEff OOM
            bcf_proc = subprocess.Popen(
                ["bcftools", "view", "-r", chrom, str(vcf_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            snpeff_proc = subprocess.Popen(
                ["snpEff", "ann", "-noStats", db_name, "-"],
                stdin=bcf_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            # Allow bcf_proc to receive SIGPIPE if snpeff_proc exits
            bcf_proc.stdout.close()

            rows = patch.populate_from_snpeff_stream(iter(snpeff_proc.stdout))
            total_rows += rows
            snpeff_rc = snpeff_proc.wait()
            bcf_rc = bcf_proc.wait()
            print(f" {rows:,} variants")
            if snpeff_rc != 0:
                raise RuntimeError(
                    f"snpEff ann failed with exit code {snpeff_rc} on {chrom}"
                )
            if bcf_rc != 0:
                raise RuntimeError(
                    f"bcftools view failed with exit code {bcf_rc} on {chrom}"
                )
    except Exception:
        patch.set_metadata("snpeff", db_name, status="failed")
        raise

    patch.set_metadata("snpeff", db_name, status="complete")
    print(f"    {total_rows} variants processed")


def _annotate_clinvar(patch, vcf_path: Path, step: int, total: int, is_update: bool):
    """Step 2: ClinVar clinical significance."""
    from genechat.download import clinvar_path

    print(f"  [{step}/{total}] ClinVar clinical significance...")

    if is_update:
        patch.clear_layer("clinvar")

    # Determine ClinVar version from file date header
    clinvar_vcf = clinvar_path()
    version = _clinvar_version(clinvar_vcf)
    patch.set_metadata("clinvar", version or "unknown", status="pending")

    # Handle contig rename if needed (use tempdir for work artifacts)
    import tempfile

    work_dir = Path(tempfile.mkdtemp(prefix="genechat_"))

    try:
        clinvar_use = _contig_rename_clinvar(clinvar_vcf, work_dir)

        proc = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "-a",
                str(clinvar_use),
                "-c",
                "INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT",
                str(vcf_path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        rows = patch.update_clinvar_from_stream(iter(proc.stdout))
        rc = proc.wait()
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"bcftools annotate (ClinVar) failed with exit code {rc}: {stderr}"
            )
    except Exception:
        patch.set_metadata("clinvar", version or "unknown", status="failed")
        # Clean up work directory before re-raising
        import shutil as _shutil

        _shutil.rmtree(work_dir, ignore_errors=True)
        raise
    else:
        # Clean up work directory on success
        import shutil as _shutil

        _shutil.rmtree(work_dir, ignore_errors=True)

    patch.set_metadata("clinvar", version or "unknown", status="complete")
    print(f"    {rows} variants updated")


def _clinvar_version(clinvar_vcf: Path) -> str | None:
    """Extract ClinVar version from the ##fileDate header."""
    result = subprocess.run(
        ["bcftools", "view", "-h", str(clinvar_vcf)],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("##fileDate="):
            return line.split("=", 1)[1].strip()
    return None


def _annotate_gnomad(
    patch,
    vcf_path: Path,
    step: int,
    total: int,
    is_update: bool,
    incremental: bool = False,
):
    """Step 3: gnomAD population frequencies (per-chromosome).

    When incremental=True, downloads each chromosome before annotating it
    and deletes the file afterward to minimize peak disk usage (~17 GB
    instead of ~150 GB).
    """
    from genechat.download import GNOMAD_CHROMS, gnomad_chr_path

    if incremental:
        from genechat.download import delete_gnomad_chr, download_gnomad_chr

    mode = " (incremental)" if incremental else ""
    print(f"  [{step}/{total}] gnomAD population frequencies{mode}...")

    if is_update:
        patch.clear_layer("gnomad")

    patch.set_metadata("gnomad", "v4.1", status="pending")

    try:
        import pysam

        with pysam.VariantFile(str(vcf_path)) as vf:
            vcf_chroms = set(vf.header.contigs)

        total_rows = 0
        for i, chrom in enumerate(GNOMAD_CHROMS, 1):
            chr_name = f"chr{chrom}"
            if chr_name not in vcf_chroms:
                continue

            pre_existed = gnomad_chr_path(chrom).exists()

            if incremental:
                download_gnomad_chr(chrom)

            gnomad_file = gnomad_chr_path(chrom)
            if not gnomad_file.exists():
                continue

            print(f"    chr{chrom} ({i}/{len(GNOMAD_CHROMS)})...", end="", flush=True)
            proc = subprocess.Popen(
                [
                    "bcftools",
                    "annotate",
                    "-a",
                    str(gnomad_file),
                    "-c",
                    "INFO/AF,INFO/AF_grpmax",
                    "-r",
                    chr_name,
                    str(vcf_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                rows = patch.update_gnomad_from_stream(iter(proc.stdout))
                total_rows += rows
                rc = proc.wait()
                print(f" {rows:,} variants")
                if rc != 0:
                    stderr = proc.stderr.read() if proc.stderr else ""
                    raise RuntimeError(
                        f"bcftools annotate (gnomAD) failed with exit code {rc} "
                        f"on chr{chrom}: {stderr}"
                    )
            except Exception:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                raise
            finally:
                if proc.stdout is not None:
                    proc.stdout.close()
                if incremental and not pre_existed:
                    delete_gnomad_chr(chrom)
    except Exception:
        patch.set_metadata("gnomad", "v4.1", status="failed")
        raise

    patch.set_metadata("gnomad", "v4.1", status="complete")
    print(f"    {total_rows} variants updated")


def _annotate_dbsnp(patch, vcf_path: Path, step: int, total: int, is_update: bool):
    """Step 4: dbSNP rsID backfill.

    Runs bcftools annotate with the chr-fixed dbSNP VCF to fill rsIDs
    for variants that lack them (rsid IS NULL in patch.db).
    """
    from genechat.download import dbsnp_path

    dbsnp_vcf = dbsnp_path()
    print(f"  [{step}/{total}] dbSNP rsID backfill...")

    if is_update:
        patch.clear_layer("dbsnp")

    version = _dbsnp_version(dbsnp_vcf)
    patch.set_metadata("dbsnp", version or "unknown", status="pending")

    import tempfile

    proc = None
    try:
        with tempfile.SpooledTemporaryFile(
            max_size=64 * 1024, mode="w+"
        ) as stderr_file:
            proc = subprocess.Popen(
                [
                    "bcftools",
                    "annotate",
                    "-a",
                    str(dbsnp_vcf),
                    "-c",
                    "ID",
                    str(vcf_path),
                ],
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                text=True,
            )
            try:
                rows = patch.update_dbsnp_from_stream(iter(proc.stdout))
                rc = proc.wait()
                if rc != 0:
                    stderr_file.seek(0)
                    stderr_tail = stderr_file.read()[-500:]
                    raise RuntimeError(
                        f"bcftools annotate (dbSNP) failed with exit code {rc}:"
                        f" {stderr_tail}"
                    )
            finally:
                if proc.stdout is not None:
                    proc.stdout.close()
    except Exception:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        patch.set_metadata("dbsnp", version or "unknown", status="failed")
        raise

    patch.set_metadata("dbsnp", version or "unknown", status="complete")
    print(f"    {rows} variants updated")


def _dbsnp_version(dbsnp_vcf: Path) -> str | None:
    """Extract dbSNP build version from the ##dbSNP_BUILD_ID= header."""
    try:
        result = subprocess.run(
            ["bcftools", "view", "-h", str(dbsnp_vcf)],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("##dbSNP_BUILD_ID="):
                return "Build " + line.split("=", 1)[1].strip()
    except (subprocess.CalledProcessError, OSError):
        pass
    return None


def _print_annotation_status(patch_db_path: Path):
    """Print current annotation status for an existing patch.db."""
    from genechat.patch import PatchDB

    patch = PatchDB(patch_db_path, readonly=True)
    try:
        meta = patch.get_metadata()
    finally:
        patch.close()

    size_mb = patch_db_path.stat().st_size / 1024 / 1024
    print(f"Patch database: {patch_db_path} ({size_mb:.0f} MB)")
    for source in ["snpeff", "clinvar", "gnomad", "dbsnp"]:
        info = meta.get(source, {})
        if info:
            version = info.get("version", "?")
            date = info.get("updated_at", "?")
            status = info.get("status", "?")
            print(f"  {source:<10} {version:<20} ({date})  [{status}]")
        else:
            print(f"  {source:<10} not applied")

    print("\nUse --clinvar, --snpeff, --gnomad, --dbsnp, or --all to update.")


def _update_config_patch_db(patch_db_path: Path, label: str = "default"):
    """Update config.toml with the patch_db path if not already set."""
    import os
    import tomllib

    from genechat.config import _serialize_config

    config = load_config()
    genome_cfg = config.genomes.get(label)
    if genome_cfg and genome_cfg.patch_db:
        return  # Already set

    config_dir = Path(user_config_dir("genechat"))
    config_path = config_dir / "config.toml"
    if not config_path.exists():
        return

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    # Migrate legacy [genome] if present
    if "genome" in data and "genomes" not in data:
        data["genomes"] = {"default": data.pop("genome")}

    data.setdefault("genomes", {}).setdefault(label, {})["patch_db"] = str(
        patch_db_path
    )
    content = _serialize_config(data)

    # Atomic write with correct permissions
    tmp_path = config_path.with_suffix(".tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp_path, config_path)


# ---------------------------------------------------------------------------
# Contig auto-fix
# ---------------------------------------------------------------------------


def _detect_bare_contigs(vcf_path: Path) -> bool:
    """Check if a VCF uses bare contig names (1, 2, ...) instead of chr prefix."""
    import pysam

    bare_names = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
    with pysam.VariantFile(str(vcf_path)) as vf:
        for contig in vf.header.contigs:
            if contig in bare_names:
                return True
            if contig.startswith("chr"):
                return False
    return False


def _fix_user_contigs(vcf_path: Path) -> Path:
    """Rewrite a VCF with bare contig names to use chr prefix.

    Returns path to the fixed VCF (in same directory as original).
    """
    import tempfile

    stem = vcf_path.name
    if stem.endswith(".vcf.gz"):
        fixed_name = stem[:-7] + "_chrfixed.vcf.gz"
    else:
        fixed_name = stem + "_chrfixed.vcf.gz"
    fixed = vcf_path.parent / fixed_name

    # Write chr rename map
    chr_map = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            chr_map = Path(f.name)
            for i in range(1, 23):
                f.write(f"{i} chr{i}\n")
            f.write("X chrX\nY chrY\nMT chrMT\n")

        subprocess.run(
            [
                "bcftools",
                "annotate",
                "--rename-chrs",
                str(chr_map),
                str(vcf_path),
                "-Oz",
                "-o",
                str(fixed),
            ],
            check=True,
            capture_output=True,
        )

        # Index the fixed VCF
        import pysam

        pysam.tabix_index(str(fixed), preset="vcf", force=True)
    finally:
        if chr_map:
            chr_map.unlink(missing_ok=True)

    return fixed


# ---------------------------------------------------------------------------
# genechat init <vcf>
# ---------------------------------------------------------------------------


def _run_init(args):
    """Full first-time setup: add + download + annotate + configure."""
    vcf_path = Path(args.vcf_path).expanduser().resolve()
    label = args.label or "default"

    print("=== GeneChat Setup ===\n")

    # Step 1: Validate VCF
    print("Step 1: Validating VCF...")
    if not _validate_vcf(vcf_path):
        sys.exit(ExitCode.VCF_ERROR)

    # Step 2: Detect and fix bare contig names
    print("\nStep 2: Checking contig names...")
    if _detect_bare_contigs(vcf_path):
        if not shutil.which("bcftools"):
            print(
                f"{_red('Error:')} VCF uses bare contig names (1, 2, ...) but bcftools "
                "is needed to fix them.",
                file=sys.stderr,
            )
            print("  Install: brew install bcftools (macOS)", file=sys.stderr)
            sys.exit(ExitCode.TOOL_ERROR)
        print("  Bare contig names detected. Adding chr prefix...")
        vcf_path = _fix_user_contigs(vcf_path)
        print(f"  Fixed VCF: {vcf_path}")
    else:
        print("  Contig names: OK (chr prefix)")

    # Step 3: Register VCF
    print(f"\nStep 3: Registering VCF as '{label}'...")
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir, label=label)
    print(f"  Config: {config_path}")

    # Step 4: Ensure lookup_tables.db
    print("\nStep 4: Checking lookup database...")
    if not _ensure_lookup_db():
        sys.exit(ExitCode.CONFIG_ERROR)
    print("  lookup_tables.db: OK")

    # Step 5: Install GWAS if requested
    step = 5
    if args.gwas:
        print(f"\nStep {step}: Installing GWAS Catalog...")
        install_args = argparse.Namespace(gwas=True, force=False)
        _run_install(install_args)
        step += 1

    # Next step: Annotate (auto-downloads ClinVar, SnpEff DB, dbSNP, gnomAD as needed)
    print(f"\nStep {step}: Building annotation database...")
    ann_args = argparse.Namespace(
        clinvar=False,
        gnomad=args.gnomad,
        snpeff=False,
        dbsnp=args.dbsnp,
        all=False,
        genome=label,
    )
    _run_annotate(ann_args)

    # Step 7: Print MCP config
    print("\n--- MCP Configuration ---\n")
    project_dir = _find_project_root()
    if project_dir:
        mcp_config = {
            "mcpServers": {
                "genechat": {
                    "command": "uv",
                    "args": [
                        "run",
                        "--directory",
                        str(project_dir),
                        "genechat",
                    ],
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

    print("Add this to your Claude Desktop or Claude Code MCP config:\n")
    print(json.dumps(mcp_config, indent=2))
    if not args.gwas:
        print("\nOptional: Enable GWAS trait search:")
        print("  genechat install --gwas")
    print("\n=== Setup complete ===")


# ---------------------------------------------------------------------------
# genechat update [--apply]
# ---------------------------------------------------------------------------


def _is_version_stale(installed: str, latest: str) -> bool:
    """Check if installed version is older than latest.

    Only compares lexicographically when both look like ISO dates (YYYY-MM-DD).
    Non-date strings like 'unknown' or 'GRCh38.p14' are always treated as stale.
    """
    import re

    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if date_re.match(latest) and date_re.match(installed):
        return latest > installed
    # Non-date installed version — treat as stale
    return True


def _run_update(args):
    """Check for newer reference versions, optionally apply updates."""
    # Handle --seeds: rebuild seed data from APIs
    if args.seeds:
        _run_update_seeds()
        return

    from genechat.update import check_all_versions, format_status_table

    config = load_config()
    genome_arg = getattr(args, "genome", None)

    # update can work without a genome registered (just shows latest versions)
    label = None
    genome_cfg = None
    if config.genomes:
        label, genome_cfg = _resolve_genome_label(config, genome_arg)

    patch_db_str = genome_cfg.patch_db if genome_cfg else ""
    installed: dict[str, dict] = {}

    if patch_db_str and Path(patch_db_str).exists():
        from genechat.patch import PatchDB

        patch = PatchDB(Path(patch_db_str), readonly=True)
        try:
            installed = patch.get_metadata()
        finally:
            patch.close()

    latest = check_all_versions()
    print()
    print(format_status_table(installed, latest))

    if args.apply:
        if not label:
            print(
                f"{_red('Error:')} No genome registered. Run: genechat add <vcf>",
                file=sys.stderr,
            )
            sys.exit(ExitCode.CONFIG_ERROR)

        # Determine which sources need updating
        stale = []
        for source in ["clinvar"]:
            meta = installed.get(source, {})
            inst_ver = meta.get("version", "")
            latest_ver = latest.get(source)
            if latest_ver and (not inst_ver or _is_version_stale(inst_ver, latest_ver)):
                stale.append(source)

        if not stale:
            print("\nAll installed sources are up to date.")
            return

        print(f"\nUpdating: {', '.join(stale)}")
        from genechat.download import download_clinvar

        for source in stale:
            if source == "clinvar":
                download_clinvar(force=True)

        # Re-annotate stale layers
        ann_args = argparse.Namespace(
            clinvar="clinvar" in stale,
            gnomad=False,
            snpeff=False,
            dbsnp=False,
            all=False,
            genome=label,
        )
        _run_annotate(ann_args)
    else:
        print("\nApply updates with: genechat update --apply")


# ---------------------------------------------------------------------------
# genechat status
# ---------------------------------------------------------------------------


def _run_status(json_output: bool = False):
    """Show genome info, annotation state, reference versions."""
    config = load_config()

    if json_output:
        _run_status_json(config)
        return

    if not config.genomes:
        print("No genome registered. Run: genechat init <vcf>")
        return

    print("=== Registered Genomes ===\n")

    any_gnomad_annotated = False
    for label, genome_cfg in config.genomes.items():
        is_default = label == config.default_genome
        suffix = " (primary)" if is_default else ""
        print(f"[{label}]{suffix}")

        vcf_path_str = genome_cfg.vcf_path
        if not vcf_path_str:
            print("  VCF: not configured\n")
            continue

        vcf_path = Path(vcf_path_str)
        vcf_exists = vcf_path.exists()
        vcf_status = _green("exists") if vcf_exists else _red("NOT FOUND")
        print(f"  VCF: {_dim(str(vcf_path))} ({vcf_status})")

        # Patch DB status
        patch_db_str = genome_cfg.patch_db
        if patch_db_str and Path(patch_db_str).exists():
            patch_db_path = Path(patch_db_str)
            size_mb = patch_db_path.stat().st_size / 1024 / 1024
            print(f"  Patch DB: {_dim(str(patch_db_path))} ({size_mb:.0f} MB)")

            from genechat.patch import PatchDB

            patch = PatchDB(patch_db_path, readonly=True)
            try:
                meta = patch.get_metadata()
            finally:
                patch.close()

            if meta.get("gnomad", {}).get("status") == "complete":
                any_gnomad_annotated = True

            print("  Annotations:")
            for source in ["snpeff", "clinvar", "gnomad", "dbsnp"]:
                info = meta.get(source, {})
                if info:
                    status = info.get("status", "unknown")
                    version = info.get("version", "?")
                    date = info.get("updated_at", "?")
                    if status == "complete":
                        print(f"    {source:<10} {version:<20} (applied {date})")
                    elif status == "pending":
                        print(
                            f"    {source:<10} {version:<20} ({_yellow('in progress')})"
                        )
                    elif status == "failed":
                        print(f"    {source:<10} {version:<20} ({_red('FAILED')})")
                    else:
                        print(f"    {source:<10} {version:<20} ({status})")
                else:
                    print(f"    {source:<10} not applied")
        else:
            print("  Patch DB: not built")
            print(
                "  Run: genechat annotate"
                + (f" --genome {label}" if not is_default else "")
            )
        print()

    # References status
    from genechat.download import (
        clinvar_installed,
        dbsnp_installed,
        gnomad_installed,
        references_dir,
        snpeff_installed,
    )

    print(f"References: {_dim(str(references_dir()))}")
    print(
        f"  ClinVar:  {'installed' if clinvar_installed() else 'not installed — genechat annotate'}"
    )
    print(
        f"  SnpEff:   {'available' if snpeff_installed() else 'not installed — brew install brewsci/bio/snpeff'}"
    )
    gnomad_files = gnomad_installed()
    if gnomad_files:
        gnomad_status = "installed"
    elif any_gnomad_annotated:
        gnomad_status = "annotated (reference files cleaned up)"
    else:
        gnomad_status = "not installed — genechat annotate --gnomad"
    print(f"  gnomAD:   {gnomad_status}")
    print(
        f"  dbSNP:    {'installed' if dbsnp_installed() else 'not installed — genechat annotate --dbsnp'}"
    )

    gwas_ok = False
    gwas_path = Path(config.gwas_db_path)
    if gwas_path.exists():
        import sqlite3 as _sql

        try:
            with _sql.connect(str(gwas_path)) as _c:
                _r = _c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='gwas_associations'"
                ).fetchone()
                gwas_ok = _r is not None
        except _sql.Error:
            pass
    print(
        f"  GWAS:     {'installed' if gwas_ok else 'not installed — genechat install --gwas'}"
    )

    print("\nRun `genechat update` to check for newer versions.")


def _run_status_json(config):
    """Output status as JSON."""
    from genechat.download import (
        clinvar_installed,
        dbsnp_installed,
        gnomad_installed,
        references_dir,
        snpeff_installed,
    )

    data: dict = {"genomes": {}, "references": {}}

    for label, genome_cfg in config.genomes.items():
        genome_info: dict = {
            "vcf_path": genome_cfg.vcf_path or None,
            "vcf_exists": bool(
                genome_cfg.vcf_path and Path(genome_cfg.vcf_path).exists()
            ),
            "is_primary": label == config.default_genome,
            "patch_db": None,
            "annotations": {},
        }

        patch_db_str = genome_cfg.patch_db
        if patch_db_str and Path(patch_db_str).exists():
            patch_db_path = Path(patch_db_str)
            genome_info["patch_db"] = str(patch_db_path)

            from genechat.patch import PatchDB

            patch = PatchDB(patch_db_path, readonly=True)
            try:
                meta = patch.get_metadata()
            finally:
                patch.close()

            for source in ["snpeff", "clinvar", "gnomad", "dbsnp"]:
                info = meta.get(source, {})
                if info:
                    genome_info["annotations"][source] = {
                        "status": info.get("status"),
                        "version": info.get("version"),
                        "updated_at": info.get("updated_at"),
                    }

        data["genomes"][label] = genome_info

    data["references"] = {
        "directory": str(references_dir()),
        "clinvar": clinvar_installed(),
        "snpeff": snpeff_installed(),
        "gnomad": gnomad_installed(),
        "dbsnp": dbsnp_installed(),
    }

    gwas_ok = False
    gwas_path = Path(config.gwas_db_path)
    if gwas_path.exists():
        import sqlite3 as _sql

        try:
            with _sql.connect(str(gwas_path)) as _c:
                _r = _c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='gwas_associations'"
                ).fetchone()
                gwas_ok = _r is not None
        except _sql.Error:
            pass
    data["references"]["gwas"] = gwas_ok

    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# genechat update --seeds
# ---------------------------------------------------------------------------


def _run_update_seeds():
    """Fetch latest seed data from APIs and rebuild lookup_tables.db."""
    project_root = _find_project_root()
    if not project_root:
        print(
            f"{_red('Error:')} --seeds requires a source checkout (pyproject.toml not found).",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CONFIG_ERROR)

    build_script = project_root / "scripts" / "build_seed_data.py"
    if not build_script.exists():
        print(
            f"{_red('Error:')} build_seed_data.py not found at {build_script}",
            file=sys.stderr,
        )
        sys.exit(ExitCode.CONFIG_ERROR)

    print("Updating seed data from upstream APIs...")
    result = subprocess.run(
        [sys.executable, str(build_script)],
        cwd=str(project_root),
    )
    if result.returncode != 0:
        print(f"{_red('Error:')} Seed data update failed.", file=sys.stderr)
        sys.exit(ExitCode.GENERAL_ERROR)


# ---------------------------------------------------------------------------
# genechat install --gwas
# ---------------------------------------------------------------------------


def _download_and_build_gwas(force: bool = False):
    """Download GWAS Catalog and build a standalone gwas.db."""
    from genechat.gwas import build_gwas_db, download_gwas_catalog

    if force:
        download_gwas_catalog()

    print("Building GWAS Catalog database...")
    build_gwas_db()
