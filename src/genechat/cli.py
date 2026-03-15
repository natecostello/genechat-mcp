"""CLI entry point for GeneChat — dispatches subcommands.

Commands:
  genechat init <vcf>           Full first-time setup (add + annotate)
  genechat add <vcf>            Register a VCF file
  genechat annotate [options]   Build/update patch.db (auto-downloads references)
  genechat install [options]    Install genome-independent reference databases
  genechat status               Show genome + annotation state
  genechat licenses             Show data source licenses for your installation
  genechat serve / genechat     Start the MCP server
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
from enum import IntEnum
from pathlib import Path
from typing import Annotated

import click.exceptions
import typer
from platformdirs import user_config_dir
from rich import print as rprint

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
# Typer app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="genechat",
    help="GeneChat MCP server for conversational personal genomics",
    epilog=(
        "Docs:   https://github.com/natecostello/genechat-mcp#readme\n"
        "Issues: https://github.com/natecostello/genechat-mcp/issues"
    ),
    no_args_is_help=False,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Concise help text for interactive use with no subcommand
# ---------------------------------------------------------------------------

_INTERACTIVE_HELP = """\
GeneChat — MCP server for conversational personal genomics

Commands:
  genechat init <vcf>       Full first-time setup (register + annotate)
  genechat add <vcf>        Register a VCF file
  genechat annotate         Build/update annotation database
  genechat install          Install genome-independent databases (GWAS, seeds)
  genechat status           Show genome info and annotation state
  genechat licenses         Show data source licenses for your installation
  genechat serve            Start the MCP server

Quick start:
  genechat init /path/to/your/raw.vcf.gz

Run 'genechat <command> --help' for details on each command.

Docs:  https://github.com/natecostello/genechat-mcp#readme
Issues: https://github.com/natecostello/genechat-mcp/issues
"""


# ---------------------------------------------------------------------------
# Dynamic completion for --genome
# ---------------------------------------------------------------------------


def _genome_completer(incomplete: str) -> list[str]:
    """Dynamic completion for --genome: returns matching genome labels."""
    try:
        config = load_config()
        return [label for label in config.genomes if label.startswith(incomplete)]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Typer callback (global flags + no-subcommand behavior)
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", help="Show version and exit")
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable color output")
    ] = False,
):
    if version:
        print(f"genechat {__version__}")
        raise typer.Exit()
    if no_color:
        os.environ["NO_COLOR"] = "1"
    if ctx.invoked_subcommand is None:
        if getattr(sys.stdin, "isatty", lambda: False)():
            print(_INTERACTIVE_HELP, end="")
            raise typer.Exit()
        else:
            _run_serve()


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


@app.command()
def serve():
    """Start the MCP server."""
    _run_serve()


@app.command()
def add(
    vcf_path: Annotated[str, typer.Argument(help="Path to your VCF (.vcf.gz)")],
    label: Annotated[str | None, typer.Option(help="Name for this genome")] = None,
):
    """Register a VCF file."""
    _run_add(vcf_path, label)


@app.command()
def install(
    gwas: Annotated[
        bool, typer.Option("--gwas", help="Install GWAS Catalog (~58 MB download)")
    ] = False,
    seeds: Annotated[
        bool,
        typer.Option(
            "--seeds",
            help="Refresh seed data (PGx, gene coords, PRS) from upstream APIs",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Re-download source files even if already present (DB is always rebuilt)",
        ),
    ] = False,
):
    """Install genome-independent reference databases."""
    _run_install(gwas=gwas, seeds=seeds, force=force)


@app.command()
def annotate(
    clinvar: Annotated[
        bool, typer.Option("--clinvar", help="Re-annotate ClinVar layer")
    ] = False,
    gnomad: Annotated[
        bool,
        typer.Option(
            "--gnomad",
            help="Re-annotate gnomAD layer (downloads incrementally if not present)",
        ),
    ] = False,
    snpeff: Annotated[
        bool, typer.Option("--snpeff", help="Re-annotate SnpEff layer")
    ] = False,
    dbsnp: Annotated[
        bool, typer.Option("--dbsnp", help="Re-annotate dbSNP layer")
    ] = False,
    all_layers: Annotated[
        bool, typer.Option("--all", help="Re-annotate all layers")
    ] = False,
    stale: Annotated[
        bool,
        typer.Option(
            "--stale",
            help="Re-annotate layers with newer references available (requires network)",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Override guards (e.g. skip rsID probe for dbSNP)"
        ),
    ] = False,
    fast: Annotated[
        bool,
        typer.Option(
            "--fast", help="Bulk-download mode: ~20x faster, ~180 GB peak disk"
        ),
    ] = False,
    genome: Annotated[
        str | None,
        typer.Option(help="Which genome to annotate", autocompletion=_genome_completer),
    ] = None,
):
    """Build or update the annotation database (patch.db)."""
    _run_annotate(
        clinvar=clinvar,
        gnomad=gnomad,
        snpeff=snpeff,
        dbsnp=dbsnp,
        all_layers=all_layers,
        stale=stale,
        force=force,
        fast=fast,
        genome=genome,
    )


@app.command()
def status(
    json_output: Annotated[
        bool, typer.Option("--json", help="Output status as JSON")
    ] = False,
    check_updates: Annotated[
        bool,
        typer.Option(
            "--check-updates",
            help="Check for newer reference versions (requires network)",
        ),
    ] = False,
):
    """Show genome info and annotation state."""
    _run_status(json_output=json_output, check_updates=check_updates)


@app.command()
def licenses():
    """Show data source licenses for your installation."""
    _run_licenses()


@app.command()
def init(
    vcf_path: Annotated[str, typer.Argument(help="Path to your raw VCF (.vcf.gz)")],
    label: Annotated[str | None, typer.Option(help="Name for this genome")] = None,
    gnomad: Annotated[
        bool,
        typer.Option(
            "--gnomad",
            help="Also annotate gnomAD population frequencies (~17 GB peak disk, ~150 GB with --fast)",
        ),
    ] = False,
    dbsnp: Annotated[
        bool,
        typer.Option(
            "--dbsnp", help="Also download dbSNP (~20 GB, ~48 GB with --fast)"
        ),
    ] = False,
    gwas: Annotated[
        bool, typer.Option("--gwas", help="Also download GWAS Catalog (~58 MB)")
    ] = False,
    fast: Annotated[
        bool,
        typer.Option(
            "--fast", help="Bulk-download mode: ~20x faster, ~180 GB peak disk"
        ),
    ] = False,
):
    """Full first-time setup for a VCF file."""
    _run_init(
        vcf_path=vcf_path,
        label=label,
        gnomad=gnomad,
        dbsnp=dbsnp,
        gwas=gwas,
        fast=fast,
    )


# ---------------------------------------------------------------------------
# main() wrapper
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None):
    try:
        rv = app(argv, standalone_mode=False)
        # standalone_mode=False returns exit codes instead of calling sys.exit().
        # Typer's __call__ catches click.Abort (from KeyboardInterrupt) internally
        # and returns 130 before our except handlers can fire.
        if rv:
            if rv == 130:
                print("\nInterrupted.", file=sys.stderr)
            sys.exit(rv)
    except click.exceptions.Exit as e:
        sys.exit(e.exit_code)
    except click.Abort:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except BrokenPipeError:
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        rprint(f"\n[red]Unexpected error:[/red] {exc}", file=sys.stderr)
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

    Checks user data dir first (rebuilt DB), then package-bundled copy.
    Returns True if DB is available, False if not.
    """
    from importlib import resources

    from genechat.config import _user_db_path

    # Check user-rebuilt copy first
    if _user_db_path().is_file():
        return True

    # Check package-bundled copy
    data_dir_ref = resources.files("genechat") / "data"
    with resources.as_file(data_dir_ref) as data_dir:
        db_path = data_dir / "lookup_tables.db"
        if db_path.exists():
            return True

        project_root = _find_project_root()
        seed_dir = project_root / "data" / "seed" if project_root else None

        if seed_dir and seed_dir.exists():
            try:
                from genechat.seeds.build_db import build_db

                print("Building lookup_tables.db from seed data...")
                build_db(seed_dir=seed_dir, db_path=db_path)
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
        rprint(
            f"[red]Error:[/red] VCF file not found: [dim]{vcf_path}[/dim]",
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
        raise typer.Exit(code=ExitCode.VCF_ERROR)

    # Write config
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir, label=label or "")
    genome_label = label or "default"
    print(f"VCF registered as '{genome_label}'. Config: {config_path}")
    return config_path


