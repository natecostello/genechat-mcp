#!/usr/bin/env python3
"""Download GIAB NA12878 benchmark VCF for GeneChat e2e testing.

Downloads the GIAB HG001 VCF and fixes chromosome naming (GIAB uses bare
names like '1', '2'; GeneChat expects 'chr1', 'chr2'). All annotation is
handled by ``genechat init`` using the production pipeline.

Usage:
    uv run python scripts/setup_giab.py [OUTPUT_DIR]

Output: OUTPUT_DIR/HG001_raw.vcf.gz + .tbi

Then run the production annotation pipeline:
    uv run genechat init OUTPUT_DIR/HG001_raw.vcf.gz

Approximate time: ~5 min download + ~30 min annotation via genechat init.
"""

import argparse
import gzip
import urllib.request
from pathlib import Path

import pysam

# --- Download URLs ---

GIAB_BASE = (
    "https://ftp-trace.ncbi.nlm.nih.gov/giab/ftp/release"
    "/NA12878_HG001/NISTv4.2.1/GRCh38"
)
GIAB_VCF_URL = f"{GIAB_BASE}/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz"


def fix_chrom(chrom: str) -> str:
    """Add 'chr' prefix if missing. GIAB uses bare numbers (1, 2, ..., X, Y)."""
    if chrom.startswith("chr"):
        return chrom
    return f"chr{chrom}"


def download_file(url: str, dest: Path, label: str = "") -> None:
    """Download a file if it doesn't already exist. Shows progress."""
    if dest.exists():
        print(f"  Already exists: {dest.name}")
        return

    display = label or dest.name
    print(f"  Downloading {display}...")

    def _reporthook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(
                f"\r  {display}: {mb:.0f}/{total_mb:.0f} MB ({pct}%)",
                end="",
                flush=True,
            )
        else:
            mb = downloaded / (1024 * 1024)
            print(f"\r  {display}: {mb:.0f} MB", end="", flush=True)

    urllib.request.urlretrieve(url, str(dest), reporthook=_reporthook)
    print()  # newline after progress


def fix_chr_prefix(input_vcf: Path, output_vcf: Path) -> int:
    """Rewrite VCF with chr-prefixed contig names.

    GIAB VCFs use bare chromosome names (1, 2, ..., X, Y).
    GeneChat expects chr-prefixed names (chr1, chr2, ...).

    Returns the number of variants processed.
    """
    temp_vcf = output_vcf.with_suffix("")  # remove .gz for uncompressed write
    if temp_vcf.suffix != ".vcf":
        temp_vcf = output_vcf.parent / (
            output_vcf.stem.replace(".vcf", "") + "_temp.vcf"
        )

    count = 0
    with gzip.open(str(input_vcf), "rt") as fin, open(str(temp_vcf), "w") as fout:
        for line in fin:
            if line.startswith("##"):
                # Fix contig names in header
                if line.startswith("##contig=<ID=") and not line.startswith(
                    "##contig=<ID=chr"
                ):
                    line = line.replace("##contig=<ID=", "##contig=<ID=chr", 1)
                fout.write(line)
                continue

            if line.startswith("#"):
                fout.write(line)
                continue

            # Data line — fix chromosome field
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 1:
                fields[0] = fix_chrom(fields[0])
            fout.write("\t".join(fields) + "\n")

            count += 1
            if count % 500_000 == 0:
                print(f"  Processed {count:,} variants...", flush=True)

    # Compress and index
    print(f"  Compressing and indexing ({count:,} variants)...")
    if output_vcf.exists():
        output_vcf.unlink()
    tbi_path = Path(f"{output_vcf}.tbi")
    if tbi_path.exists():
        tbi_path.unlink()

    pysam.tabix_compress(str(temp_vcf), str(output_vcf))
    pysam.tabix_index(str(output_vcf), preset="vcf")
    temp_vcf.unlink()

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Download GIAB NA12878 benchmark VCF for GeneChat e2e testing"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="./giab",
        help="Output directory (default: ./giab)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    output_vcf = output_dir / "HG001_raw.vcf.gz"
    if output_vcf.exists() and Path(f"{output_vcf}.tbi").exists():
        print(f"Output already exists: {output_vcf}")
        print("Delete it to re-run.")
        return

    # --- Step 1: Download GIAB VCF ---
    print("Step 1/2: Downloading GIAB NA12878 v4.2.1 GRCh38...")
    giab_vcf = work_dir / "HG001_download.vcf.gz"
    download_file(GIAB_VCF_URL, giab_vcf, "GIAB VCF (~120 MB)")

    # --- Step 2: Fix chromosome prefix ---
    print("Step 2/2: Fixing chromosome names (1 -> chr1)...")
    count = fix_chr_prefix(giab_vcf, output_vcf)

    # --- Cleanup work directory ---
    import shutil

    print("Cleaning up intermediate files...")
    try:
        shutil.rmtree(work_dir)
        print(f"  Removed {work_dir}")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Failed to remove work directory {work_dir}: {exc}")

    # --- Done ---
    print()
    print("=" * 50)
    print(f"GIAB VCF ready: {output_vcf} ({count:,} variants)")
    print("=" * 50)
    print()
    print("Next: run the production annotation pipeline:")
    print(f"  uv run genechat init {output_vcf}")
    print()
    print("Then run e2e tests:")
    print(f"  export GENECHAT_GIAB_VCF={output_vcf}")
    print("  uv run pytest tests/e2e/ -v")


if __name__ == "__main__":
    main()
