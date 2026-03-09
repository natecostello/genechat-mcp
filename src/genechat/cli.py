"""CLI entry point for GeneChat — dispatches subcommands.

Commands:
  genechat init <vcf>           Full first-time setup (add + download + annotate)
  genechat add <vcf>            Register a VCF file
  genechat download [options]   Download reference databases
  genechat annotate [options]   Build/update patch.db
  genechat update [--apply]     Check for newer references
  genechat status               Show genome + annotation state
  genechat serve / genechat     Start the MCP server
"""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from platformdirs import user_config_dir

from genechat.config import load_config, write_config


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="genechat",
        description="GeneChat MCP server for conversational personal genomics",
    )
    sub = parser.add_subparsers(dest="command")

    # genechat init
    init_p = sub.add_parser("init", help="Full first-time setup for a VCF file")
    init_p.add_argument("vcf_path", help="Path to your raw VCF (.vcf.gz)")
    init_p.add_argument("--label", help="Name for this genome (default: from filename)")
    init_p.add_argument(
        "--gnomad", action="store_true", help="Also download gnomAD (~8 GB)"
    )
    init_p.add_argument(
        "--dbsnp", action="store_true", help="Also download dbSNP (~20 GB)"
    )

    # genechat add
    add_p = sub.add_parser("add", help="Register a VCF file")
    add_p.add_argument("vcf_path", help="Path to your VCF (.vcf.gz)")
    add_p.add_argument("--label", help="Name for this genome")

    # genechat download
    dl_p = sub.add_parser("download", help="Download reference databases")
    dl_p.add_argument(
        "--gnomad", action="store_true", help="Download gnomAD exomes (~8 GB)"
    )
    dl_p.add_argument("--dbsnp", action="store_true", help="Download dbSNP (~20 GB)")
    dl_p.add_argument("--all", action="store_true", help="Download everything")
    dl_p.add_argument(
        "--force", action="store_true", help="Re-download even if files exist"
    )

    # genechat download --gwas
    dl_p.add_argument(
        "--gwas", action="store_true", help="Download GWAS Catalog (~58 MB)"
    )

    # genechat annotate
    ann_p = sub.add_parser("annotate", help="Build or update patch.db")
    ann_p.add_argument(
        "--clinvar", action="store_true", help="Re-annotate ClinVar layer"
    )
    ann_p.add_argument("--gnomad", action="store_true", help="Re-annotate gnomAD layer")
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
    sub.add_parser("status", help="Show genome info and annotation state")

    # genechat serve
    sub.add_parser("serve", help="Start the MCP server")

    args = parser.parse_args(argv)

    if args.command == "init":
        _run_init(args)
    elif args.command == "add":
        _run_add(args.vcf_path, args.label)
    elif args.command == "download":
        _run_download(args)
    elif args.command == "annotate":
        _run_annotate(args)
    elif args.command == "update":
        _run_update(args)
    elif args.command == "status":
        _run_status()
    else:
        # No subcommand or "serve" -> start MCP server
        _run_serve()


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
        print(f"Error: VCF file not found: {vcf_path}", file=sys.stderr)
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
        sys.exit(1)

    # Write config
    config_dir = Path(user_config_dir("genechat"))
    config_path = write_config(vcf_path, config_dir, label=label or "")
    genome_label = label or "default"
    print(f"VCF registered as '{genome_label}'. Config: {config_path}")
    return config_path


# ---------------------------------------------------------------------------
# genechat download [options]
# ---------------------------------------------------------------------------


def _run_download(args):
    """Download reference databases to shared cache."""
    from genechat.download import (
        download_clinvar,
        download_dbsnp,
        download_gnomad,
        download_snpeff_db,
        references_dir,
    )

    print(f"References directory: {references_dir()}\n")

    # Default (no flags): recommended set (ClinVar + SnpEff DB)
    download_all = args.all
    explicit = args.gnomad or args.dbsnp or args.gwas

    # Always download ClinVar + SnpEff (unless only explicit optional flags)
    if not explicit or download_all:
        download_clinvar(force=args.force)
        download_snpeff_db()

    if args.gnomad or download_all:
        download_gnomad(force=args.force)

    if args.dbsnp or download_all:
        download_dbsnp(force=args.force)

    if args.gwas or download_all:
        _download_and_build_gwas(force=args.force)

    print("\nDownload complete.")


