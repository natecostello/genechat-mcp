"""Download reference databases for GeneChat annotation.

Downloads to a shared cache directory (~/.local/share/genechat/references/
via platformdirs). References are genome-build-specific, not sample-specific.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

from platformdirs import user_data_dir

from genechat.progress import ProgressLine, format_size, format_speed

REFERENCES_DIR = Path(user_data_dir("genechat")) / "references"

CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
CLINVAR_TBI_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi"
)

GNOMAD_BASE = (
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes"
)
GNOMAD_CHROMS = [str(i) for i in range(1, 23)] + ["X", "Y"]

DBSNP_BASE = "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF"
DBSNP_VCF_NAME = "GCF_000001405.40.gz"
DBSNP_TBI_NAME = "GCF_000001405.40.gz.tbi"

# RefSeq accessions for GRCh38 primary assembly → chr-prefixed names.
# Used for per-chromosome remote region queries and contig rename.
DBSNP_CONTIGS = [
    ("NC_000001.11", "chr1"),
    ("NC_000002.12", "chr2"),
    ("NC_000003.12", "chr3"),
    ("NC_000004.12", "chr4"),
    ("NC_000005.10", "chr5"),
    ("NC_000006.12", "chr6"),
    ("NC_000007.14", "chr7"),
    ("NC_000008.11", "chr8"),
    ("NC_000009.12", "chr9"),
    ("NC_000010.11", "chr10"),
    ("NC_000011.10", "chr11"),
    ("NC_000012.12", "chr12"),
    ("NC_000013.11", "chr13"),
    ("NC_000014.9", "chr14"),
    ("NC_000015.10", "chr15"),
    ("NC_000016.10", "chr16"),
    ("NC_000017.11", "chr17"),
    ("NC_000018.10", "chr18"),
    ("NC_000019.10", "chr19"),
    ("NC_000020.11", "chr20"),
    ("NC_000021.9", "chr21"),
    ("NC_000022.11", "chr22"),
    ("NC_000023.11", "chrX"),
    ("NC_000024.10", "chrY"),
    ("NC_012920.1", "chrMT"),
]


def references_dir() -> Path:
    """Return the shared references directory, creating it if needed."""
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    return REFERENCES_DIR


def clinvar_path() -> Path:
    return references_dir() / "clinvar.vcf.gz"


def clinvar_tbi_path() -> Path:
    return references_dir() / "clinvar.vcf.gz.tbi"


def gnomad_dir() -> Path:
    return references_dir() / "gnomad_exomes_v4"


def gnomad_chr_path(chrom: str) -> Path:
    return gnomad_dir() / f"gnomad.exomes.v4.1.sites.chr{chrom}.vcf.bgz"


def download_file(url: str, dest: Path, label: str = "") -> None:
    """Download a file with progress indication."""
    display = label or dest.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        req = Request(url, headers={"User-Agent": "genechat/0.1"})
        with urlopen(req, timeout=300) as resp:
            total = resp.headers.get("Content-Length")
            total_bytes = None
            if total:
                try:
                    total_bytes = int(total)
                except (TypeError, ValueError):
                    total_bytes = None
            size_str = f" ({format_size(total_bytes)})" if total_bytes else ""
            print(f"  Downloading {display}{size_str}...")
            progress = ProgressLine(display, total=total_bytes)
            start = time.monotonic()
            with open(tmp, "wb") as f:
                downloaded = 0
                while True:
                    chunk = resp.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.monotonic() - start
                    speed = format_speed(downloaded, elapsed) if elapsed > 0 else ""
                    progress.update(downloaded, suffix=speed)
            progress.done(f"{format_size(downloaded)} downloaded")
        os.replace(tmp, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def download_clinvar(force: bool = False) -> Path:
    """Download ClinVar VCF + index. Returns path to the VCF."""
    vcf = clinvar_path()
    tbi = clinvar_tbi_path()
    if vcf.exists() and tbi.exists() and not force:
        print(f"  ClinVar already downloaded: {vcf}")
        return vcf
    download_file(CLINVAR_URL, vcf, "ClinVar VCF")
    download_file(CLINVAR_TBI_URL, tbi, "ClinVar index")
    return vcf


def download_snpeff_db() -> str | None:
    """Download SnpEff database. Returns the DB name or None on failure.

    Requires snpEff to be installed (Java dependency).
    """
    if not shutil.which("snpEff"):
        print(
            "  WARNING: snpEff not found in PATH. Skipping SnpEff DB download.",
            file=sys.stderr,
        )
        print("  Install: brew install brewsci/bio/snpeff (macOS)", file=sys.stderr)
        print("           conda install -c bioconda snpeff (Linux)", file=sys.stderr)
        return None

    db_name = _detect_snpeff_db()
    print(f"  Downloading SnpEff database: {db_name}...")
    try:
        subprocess.run(
            ["snpEff", "download", "-v", db_name],
            check=True,
            capture_output=True,
        )
        return db_name
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: SnpEff DB download failed: {e}", file=sys.stderr)
        return None


def _detect_snpeff_db() -> str:
    """Auto-detect the appropriate SnpEff database name."""
    try:
        result = subprocess.run(
            ["snpEff", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        combined = "\n".join(s for s in (result.stderr, result.stdout) if s)
        for line in combined.splitlines():
            if "4.3" in line:
                return "GRCh38.86"
    except (subprocess.SubprocessError, OSError):
        pass
    return "GRCh38.p14"


def download_gnomad_chr(chrom: str, force: bool = False) -> Path:
    """Download a single gnomAD chromosome VCF + index. Returns path to VCF."""
    gdir = gnomad_dir()
    gdir.mkdir(parents=True, exist_ok=True)
    vcf_name = f"gnomad.exomes.v4.1.sites.chr{chrom}.vcf.bgz"
    tbi_name = f"{vcf_name}.tbi"
    vcf_path = gdir / vcf_name
    tbi_path = gdir / tbi_name

    if vcf_path.exists() and tbi_path.exists() and not force:
        print(f"  Already exists: {vcf_name}")
    else:
        # Download VCF + TBI as an atomic pair (index must match the exact bgzip file)
        download_file(f"{GNOMAD_BASE}/{vcf_name}", vcf_path, vcf_name)
        download_file(f"{GNOMAD_BASE}/{tbi_name}", tbi_path, tbi_name)

    return vcf_path


def delete_gnomad_chr(chrom: str) -> None:
    """Delete a single gnomAD chromosome VCF + index to free disk space."""
    gdir = gnomad_dir()
    vcf_name = f"gnomad.exomes.v4.1.sites.chr{chrom}.vcf.bgz"
    (gdir / vcf_name).unlink(missing_ok=True)
    (gdir / f"{vcf_name}.tbi").unlink(missing_ok=True)


def download_gnomad(force: bool = False) -> Path:
    """Download all gnomAD v4 exome VCFs (per-chromosome). Returns the directory."""
    for chrom in GNOMAD_CHROMS:
        download_gnomad_chr(chrom, force=force)
    return gnomad_dir()


def dbsnp_dir() -> Path:
    return references_dir() / "dbsnp"


def dbsnp_raw_path() -> Path:
    """Path to the raw dbSNP VCF (RefSeq contig names)."""
    return dbsnp_dir() / DBSNP_VCF_NAME


def dbsnp_path() -> Path:
    """Path to the chr-prefix renamed dbSNP VCF (ready for bcftools annotate)."""
    return dbsnp_dir() / "dbsnp_chrfixed.vcf.gz"


def _delete_dbsnp_raw() -> None:
    """Delete raw dbSNP files (RefSeq-named) to free disk space."""
    raw = dbsnp_raw_path()
    raw_tbi = raw.with_suffix(raw.suffix + ".tbi")
    freed = 0
    for f in (raw, raw_tbi):
        if f.exists():
            freed += f.stat().st_size
            f.unlink()
    if freed > 0:
        print(f"  Cleaned up raw dbSNP files ({format_size(freed)} freed)")


def _dbsnp_state_path() -> Path:
    """Path to the per-chromosome resume state file."""
    return dbsnp_dir() / "dbsnp_progress.json"


def _load_dbsnp_state() -> dict:
    """Load per-chromosome resume state, or return empty state."""
    path = _dbsnp_state_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_dbsnp_state(state: dict) -> None:
    """Write per-chromosome resume state atomically."""
    path = _dbsnp_state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, path)


def _download_dbsnp_chromosome(
    refseq: str,
    chrom: str,
    remote_url: str,
    chr_map: Path,
    output: Path,
) -> None:
    """Fetch one chromosome from remote dbSNP via region query and rename contigs.

    Uses htslib HTTP Range requests to read only the bgzip blocks for the
    requested region. Pipes through bcftools annotate for contig rename.
    """
    tmp = output.with_suffix(".tmp.vcf.gz")
    try:
        # bcftools view -r <contig> <remote_url> | bcftools annotate --rename-chrs
        view = subprocess.Popen(
            ["bcftools", "view", "-r", refseq, remote_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        rename = subprocess.Popen(
            [
                "bcftools",
                "annotate",
                "--rename-chrs",
                str(chr_map),
                "-",
                "-Oz",
                "-o",
                str(tmp),
            ],
            stdin=view.stdout,
            stderr=subprocess.PIPE,
        )
        # Allow view to receive SIGPIPE if rename exits early
        view.stdout.close()

        _, rename_stderr = rename.communicate()
        view_rc = view.wait()
        rename_rc = rename.returncode

        if view_rc != 0:
            view_stderr = view.stderr.read().decode(errors="replace")[:500]
            raise subprocess.CalledProcessError(
                view_rc, "bcftools view", stderr=view_stderr
            )
        if rename_rc != 0:
            raise subprocess.CalledProcessError(
                rename_rc,
                "bcftools annotate",
                stderr=rename_stderr.decode(errors="replace")[:500],
            )

        os.replace(tmp, output)

    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        # Ensure stderr pipes are closed
        if view.stderr:
            view.stderr.close()


def _concat_dbsnp_chromosomes(chr_files: list[Path], output: Path) -> None:
    """Concatenate per-chromosome VCFs into the final chrfixed file and index it."""
    tmp = output.with_name(
        output.name.replace(".vcf.gz", ".tmp.vcf.gz")
        if output.name.endswith(".vcf.gz")
        else output.stem + ".tmp.vcf.gz"
    )
    tmp_tbi = tmp.with_name(f"{tmp.name}.tbi")
    output_tbi = output.with_name(f"{output.name}.tbi")

    try:
        subprocess.run(
            ["bcftools", "concat"]
            + [str(f) for f in chr_files]
            + ["-Oz", "-o", str(tmp)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["tabix", "-p", "vcf", str(tmp)],
            check=True,
            capture_output=True,
        )
        os.replace(tmp, output)
        os.replace(tmp_tbi, output_tbi)
    except Exception:
        tmp.unlink(missing_ok=True)
        tmp_tbi.unlink(missing_ok=True)
        raise


def download_dbsnp(force: bool = False) -> Path | None:
    """Download dbSNP per-chromosome via remote region queries, rename contigs.

    Uses htslib HTTP Range requests against the remote bgzipped+tabix-indexed
    dbSNP VCF to fetch one chromosome at a time. Each chromosome is independently
    resumable — on failure, completed chromosomes are skipped on restart.

    If a legacy raw dbSNP file exists on disk, uses file-based rename instead
    and deletes the raw file afterward.

    Returns path to the chr-fixed VCF on success.
    Returns None only if required tools are missing or processing fails;
    download/network errors will raise.
    """
    ddir = dbsnp_dir()
    ddir.mkdir(parents=True, exist_ok=True)

    chrfixed = dbsnp_path()
    chrfixed_tbi = chrfixed.with_suffix(chrfixed.suffix + ".tbi")

    if chrfixed.exists() and chrfixed_tbi.exists() and not force:
        print(f"  dbSNP already downloaded: {chrfixed}")
        return chrfixed

    if not shutil.which("bcftools"):
        print("  ERROR: bcftools not found. Cannot rename contigs.", file=sys.stderr)
        print("  Install: brew install bcftools (macOS)", file=sys.stderr)
        return None
    if not shutil.which("tabix"):
        print("  ERROR: tabix not found. Cannot index.", file=sys.stderr)
        print("  Install: brew install htslib (macOS)", file=sys.stderr)
        return None

    chr_map = ddir / "refseq_to_chr.txt"
    _write_refseq_chr_map(chr_map)

    # Legacy path: if raw dbSNP file already exists on disk, use file-based
    # rename then delete the raw file. This avoids re-downloading ~28 GB.
    raw_vcf = dbsnp_raw_path()
    if raw_vcf.exists() and not force:
        return _file_based_dbsnp_rename(raw_vcf, chr_map, chrfixed, ddir)

    # Per-chromosome remote region queries
    remote_url = f"{DBSNP_BASE}/{DBSNP_VCF_NAME}"
    total = len(DBSNP_CONTIGS)

    state = {} if force else _load_dbsnp_state()
    completed = set(state.get("completed_contigs", []))

    if completed:
        print(f"  Resuming dbSNP download ({len(completed)}/{total} complete)")

    chr_dir = ddir / "per_chrom"
    chr_dir.mkdir(exist_ok=True)
    chr_files = []

    try:
        for i, (refseq, chrom) in enumerate(DBSNP_CONTIGS, 1):
            chr_output = chr_dir / f"dbsnp_{chrom}.vcf.gz"
            chr_files.append(chr_output)

            if refseq in completed and chr_output.exists():
                print(f"  [{i}/{total}] {chrom} — already complete, skipping")
                continue

            print(f"  [{i}/{total}] Fetching {chrom} ({refseq})...")
            start = time.monotonic()
            _download_dbsnp_chromosome(refseq, chrom, remote_url, chr_map, chr_output)
            elapsed = time.monotonic() - start
            size = format_size(chr_output.stat().st_size)
            print(f"  [{i}/{total}] {chrom} done ({size}, {int(elapsed)}s)")

            completed.add(refseq)
            _save_dbsnp_state({"completed_contigs": sorted(completed)})

        print("  Concatenating per-chromosome files...")
        _concat_dbsnp_chromosomes(chr_files, chrfixed)
        print(f"  dbSNP ready: {chrfixed}")

        # Clean up per-chromosome files, state, and chr_map
        shutil.rmtree(chr_dir, ignore_errors=True)
        _dbsnp_state_path().unlink(missing_ok=True)
        _delete_dbsnp_raw()

    except subprocess.CalledProcessError as e:
        print(f"  ERROR: dbSNP processing failed: {e}", file=sys.stderr)
        if hasattr(e, "stderr") and e.stderr:
            stderr_str = (
                e.stderr.decode(errors="replace")[:500]
                if isinstance(e.stderr, bytes)
                else str(e.stderr)[:500]
            )
            print(f"  {stderr_str}", file=sys.stderr)
        return None
    finally:
        chr_map.unlink(missing_ok=True)

    return chrfixed


def _file_based_dbsnp_rename(
    raw_vcf: Path, chr_map: Path, chrfixed: Path, ddir: Path
) -> Path | None:
    """Rename contigs in a local raw dbSNP file, then delete the raw file."""
    print("  Renaming dbSNP contigs from existing raw file...")
    tmp = chrfixed.with_name(
        chrfixed.name.replace(".vcf.gz", ".tmp.vcf.gz")
        if chrfixed.name.endswith(".vcf.gz")
        else chrfixed.stem + ".tmp.vcf.gz"
    )
    tmp_tbi = tmp.with_name(f"{tmp.name}.tbi")
    chrfixed_tbi = chrfixed.with_name(f"{chrfixed.name}.tbi")

    try:
        subprocess.run(
            [
                "bcftools",
                "annotate",
                "--rename-chrs",
                str(chr_map),
                str(raw_vcf),
                "-Oz",
                "-o",
                str(tmp),
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["tabix", "-p", "vcf", str(tmp)],
            check=True,
            capture_output=True,
        )
        os.replace(tmp, chrfixed)
        os.replace(tmp_tbi, chrfixed_tbi)
        _delete_dbsnp_raw()
        print(f"  dbSNP ready: {chrfixed}")
        return chrfixed
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: dbSNP processing failed: {e}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        tmp_tbi.unlink(missing_ok=True)
        return None
    finally:
        chr_map.unlink(missing_ok=True)


def _write_refseq_chr_map(path: Path) -> None:
    """Write a RefSeq-to-chr contig rename map for bcftools --rename-chrs."""
    with open(path, "w") as f:
        for refseq, chrom in DBSNP_CONTIGS:
            f.write(f"{refseq} {chrom}\n")


def gnomad_installed() -> bool:
    """Check if gnomAD exome VCFs and indexes are fully installed."""
    gdir = gnomad_dir()
    if not gdir.exists():
        return False
    return all(
        (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz").exists()
        and (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz.tbi").exists()
        for c in GNOMAD_CHROMS
    )


def dbsnp_installed() -> bool:
    """Check if the chr-prefix renamed dbSNP VCF and index are installed."""
    chrfixed = dbsnp_path()
    return chrfixed.exists() and chrfixed.with_suffix(chrfixed.suffix + ".tbi").exists()


def clinvar_installed() -> bool:
    return clinvar_path().exists() and clinvar_tbi_path().exists()


def snpeff_installed() -> bool:
    """Check if snpEff is available (tool, not just DB)."""
    return shutil.which("snpEff") is not None