# ---------------------------------------------------------------------------
# genechat install [options]
# ---------------------------------------------------------------------------


def _run_install(gwas: bool = False, seeds: bool = False, force: bool = False):
    """Install genome-independent reference databases."""
    from genechat.gwas import gwas_db_path

    print(f"Data directory: {gwas_db_path().parent}\n")

    if not gwas and not seeds:
        print("Available databases:")
        print(
            "  --gwas    GWAS Catalog associations (~58 MB download, ~300 MB on disk)"
        )
        print(
            "  --seeds   Seed data (PGx guidelines, gene coords, PRS weights) from APIs"
        )
        print("\nRun: genechat install --gwas")
        return

    if gwas:
        from genechat.gwas import gwas_installed

        if gwas_installed() and not force:
            print("GWAS Catalog already installed. Use --force to rebuild.")
        else:
            _download_and_build_gwas(force=force)

    if seeds:
        _run_update_seeds()

    print("\nInstall complete.")


# ---------------------------------------------------------------------------
# genechat annotate [options]
# ---------------------------------------------------------------------------


def _resolve_genome_label(config, genome_arg: str | None) -> tuple[str, object]:
    """Resolve a --genome arg to (label, GenomeConfig). Exits on error.

    When only one genome is registered, genome_arg may be None and defaults
    to the only available genome.  When multiple genomes are registered,
    genome_arg is required — omitting it prints available genomes and exits.
    """
    if not config.genomes:
        rprint(
            "[red]Error:[/red] No VCF registered. Run: genechat add <vcf>",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    if genome_arg is None:
        if len(config.genomes) == 1:
            label = next(iter(config.genomes))
        else:
            available = "\n".join(f"  {k}" for k in config.genomes)
            print(
                "Usage: genechat annotate --genome <label> "
                "[--clinvar | --snpeff | --gnomad | --dbsnp | --all]"
            )
            print(f"\nAvailable genomes:\n{available}")
            print("\nRun 'genechat status' to see current annotation state.")
            raise typer.Exit(code=ExitCode.USAGE_ERROR)
    else:
        label = genome_arg

    if label not in config.genomes:
        available = ", ".join(config.genomes.keys())
        rprint(
            f"[red]Error:[/red] Unknown genome '{label}'. Available: {available}",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    return label, config.genomes[label]


def _resolve_stale_layers(
    genome_cfg, clinvar: bool, gnomad: bool, snpeff: bool, dbsnp: bool
) -> tuple[bool, bool, bool, bool]:
    """Check for newer reference versions and enable stale layers.

    Returns updated (clinvar, gnomad, snpeff, dbsnp) flags with stale
    layers set to True.
    """
    from genechat.patch import PatchDB
    from genechat.update import _is_newer, check_all_versions

    vcf_path = Path(genome_cfg.vcf_path) if genome_cfg.vcf_path else None
    if not vcf_path:
        return clinvar, gnomad, snpeff, dbsnp

    patch_db_path = _patch_db_path_for(vcf_path, genome_cfg)
    if not patch_db_path.exists():
        return clinvar, gnomad, snpeff, dbsnp

    patch = PatchDB(patch_db_path, readonly=True)
    try:
        meta = patch.get_metadata()
    finally:
        patch.close()

    latest = check_all_versions()
    stale_layers = []
    any_checked = False

    for source, latest_ver in latest.items():
        if latest_ver is None:
            continue
        info = meta.get(source, {})
        installed_ver = info.get("version")
        if not installed_ver:
            continue
        any_checked = True
        if _is_newer(latest_ver, installed_ver):
            stale_layers.append(source)

    if stale_layers:
        print(f"Stale layers detected: {', '.join(stale_layers)}")
        for layer in stale_layers:
            if layer == "clinvar":
                clinvar = True
            elif layer == "gnomad":
                gnomad = True
            elif layer == "snpeff":
                snpeff = True
            elif layer == "dbsnp":
                dbsnp = True
    elif any_checked:
        print("All checkable layers are up to date.")
    else:
        print("Could not check for updates (version checks returned no data).")

    return clinvar, gnomad, snpeff, dbsnp


def _run_annotate(
    clinvar: bool = False,
    gnomad: bool = False,
    snpeff: bool = False,
    dbsnp: bool = False,
    all_layers: bool = False,
    stale: bool = False,
    force: bool = False,
    fast: bool = False,
    genome: str | None = None,
):
    """Build or update patch.db for the registered VCF."""
    config = load_config()
    label, genome_cfg = _resolve_genome_label(config, genome)

    # --stale: check for newer versions and enable stale layers
    if stale:
        clinvar, gnomad, snpeff, dbsnp = _resolve_stale_layers(
            genome_cfg, clinvar, gnomad, snpeff, dbsnp
        )

    # Check for action flags early — before VCF validation
    any_flag = clinvar or gnomad or snpeff or dbsnp or all_layers

    vcf_path_str = genome_cfg.vcf_path
    if not vcf_path_str:
        rprint(
            f"[red]Error:[/red] Genome '{label}' has no vcf_path. Run: genechat add <vcf>",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)

    vcf_path = Path(vcf_path_str)

    # Determine patch.db path
    patch_db_path = _patch_db_path_for(vcf_path, genome_cfg)
    first_run = not patch_db_path.exists()

    if not any_flag and not first_run:
        # No action flags and patch.db already exists → show usage guidance
        genome_labels = list(config.genomes)
        if len(genome_labels) == 1:
            # Single-genome config: --genome is optional
            print(
                "Usage: genechat annotate "
                "[--clinvar | --snpeff | --gnomad | --dbsnp | --all]"
            )
            print(
                f"\nOnly one genome is registered (no --genome needed):"
                f"\n  {genome_labels[0]}"
            )
        else:
            # Multi-genome config: require explicit --genome <label>
            available = "\n".join(f"  {k}" for k in genome_labels)
            print(
                "Usage: genechat annotate --genome <label> "
                "[--clinvar | --snpeff | --gnomad | --dbsnp | --all]"
            )
            print(f"\nAvailable genomes:\n{available}")
        print("\nRun 'genechat status' to see current annotation state.")
        return

    if not vcf_path.exists():
        rprint(
            f"[red]Error:[/red] VCF not found: [dim]{vcf_path}[/dim]",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.VCF_ERROR)

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

    # On first run or --all, run everything available
    run_snpeff = first_run or snpeff or all_layers
    run_clinvar = first_run or clinvar or all_layers
    # gnomAD/dbSNP: run when explicitly requested, or on first run if already available
    run_gnomad = gnomad or all_layers or (first_run and gnomad_installed())
    run_dbsnp = dbsnp or all_layers or (first_run and dbsnp_installed())

    # Check tool prerequisites (can't auto-install system packages)
    if run_snpeff and not snpeff_installed():
        rprint(
            "[red]Error:[/red] snpEff not found in PATH. Required for functional annotation.",
            file=sys.stderr,
        )
        print("  Install: brew install brewsci/bio/snpeff (macOS)", file=sys.stderr)
        raise typer.Exit(code=ExitCode.TOOL_ERROR)

    if not shutil.which("bcftools"):
        rprint("[red]Error:[/red] bcftools not found in PATH.", file=sys.stderr)
        print("  Install: brew install bcftools (macOS)", file=sys.stderr)
        raise typer.Exit(code=ExitCode.TOOL_ERROR)

    needs_tabix = run_clinvar or (run_dbsnp and not dbsnp_installed())
    if needs_tabix and not shutil.which("tabix"):
        rprint(
            "[red]Error:[/red] tabix not found in PATH (needed for contig rename).",
            file=sys.stderr,
        )
        print("  Install: brew install htslib (macOS)", file=sys.stderr)
        raise typer.Exit(code=ExitCode.TOOL_ERROR)

    # rsID probe guard: skip dbSNP download if VCF already has rsIDs
    # (only when patch.db exists — first_run has no annotations to probe)
    if run_dbsnp and not first_run:
        probe_patch = PatchDB(patch_db_path, readonly=True)
        try:
            total_ann, has_rsid = probe_patch.rsid_coverage()
        finally:
            probe_patch.close()
        if total_ann > 0 and not force:
            coverage = has_rsid / total_ann
            if coverage > 0.9:
                print(
                    f"  Skipping dbSNP: {coverage:.0%} of variants already have "
                    f"rsIDs ({has_rsid:,}/{total_ann:,}). Use --force to override."
                )
                run_dbsnp = False

    # Fast mode: pre-download all gnomAD chromosomes so annotation is non-incremental
    if fast and run_gnomad and not gnomad_installed():
        from genechat.download import download_gnomad

        print("  Pre-downloading all gnomAD chromosomes (fast mode)...")
        download_gnomad()

    gnomad_incremental = run_gnomad and not gnomad_installed()

    # Auto-download references if not present
    if run_clinvar and not clinvar_installed():
        print("  Downloading ClinVar reference...")
        download_clinvar()

    if run_snpeff:
        if download_snpeff_db() is None:
            rprint(
                "[red]Error:[/red] SnpEff database download failed.", file=sys.stderr
            )
            raise typer.Exit(code=ExitCode.NETWORK_ERROR)

    if run_dbsnp and not dbsnp_installed():
        print("  Downloading dbSNP reference...")
        result = download_dbsnp(fast=fast)
        if result is None:
            rprint(
                "[red]Error:[/red] dbSNP download/processing failed.", file=sys.stderr
            )
            raise typer.Exit(code=ExitCode.NETWORK_ERROR)

    import time

    from genechat.progress import format_elapsed, format_size

    # Create or open patch.db
    if first_run:
        patch = PatchDB.create(patch_db_path)
        print(f"Building patch.db for {vcf_path.name}...")
    else:
        patch = PatchDB(patch_db_path)
        print(f"Updating patch.db for {vcf_path.name}...")

    step = 0
    total_steps = sum([run_snpeff, run_clinvar, run_gnomad, run_dbsnp])
    overall_start = time.monotonic()

    # Detect bare contigs — create rename map if annotation steps need it
    chr_rename_map = None
    if _detect_bare_contigs(vcf_path):
        import tempfile as _tf

        chr_rename_map = Path(_tf.mktemp(suffix=".txt", prefix="genechat_chr_"))
        _write_bare_to_chr_map(chr_rename_map)
        print("  VCF uses bare contig names — will rename to chr prefix for annotation")

    try:
        if run_snpeff:
            step += 1
            _annotate_snpeff(patch, vcf_path, step, total_steps, not first_run)

        if run_clinvar:
            step += 1
            _annotate_clinvar(
                patch, vcf_path, step, total_steps, not first_run,
                chr_rename_map=chr_rename_map,
            )

        if run_gnomad:
            step += 1
            _annotate_gnomad(
                patch,
                vcf_path,
                step,
                total_steps,
                not first_run,
                incremental=gnomad_incremental,
                chr_rename_map=chr_rename_map,
            )

        if run_dbsnp:
            step += 1
            _annotate_dbsnp(
                patch, vcf_path, step, total_steps, not first_run,
                chr_rename_map=chr_rename_map,
            )

        # Store VCF fingerprint
        patch.store_vcf_fingerprint(vcf_path)

        # Update config with patch_db path
        _update_config_patch_db(patch_db_path, label)

    finally:
        patch.close()
        if chr_rename_map:
            chr_rename_map.unlink(missing_ok=True)

    elapsed = format_elapsed(time.monotonic() - overall_start)
    db_size = format_size(patch_db_path.stat().st_size)
    print(
        f"\nAnnotation complete ({elapsed}). Patch database: {patch_db_path} ({db_size})"
    )


def _patch_db_path_for(vcf_path: Path, genome_cfg) -> Path:
    """Determine the patch.db path for a VCF."""
    from genechat.config import GenomeConfig

    if isinstance(genome_cfg, GenomeConfig) and genome_cfg.patch_db:
        return Path(genome_cfg.patch_db)
    # Convention: same directory as VCF, <stem>.patch.db
    return vcf_path.parent / f"{vcf_path.stem.replace('.vcf', '')}.patch.db"



def _write_bare_to_chr_map(map_path: Path) -> Path:
    """Write a contig rename map: bare names -> chr-prefixed.

    Returns map_path for convenience.
    """
    with open(map_path, "w") as f:
        for i in range(1, 23):
            f.write(f"{i} chr{i}\n")
        f.write("X chrX\nY chrY\nMT chrMT\nM chrM\n")
    return map_path


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
    import time

    from genechat.download import _detect_snpeff_db
    from genechat.progress import ProgressLine, format_elapsed

    db_name = _detect_snpeff_db()
    print(f"  [{step}/{total}] SnpEff functional annotation ({db_name})...")

    if is_update:
        patch.clear_layer("snpeff")

    patch.set_metadata("snpeff", db_name, status="pending")
    step_start = time.monotonic()

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
            progress = ProgressLine(f"    {chrom} ({i}/{len(chroms)})")
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

            rows = patch.populate_from_snpeff_stream(
                iter(snpeff_proc.stdout),
                progress_callback=lambda n: progress.update(n),
            )
            total_rows += rows
            snpeff_rc = snpeff_proc.wait()
            bcf_rc = bcf_proc.wait()
            progress.done(f"{rows:,} variants")
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

    elapsed = format_elapsed(time.monotonic() - step_start)
    patch.set_metadata("snpeff", db_name, status="complete")
    print(f"    SnpEff complete: {total_rows:,} variants ({elapsed})")


def _annotate_clinvar(
    patch, vcf_path: Path, step: int, total: int, is_update: bool,
    chr_rename_map: Path | None = None,
):
    """Step 2: ClinVar clinical significance."""
    from genechat.download import clinvar_path
    from genechat.progress import ProgressLine

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

    rename_proc = None
    try:
        clinvar_use = _contig_rename_clinvar(clinvar_vcf, work_dir)

        progress = ProgressLine("    ClinVar")
        if chr_rename_map:
            # User VCF has bare contigs — pipe through rename to match ClinVar
            rename_proc = subprocess.Popen(
                ["bcftools", "annotate", "--rename-chrs", str(chr_rename_map),
                 str(vcf_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            proc = subprocess.Popen(
                ["bcftools", "annotate", "-a", str(clinvar_use),
                 "-c", "INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT", "-"],
                stdin=rename_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            rename_proc.stdout.close()
        else:
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
        rows = patch.update_clinvar_from_stream(
            iter(proc.stdout),
            progress_callback=lambda n: progress.update(n),
        )
        rc = proc.wait()
        if rename_proc:
            rename_rc = rename_proc.wait()
            if rename_rc != 0:
                raise RuntimeError(
                    f"bcftools annotate --rename-chrs failed with exit code {rename_rc}"
                )
        if rc != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(
                f"bcftools annotate (ClinVar) failed with exit code {rc}: {stderr}"
            )
    except Exception:
        if rename_proc and rename_proc.poll() is None:
            rename_proc.terminate()
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
    progress.done(f"{rows:,} variants updated")


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
    chr_rename_map: Path | None = None,
):
    """Step 3: gnomAD population frequencies (per-chromosome).

    When incremental=True, downloads each chromosome before annotating it
    and deletes the file afterward to minimize peak disk usage (~17 GB
    instead of ~150 GB).

    When chr_rename_map is provided, the user VCF has bare contigs and
    needs to be piped through bcftools --rename-chrs to match gnomAD's
    chr-prefixed contigs.
    """
    from genechat.download import GNOMAD_CHROMS, gnomad_chr_path

    if incremental:
        from genechat.download import delete_gnomad_chr, download_gnomad_chr

    import time

    from genechat.progress import ProgressLine, format_elapsed

    mode = " (incremental)" if incremental else ""
    print(f"  [{step}/{total}] gnomAD population frequencies{mode}...")

    if is_update:
        patch.clear_layer("gnomad")

    patch.set_metadata("gnomad", "v4.1", status="pending")
    step_start = time.monotonic()

    try:
        import pysam

        with pysam.VariantFile(str(vcf_path)) as vf:
            vcf_chroms = set(vf.header.contigs)

        total_rows = 0
        for i, chrom in enumerate(GNOMAD_CHROMS, 1):
            chr_name = f"chr{chrom}"
            # For bare-contig VCFs, check the bare chrom name
            vcf_chrom = chrom if chr_rename_map else chr_name
            if vcf_chrom not in vcf_chroms:
                continue

            pre_existed = gnomad_chr_path(chrom).exists()

            if incremental:
                download_gnomad_chr(chrom)

            gnomad_file = gnomad_chr_path(chrom)
            if not gnomad_file.exists():
                continue

            progress = ProgressLine(f"    chr{chrom} ({i}/{len(GNOMAD_CHROMS)})")
            rename_proc = None
            if chr_rename_map:
                # Pipe user VCF through rename: bare -> chr-prefixed
                rename_proc = subprocess.Popen(
                    ["bcftools", "annotate", "--rename-chrs",
                     str(chr_rename_map), "-r", chrom, str(vcf_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                proc = subprocess.Popen(
                    ["bcftools", "annotate", "-a", str(gnomad_file),
                     "-c", "INFO/AF,INFO/AF_grpmax", "-"],
                    stdin=rename_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                rename_proc.stdout.close()
            else:
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
                rows = patch.update_gnomad_from_stream(
                    iter(proc.stdout),
                    progress_callback=lambda n: progress.update(n),
                )
                total_rows += rows
                rc = proc.wait()
                if rename_proc:
                    rename_rc = rename_proc.wait()
                    if rename_rc != 0:
                        raise RuntimeError(
                            f"bcftools annotate --rename-chrs failed with "
                            f"exit code {rename_rc} on chr{chrom}"
                        )
                progress.done(f"{rows:,} variants")
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
                if rename_proc and rename_proc.poll() is None:
                    rename_proc.terminate()
                raise
            finally:
                if proc.stdout is not None:
                    proc.stdout.close()
                if incremental and not pre_existed:
                    delete_gnomad_chr(chrom)
    except Exception:
        patch.set_metadata("gnomad", "v4.1", status="failed")
        raise

    elapsed = format_elapsed(time.monotonic() - step_start)
    patch.set_metadata("gnomad", "v4.1", status="complete")
    print(f"    gnomAD complete: {total_rows:,} variants ({elapsed})")


def _annotate_dbsnp(
    patch, vcf_path: Path, step: int, total: int, is_update: bool,
    chr_rename_map: Path | None = None,
):
    """Step 4: dbSNP rsID backfill.

    Runs bcftools annotate with the chr-fixed dbSNP VCF to fill rsIDs
    for variants that lack them (rsid IS NULL in patch.db).

    When chr_rename_map is provided, the user VCF has bare contigs and
    needs to be piped through bcftools --rename-chrs to match dbSNP's
    chr-prefixed contigs.
    """
    from genechat.download import dbsnp_path
    from genechat.progress import ProgressLine

    dbsnp_vcf = dbsnp_path()
    print(f"  [{step}/{total}] dbSNP rsID backfill...")

    if is_update:
        patch.clear_layer("dbsnp")

    version = _dbsnp_version(dbsnp_vcf)
    patch.set_metadata("dbsnp", version or "unknown", status="pending")

    import tempfile

    progress = ProgressLine("    dbSNP", report_interval=15.0)
    proc = None
    rename_proc = None
    try:
        with tempfile.SpooledTemporaryFile(
            max_size=64 * 1024, mode="w+"
        ) as stderr_file:
            if chr_rename_map:
                # User VCF has bare contigs — pipe through rename to match dbSNP
                rename_proc = subprocess.Popen(
                    ["bcftools", "annotate", "--rename-chrs",
                     str(chr_rename_map), str(vcf_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                proc = subprocess.Popen(
                    ["bcftools", "annotate", "-a", str(dbsnp_vcf),
                     "-c", "ID", "-"],
                    stdin=rename_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=stderr_file,
                    text=True,
                )
                rename_proc.stdout.close()
            else:
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
                rows = patch.update_dbsnp_from_stream(
                    iter(proc.stdout),
                    progress_callback=lambda n: progress.update(n),
                )
                rc = proc.wait()
                if rename_proc:
                    rename_rc = rename_proc.wait()
                    if rename_rc != 0:
                        raise RuntimeError(
                            f"bcftools annotate --rename-chrs failed with "
                            f"exit code {rename_rc}"
                        )
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
        if rename_proc is not None and rename_proc.poll() is None:
            rename_proc.terminate()
        patch.set_metadata("dbsnp", version or "unknown", status="failed")
        raise

    patch.set_metadata("dbsnp", version or "unknown", status="complete")
    progress.done(f"{rows:,} variants updated")


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


def _run_init(
    vcf_path: str,
    label: str | None = None,
    gnomad: bool = False,
    dbsnp: bool = False,
    gwas: bool = False,
    fast: bool = False,
):
    """Full first-time setup: add + download + annotate + configure."""
    vcf_path = Path(vcf_path).expanduser().resolve()
    label = label or "default"

    print("=== GeneChat Setup ===\n")

    # Step 1: Validate VCF
    print("Step 1: Validating VCF...")
    if not _validate_vcf(vcf_path):
        raise typer.Exit(code=ExitCode.VCF_ERROR)

    # Step 2: Detect and fix bare contig names
    print("\nStep 2: Checking contig names...")
    if _detect_bare_contigs(vcf_path):
        if not shutil.which("bcftools"):
            rprint(
                "[red]Error:[/red] VCF uses bare contig names (1, 2, ...) but bcftools "
                "is needed to fix them.",
                file=sys.stderr,
            )
            print("  Install: brew install bcftools (macOS)", file=sys.stderr)
            raise typer.Exit(code=ExitCode.TOOL_ERROR)
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
        raise typer.Exit(code=ExitCode.CONFIG_ERROR)
    print("  lookup_tables.db: OK")

    # Step 5: Install GWAS if requested
    step = 5
    if gwas:
        print(f"\nStep {step}: Installing GWAS Catalog...")
        _run_install(gwas=True)
        step += 1

    # Next step: Annotate (auto-downloads ClinVar, SnpEff DB, dbSNP, gnomAD as needed)
    print(f"\nStep {step}: Building annotation database...")
    _run_annotate(gnomad=gnomad, dbsnp=dbsnp, fast=fast, genome=label)

    # Print MCP config
    step += 1
    print(f"\n--- Step {step}: MCP Configuration ---\n")
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

    # Next steps
    print("\n=== Next Steps ===\n")
    print(f"Your genome '{label}' is ready. Here's what you can enhance:\n")
    if not gwas:
        print("  GWAS trait search (58 MB):     genechat install --gwas")
    if not gnomad:
        print(
            f"  gnomAD smart filter (150 GB):  genechat annotate --genome {label} --gnomad"
        )
    if not dbsnp:
        # rsID probe: check if VCF already has rsIDs
        _rsid_hint = "  dbSNP rsID backfill:           "
        try:
            from genechat.patch import PatchDB as _PDB

            _cfg = load_config()
            _pd = _PDB(_patch_db_path_for(vcf_path, _cfg.genomes[label]), readonly=True)
            try:
                _total, _has = _pd.rsid_coverage()
            finally:
                _pd.close()
            if _total > 0 and _has / _total > 0.9:
                print(_rsid_hint + "[Not needed — your VCF already has rsIDs]")
            else:
                print(_rsid_hint + "[Recommended — your VCF lacks rsIDs]")
                print(
                    f"                                 genechat annotate --genome {label} --dbsnp"
                )
        except Exception:
            print(
                f"  dbSNP rsID backfill:           genechat annotate --genome {label} --dbsnp"
            )

    print("\nRun 'genechat status' to see your full setup.")
    print("=== Setup complete ===")


# ---------------------------------------------------------------------------
# genechat status
# ---------------------------------------------------------------------------


def _gwas_installed(gwas_db_path: str) -> bool:
    """Check if the GWAS database is installed and has the expected table."""
    import sqlite3 as _sql

    path = Path(gwas_db_path)
    if not path.exists():
        return False
    try:
        with _sql.connect(str(path)) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='gwas_associations'"
            ).fetchone()
            return row is not None
    except _sql.Error:
        return False


def _freshness_indicator(
    source: str, installed_version: str, latest_versions: dict[str, str | None]
) -> str:
    """Return a freshness suffix for a layer, or empty string if not checking."""
    if not latest_versions:
        return ""
    latest = latest_versions.get(source)
    if latest is None:
        return ""
    from genechat.update import _is_newer

    if _is_newer(latest, installed_version):
        return f", [yellow]newer: {latest}[/yellow]"
    return ", [green]up to date[/green]"


def _run_status(json_output: bool = False, check_updates: bool = False):
    """Show genome info, annotation state, reference versions."""
    config = load_config()

    if json_output:
        _run_status_json(config)
        return

    if not config.genomes:
        print("No genome registered. Run: genechat init <vcf>")
        return

    from genechat.download import (
        clinvar_installed,
        dbsnp_installed,
        gnomad_installed,
        references_dir,
        snpeff_installed,
    )

    # Fetch latest versions upfront if --check-updates
    latest_versions: dict[str, str | None] = {}
    if check_updates:
        from genechat.update import check_all_versions

        latest_versions = check_all_versions()

    # Section 1: Installed databases (genome-independent)
    gwas_ok = _gwas_installed(config.gwas_db_path)
    print("Installed databases:")
    if gwas_ok:
        print("  GWAS:           installed (CC0)")
    else:
        print("  GWAS:           not installed — genechat install --gwas")
    print("  Lookup tables:  installed")
    print()

    # Section 2: Per-genome annotation state
    print("Genomes:")
    any_gnomad_annotated = False
    for label, genome_cfg in config.genomes.items():
        print(f"  {label}:")

        vcf_path_str = genome_cfg.vcf_path
        if not vcf_path_str:
            print("    VCF: not configured\n")
            continue

        vcf_path = Path(vcf_path_str)
        vcf_exists = vcf_path.exists()
        vcf_status = "[green]exists[/green]" if vcf_exists else "[red]NOT FOUND[/red]"
        rprint(f"    VCF:      [dim]{vcf_path}[/dim] ({vcf_status})")

        # Patch DB status — use same resolution as annotate
        patch_db_path = _patch_db_path_for(vcf_path, genome_cfg)
        if patch_db_path.exists():
            size_mb = patch_db_path.stat().st_size / 1024 / 1024
            rprint(f"    Patch DB: [dim]{patch_db_path}[/dim] ({size_mb:.0f} MB)")

            from genechat.patch import PatchDB

            patch = PatchDB(patch_db_path, readonly=True)
            try:
                meta = patch.get_metadata()
            finally:
                patch.close()

            if meta.get("gnomad", {}).get("status") == "complete":
                any_gnomad_annotated = True

            layers = []
            for source in ["snpeff", "clinvar", "gnomad", "dbsnp"]:
                info = meta.get(source, {})
                if info:
                    status = info.get("status", "unknown")
                    version = info.get("version", "?")
                    if status == "complete":
                        freshness = _freshness_indicator(
                            source, version, latest_versions
                        )
                        lic_tag = _LICENSE_TAGS.get(source, "")
                        lic_suffix = f", {lic_tag}" if lic_tag else ""
                        layers.append(f"{source} ({version}{freshness}{lic_suffix})")
                    elif status == "pending":
                        layers.append(f"{source} ([yellow]in progress[/yellow])")
                    elif status == "failed":
                        layers.append(f"{source} ([red]FAILED[/red])")
            if layers:
                rprint(f"    Layers:   {', '.join(layers)}")
            else:
                rprint("    Layers:   none")
        else:
            print("    Patch DB: not built")
            print(f"    Run: genechat annotate --genome {label}")
        print()

    # Section 3: Annotation caches
    rprint(f"Annotation caches: [dim]{references_dir()}[/dim]")
    print(f"  ClinVar:  {'cached' if clinvar_installed() else 'not cached'}")
    print(f"  SnpEff:   {'cached' if snpeff_installed() else 'not cached'}")
    print(f"  dbSNP:    {'cached' if dbsnp_installed() else 'not cached'}")
    gnomad_files = gnomad_installed()
    if gnomad_files:
        print("  gnomAD:   cached")
    elif any_gnomad_annotated:
        print("  gnomAD:   not cached (downloaded per-chromosome during annotation)")
    else:
        print("  gnomAD:   not cached")


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
            "is_primary": False,  # Legacy field kept for JSON compat
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

    data["references"]["gwas"] = _gwas_installed(config.gwas_db_path)

    print(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# License tags for status output
# ---------------------------------------------------------------------------

_LICENSE_TAGS: dict[str, str] = {
    "snpeff": "MIT",
    "clinvar": "public domain",
    "gnomad": "ODbL 1.0",
    "dbsnp": "public domain",
}


# ---------------------------------------------------------------------------
# genechat licenses
# ---------------------------------------------------------------------------


def _has_annotation_layer(config, layer: str) -> bool:
    """Check if any genome has the given annotation layer completed."""
    for _label, genome_cfg in config.genomes.items():
        if not genome_cfg.vcf_path:
            continue
        patch_db_path = _patch_db_path_for(Path(genome_cfg.vcf_path), genome_cfg)
        if patch_db_path.exists():
            from genechat.patch import PatchDB

            patch = PatchDB(patch_db_path, readonly=True)
            try:
                meta = patch.get_metadata()
            finally:
                patch.close()
            if meta.get(layer, {}).get("status") == "complete":
                return True
    return False


def _lookup_db_has_table(config, table_name: str) -> bool:
    """Check if the lookup_tables.db contains the given table."""
    import sqlite3 as _sql

    db_path = config.lookup_db_path
    if not Path(db_path).exists():
        return False
    try:
        with _sql.connect(db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            return row is not None
    except Exception:
        return False


def _run_licenses():
    """Print data source licenses for the current installation."""
    config = load_config()

    from genechat.download import dbsnp_installed, gnomad_installed

    print("Data source licenses for your GeneChat installation")
    print("=" * 52)
    print()

    # Always-applicable sources
    print("Always applicable:")
    print("  ClinVar          Public domain (NCBI)")
    print("  SnpEff           MIT — Copyright Pablo Cingolani")
    print("  CPIC             CC0 (cite: cpicpgx.org)")
    print("  HGNC             CC0 (cite: PMID:36243972)")
    print("  Ensembl          No restrictions (cite: PMID:39656687)")
    print()

    # Enhanced-warning gene list (HPO + ClinVar + ACMG SF)
    if _lookup_db_has_table(config, "enhanced_warning_genes"):
        print("Enhanced-warning gene list (bundled in lookup_tables.db):")
        print("  Sources:         ClinVar (public domain) + HPO + ACMG SF v3.3")
        print(
            "  HPO license:     Custom — must cite, show version, do not modify HPO data"
        )
        print(
            "  HPO cite:        Kohler S et al., Nucleic Acids Res 2021. PMID: 33264411"
        )
        print("  ACMG SF cite:    Miller DT et al., Genet Med 2023. PMID: 37347242")
        print()
    else:
        print(
            "Enhanced-warning gene list: not found in lookup DB — run genechat install --seeds"
        )
        print()

    # gnomAD
    if _has_annotation_layer(config, "gnomad") or gnomad_installed():
        print("gnomAD (installed):")
        print("  License:         Open Database License (ODbL) v1.0")
        print('  Attribution:     "Contains information from the Genome Aggregation')
        print('                   Database (gnomAD), made available under the ODbL."')
        print(
            "  Share-alike:     Derivative databases (patch.db with gnomAD frequencies)"
        )
        print("                   must be offered under ODbL if shared.")
        print("                   Tool responses to the LLM are produced works and")
        print("                   require only the attribution notice above.")
        print(
            "  Cite:            Chen S et al., Nature 2024. DOI: 10.1038/s41586-023-06045-0"
        )
        print()
    else:
        print("gnomAD:            not installed")
        print()

    # dbSNP
    if _has_annotation_layer(config, "dbsnp") or dbsnp_installed():
        print("dbSNP (installed):")
        print("  License:         Public domain (NCBI)")
        print(
            "  Cite:            Sherry ST et al., Nucleic Acids Res 2001. PMID: 11125122"
        )
        print()
    else:
        print("dbSNP:             not installed")
        print()

    # GWAS Catalog
    gwas_ok = _gwas_installed(config.gwas_db_path)
    if gwas_ok:
        print("GWAS Catalog (installed):")
        print("  License:         CC0 1.0")
        print(
            "  Cite:            Sollis E et al., Nucleic Acids Res 2023. PMID: 36350656"
        )
        print()
    else:
        print("GWAS Catalog:      not installed")
        print()

    # PGS Catalog scores
    if _lookup_db_has_table(config, "prs_weights"):
        print("PGS Catalog (bundled in lookup_tables.db):")
        print(
            "  Catalog cite:    Lambert SA et al., Nat Genet 2024. DOI: 10.1038/s41588-024-01937-x"
        )
        print("  Installed scores:")
        print("    PGS000010 (CAD)        Mega JL et al., Lancet 2015. PMID: 25748612")
        print(
            "    PGS000349 (CAD)        Pechlivanis S et al., BMC Med Genet 2020. PMID: 32912153"
        )
        print("                           CC BY 4.0")
        print(
            "    PGS000074 (Colorectal) Graff RE et al., Nat Commun 2021. PMID: 33579919"
        )
        print("                           CC BY 4.0")
        print(
            "    PGS002251 (BMI)        Dashti HS et al., BMC Med 2022. PMID: 35016652"
        )
        print("                           CC BY 4.0")
        print()
    else:
        print(
            "PGS Catalog:       not found in lookup DB — run genechat install --seeds"
        )
        print()

    print("Full details: docs/licenses.md")


# ---------------------------------------------------------------------------
# Seed data refresh (used by install --seeds)
# ---------------------------------------------------------------------------


def _run_update_seeds():
    """Fetch latest seed data from APIs and rebuild lookup_tables.db."""
    from genechat.seeds.pipeline import run_pipeline

    print("Updating seed data from upstream APIs...")
    rc = run_pipeline()
    if rc != 0:
        rprint("[red]Error:[/red] Seed data update failed.", file=sys.stderr)
        raise typer.Exit(code=ExitCode.GENERAL_ERROR)


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