# ---------------------------------------------------------------------------
# genechat annotate [options]
# ---------------------------------------------------------------------------


def _resolve_genome_label(config, genome_arg: str | None) -> tuple[str, object]:
    """Resolve a --genome arg to (label, GenomeConfig). Exits on error."""
    if not config.genomes:
        print("Error: No VCF registered. Run: genechat add <vcf>", file=sys.stderr)
        sys.exit(1)

    label = genome_arg or config.default_genome
    if label not in config.genomes:
        available = ", ".join(config.genomes.keys())
        print(
            f"Error: Unknown genome '{label}'. Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)

    return label, config.genomes[label]


def _run_annotate(args):
    """Build or update patch.db for the registered VCF."""
    config = load_config()
    genome_arg = getattr(args, "genome", None)
    label, genome_cfg = _resolve_genome_label(config, genome_arg)

    vcf_path_str = genome_cfg.vcf_path
    if not vcf_path_str:
        print(
            f"Error: Genome '{label}' has no vcf_path. Run: genechat add <vcf>",
            file=sys.stderr,
        )
        sys.exit(1)

    vcf_path = Path(vcf_path_str)
    if not vcf_path.exists():
        print(f"Error: VCF not found: {vcf_path}", file=sys.stderr)
        sys.exit(1)

    # Determine patch.db path
    patch_db_path = _patch_db_path_for(vcf_path, genome_cfg)

    from genechat.download import (
        clinvar_installed,
        dbsnp_installed,
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
    run_gnomad = (first_run or args.gnomad or args.all) and gnomad_installed()
    run_dbsnp = (args.dbsnp or args.all) and dbsnp_installed()

    # Check prerequisites
    if run_snpeff and not snpeff_installed():
        print(
            "Error: snpEff not found in PATH. Required for functional annotation.",
            file=sys.stderr,
        )
        print("  Install: brew install brewsci/bio/snpeff (macOS)", file=sys.stderr)
        sys.exit(1)

    if not shutil.which("bcftools"):
        print("Error: bcftools not found in PATH.", file=sys.stderr)
        print("  Install: brew install bcftools (macOS)", file=sys.stderr)
        sys.exit(1)

    if run_clinvar and not shutil.which("tabix"):
        print(
            "Error: tabix not found in PATH (needed for ClinVar contig rename).",
            file=sys.stderr,
        )
        print("  Install: brew install htslib (macOS)", file=sys.stderr)
        sys.exit(1)

    if run_clinvar and not clinvar_installed():
        print(
            "Error: ClinVar reference not found.",
            file=sys.stderr,
        )
        print("Run: genechat download", file=sys.stderr)
        sys.exit(1)

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
            _annotate_gnomad(patch, vcf_path, step, total_steps, not first_run)
        elif (first_run or args.gnomad) and not gnomad_installed():
            print("  gnomAD: skipped (not installed)")
            print("    Install: genechat download --gnomad (~8 GB)")

        if run_dbsnp:
            step += 1
            _annotate_dbsnp(patch, vcf_path, step, total_steps, not first_run)
        elif (args.dbsnp or args.all) and not dbsnp_installed():
            print("  dbSNP: skipped (not installed)")
            print("    Install: genechat download --dbsnp (~20 GB)")

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


def _annotate_gnomad(patch, vcf_path: Path, step: int, total: int, is_update: bool):
    """Step 3: gnomAD population frequencies (per-chromosome)."""
    from genechat.download import GNOMAD_CHROMS, gnomad_chr_path

    print(f"  [{step}/{total}] gnomAD population frequencies...")

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
        sys.exit(1)

    # Step 2: Detect and fix bare contig names
    print("\nStep 2: Checking contig names...")
    if _detect_bare_contigs(vcf_path):
        if not shutil.which("bcftools"):
            print(
                "Error: VCF uses bare contig names (1, 2, ...) but bcftools "
                "is needed to fix them.",
                file=sys.stderr,
            )
            print("  Install: brew install bcftools (macOS)", file=sys.stderr)
            sys.exit(1)
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
        sys.exit(1)
    print("  lookup_tables.db: OK")

    # Step 5: Download references
    print("\nStep 5: Downloading reference databases...")
    from genechat.download import (
        clinvar_installed,
        download_clinvar,
        download_gnomad,
        download_snpeff_db,
        snpeff_installed,
    )

    download_clinvar()
    download_snpeff_db()
    if args.gnomad:
        download_gnomad()
    if args.dbsnp:
        from genechat.download import download_dbsnp

        download_dbsnp()

    # Step 6: Annotate
    print("\nStep 6: Building annotation database...")
    if not snpeff_installed():
        print(
            "WARNING: snpEff not installed. Skipping annotation.\n"
            "Install snpEff, then run: genechat annotate",
            file=sys.stderr,
        )
    elif not clinvar_installed():
        print(
            "WARNING: ClinVar download failed. Skipping annotation.\n"
            "Run: genechat download && genechat annotate",
            file=sys.stderr,
        )
    else:
        ann_args = argparse.Namespace(
            clinvar=False,
            gnomad=False,
            snpeff=False,
            dbsnp=False,
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
    print("\nOptional: Enable GWAS trait search:")
    print("  genechat download --gwas")
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
                "Error: No genome registered. Run: genechat add <vcf>",
                file=sys.stderr,
            )
            sys.exit(1)

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


def _run_status():
    """Show genome info, annotation state, reference versions."""
    config = load_config()

    if not config.genomes:
        print("No genome registered. Run: genechat init <vcf>")
        return

    print("=== Registered Genomes ===\n")

    for label, genome_cfg in config.genomes.items():
        is_default = label == config.default_genome
        suffix = " (primary)" if is_default else ""
        print(f"[{label}]{suffix}")

        vcf_path_str = genome_cfg.vcf_path
        if not vcf_path_str:
            print("  VCF: not configured\n")
            continue

        vcf_path = Path(vcf_path_str)
        print(f"  VCF: {vcf_path} ({'exists' if vcf_path.exists() else 'NOT FOUND'})")

        # Patch DB status
        patch_db_str = genome_cfg.patch_db
        if patch_db_str and Path(patch_db_str).exists():
            patch_db_path = Path(patch_db_str)
            size_mb = patch_db_path.stat().st_size / 1024 / 1024
            print(f"  Patch DB: {patch_db_path} ({size_mb:.0f} MB)")

            from genechat.patch import PatchDB

            patch = PatchDB(patch_db_path, readonly=True)
            try:
                meta = patch.get_metadata()
            finally:
                patch.close()

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
                        print(f"    {source:<10} {version:<20} (in progress)")
                    elif status == "failed":
                        print(f"    {source:<10} {version:<20} (FAILED)")
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

    print(f"References: {references_dir()}")
    print(
        f"  ClinVar:  {'installed' if clinvar_installed() else 'not installed — genechat download'}"
    )
    print(
        f"  SnpEff:   {'available' if snpeff_installed() else 'not installed — brew install brewsci/bio/snpeff'}"
    )
    print(
        f"  gnomAD:   {'installed' if gnomad_installed() else 'not installed — genechat download --gnomad'}"
    )
    print(
        f"  dbSNP:    {'installed' if dbsnp_installed() else 'not installed — genechat download --dbsnp'}"
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
        f"  GWAS:     {'installed' if gwas_ok else 'not installed — genechat download --gwas'}"
    )

    print("\nRun `genechat update` to check for newer versions.")


# ---------------------------------------------------------------------------
# genechat update --seeds
# ---------------------------------------------------------------------------


def _run_update_seeds():
    """Fetch latest seed data from APIs and rebuild lookup_tables.db."""
    project_root = _find_project_root()
    if not project_root:
        print(
            "Error: --seeds requires a source checkout (pyproject.toml not found).",
            file=sys.stderr,
        )
        sys.exit(1)

    build_script = project_root / "scripts" / "build_seed_data.py"
    if not build_script.exists():
        print(
            f"Error: build_seed_data.py not found at {build_script}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Updating seed data from upstream APIs...")
    result = subprocess.run(
        [sys.executable, str(build_script)],
        cwd=str(project_root),
    )
    if result.returncode != 0:
        print("Error: Seed data update failed.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# genechat download --gwas
# ---------------------------------------------------------------------------


def _download_and_build_gwas(force: bool = False):
    """Download GWAS Catalog and build a standalone gwas.db."""
    from genechat.gwas import build_gwas_db, download_gwas_catalog

    if force:
        download_gwas_catalog()

    print("Building GWAS Catalog database...")
    build_gwas_db()
