"""Download reference databases for GeneChat annotation.

Downloads to a shared cache directory (~/.local/share/genechat/references/
via platformdirs). References are genome-build-specific, not sample-specific.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen, Request

from platformdirs import user_data_dir

REFERENCES_DIR = Path(user_data_dir("genechat")) / "references"

CLINVAR_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
CLINVAR_TBI_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi"
)

GNOMAD_BASE = (
    "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes"
)
GNOMAD_CHROMS = [str(i) for i in range(1, 23)] + ["X", "Y"]


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


def _download_file(url: str, dest: Path, label: str = "") -> None:
    """Download a file with progress indication."""
    display = label or dest.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        req = Request(url, headers={"User-Agent": "genechat/0.1"})
        with urlopen(req, timeout=60) as resp:
            total = resp.headers.get("Content-Length")
            total_mb = f" ({int(total) / 1024 / 1024:.0f} MB)" if total else ""
            print(f"  Downloading {display}{total_mb}...")
            with open(tmp, "wb") as f:
                shutil.copyfileobj(resp, f)
        tmp.rename(dest)
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
    _download_file(CLINVAR_URL, vcf, "ClinVar VCF")
    _download_file(CLINVAR_TBI_URL, tbi, "ClinVar index")
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
        print("           conda install -c bioconda snpsift (Linux)", file=sys.stderr)
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
        version_line = result.stderr.split("\n")[0] if result.stderr else ""
        if "4.3" in version_line:
            return "GRCh38.86"
    except (subprocess.SubprocessError, OSError):
        pass
    return "GRCh38.p14"


def download_gnomad(force: bool = False) -> Path:
    """Download gnomAD v4 exome VCFs (per-chromosome). Returns the directory."""
    gdir = gnomad_dir()
    gdir.mkdir(parents=True, exist_ok=True)

    for chrom in GNOMAD_CHROMS:
        vcf_name = f"gnomad.exomes.v4.1.sites.chr{chrom}.vcf.bgz"
        tbi_name = f"{vcf_name}.tbi"
        vcf_path = gdir / vcf_name
        tbi_path = gdir / tbi_name

        if vcf_path.exists() and not force:
            print(f"  Already exists: {vcf_name}")
        else:
            _download_file(f"{GNOMAD_BASE}/{vcf_name}", vcf_path, vcf_name)

        if tbi_path.exists() and not force:
            pass  # tbi already present
        else:
            _download_file(f"{GNOMAD_BASE}/{tbi_name}", tbi_path, tbi_name)

    return gdir


def download_dbsnp(force: bool = False) -> Path | None:
    """Placeholder for dbSNP download. Returns None (manual download required)."""
    print(
        "  NOTE: dbSNP (~20 GB) requires manual download from:\n"
        "  https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/"
    )
    return None


def gnomad_installed() -> bool:
    """Check if gnomAD exome VCFs are fully installed."""
    gdir = gnomad_dir()
    if not gdir.exists():
        return False
    return all(
        (gdir / f"gnomad.exomes.v4.1.sites.chr{c}.vcf.bgz").exists()
        for c in GNOMAD_CHROMS
    )


def clinvar_installed() -> bool:
    return clinvar_path().exists() and clinvar_tbi_path().exists()


def snpeff_installed() -> bool:
    """Check if snpEff is available (tool, not just DB)."""
    return shutil.which("snpEff") is not None
