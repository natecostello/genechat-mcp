"""Download reference databases for GeneChat annotation.

Downloads to a shared cache directory (~/.local/share/genechat/references/
via platformdirs). References are genome-build-specific, not sample-specific.
"""

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


def _stream_dbsnp_rename(chr_map: Path, output: Path) -> None:
    """Download dbSNP and pipe directly through bcftools for contig rename.

    Streams the HTTP download into bcftools stdin, avoiding writing the
    ~20 GB raw file to disk. Only the chr-fixed output touches disk.
    """
    import tempfile

    url = f"{DBSNP_BASE}/{DBSNP_VCF_NAME}"
    req = Request(url, headers={"User-Agent": "genechat/0.1"})

    # Redirect stderr to a tempfile to avoid pipe buffer deadlock
    stderr_file = tempfile.SpooledTemporaryFile(max_size=64 * 1024)

    proc = subprocess.Popen(
        [
            "bcftools",
            "annotate",
            "--rename-chrs",
            str(chr_map),
            "-",
            "-Oz",
            "-o",
            str(output),
        ],
        stdin=subprocess.PIPE,
        stderr=stderr_file,
    )

    try:
        with urlopen(req, timeout=300) as resp:
            total = resp.headers.get("Content-Length")
            total_bytes = None
            if total:
                try:
                    total_bytes = int(total)
                except (TypeError, ValueError):
                    total_bytes = None
            size_str = f" ({format_size(total_bytes)})" if total_bytes else ""
            print(f"  Streaming dbSNP download + contig rename{size_str}...")
            progress = ProgressLine(
                "dbSNP stream", total=total_bytes, report_interval=15.0
            )
            start = time.monotonic()
            downloaded = 0
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                proc.stdin.write(chunk)
                downloaded += len(chunk)
                elapsed = time.monotonic() - start
                speed = format_speed(downloaded, elapsed) if elapsed > 0 else ""
                progress.update(downloaded, suffix=speed)

        proc.stdin.close()
        rc = proc.wait()

        if rc != 0:
            stderr_file.seek(0)
            err_msg = stderr_file.read().decode(errors="replace")[:500]
            raise subprocess.CalledProcessError(rc, "bcftools annotate", stderr=err_msg)

        progress.done(f"{format_size(downloaded)} streamed + renamed")

    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        proc.wait()
        raise
    finally:
        stderr_file.close()


def download_dbsnp(force: bool = False) -> Path | None:
    """Download dbSNP VCF + index, rename contigs to chr prefix.

    When the raw file doesn't exist on disk, streams the download directly
    through bcftools to avoid writing the ~20 GB raw file (saves ~20 GB
    peak disk). When the raw file already exists, uses it for the rename
    then deletes it afterward.

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

    # Validate tools before starting a ~20 GB download
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

    # Build temp path that preserves .vcf.gz extension for bcftools/tabix
    base_name = (
        chrfixed.name[:-7] if chrfixed.name.endswith(".vcf.gz") else chrfixed.stem
    )
    tmp = chrfixed.with_name(f"{base_name}.tmp.vcf.gz")
    tmp_tbi = tmp.with_name(f"{tmp.name}.tbi")

    raw_vcf = dbsnp_raw_path()
    use_streaming = not raw_vcf.exists() or force

    try:
        if use_streaming:
            # Stream: download piped directly through bcftools (no raw file on disk)
            _stream_dbsnp_rename(chr_map, tmp)
        else:
            # File-based: raw already on disk, use it then clean up
            print("  Renaming dbSNP contigs to chr prefix...")
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

        print("  Indexing chr-fixed dbSNP VCF...")
        subprocess.run(
            ["tabix", "-p", "vcf", str(tmp)],
            check=True,
            capture_output=True,
        )
        # Atomically replace final files
        os.replace(tmp, chrfixed)
        os.replace(tmp_tbi, chrfixed_tbi)

        # Clean up raw files if they exist (frees ~20 GB)
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
        tmp.unlink(missing_ok=True)
        tmp_tbi.unlink(missing_ok=True)
        return None
    finally:
        chr_map.unlink(missing_ok=True)

    print(f"  dbSNP ready: {chrfixed}")
    return chrfixed


def _write_refseq_chr_map(path: Path) -> None:
    """Write a RefSeq-to-chr contig rename map for bcftools --rename-chrs.

    Maps NC_000001.11 → chr1, ..., NC_000022.11 → chr22,
    NC_000023.11 → chrX, NC_000024.10 → chrY, NC_012920.1 → chrMT.
    """
    # RefSeq accessions for GRCh38 primary assembly
    refseq_map = {
        "NC_000001.11": "chr1",
        "NC_000002.12": "chr2",
        "NC_000003.12": "chr3",
        "NC_000004.12": "chr4",
        "NC_000005.10": "chr5",
        "NC_000006.12": "chr6",
        "NC_000007.14": "chr7",
        "NC_000008.11": "chr8",
        "NC_000009.12": "chr9",
        "NC_000010.11": "chr10",
        "NC_000011.10": "chr11",
        "NC_000012.12": "chr12",
        "NC_000013.11": "chr13",
        "NC_000014.9": "chr14",
        "NC_000015.10": "chr15",
        "NC_000016.10": "chr16",
        "NC_000017.11": "chr17",
        "NC_000018.10": "chr18",
        "NC_000019.10": "chr19",
        "NC_000020.11": "chr20",
        "NC_000021.9": "chr21",
        "NC_000022.11": "chr22",
        "NC_000023.11": "chrX",
        "NC_000024.10": "chrY",
        "NC_012920.1": "chrMT",
    }
    with open(path, "w") as f:
        for refseq, chrom in refseq_map.items():
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
