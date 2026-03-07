#!/usr/bin/env python3
"""Pure-Python GIAB NA12878 setup for GeneChat.

Downloads the GIAB HG001 benchmark VCF and annotates it with ClinVar significance
and dbSNP rsIDs using only pysam — no bcftools, SnpEff, or Java required.

Usage:
    uv run python scripts/setup_giab.py [OUTPUT_DIR] [--skip-rsid]

Options:
    OUTPUT_DIR      Where to store files (default: ./giab)
    --skip-rsid     Skip the ~15 GB dbSNP download. ClinVar annotation still works,
                    but rsID-based lookups (e.g. "tell me about rs4149056") won't.

Output: OUTPUT_DIR/HG001_annotated.vcf.gz + .tbi

What this provides vs the full pipeline (setup_giab.sh):
    - Your genotype at every position (the only thing the LLM can't infer)
    - ClinVar clinical significance, condition, review status
    - dbSNP rsIDs (unless --skip-rsid)
    - NO SnpEff functional annotation (ANN field) — but Claude already knows
      functional consequences for well-characterized variants
    - NO gnomAD population frequencies

Approximate time: ~20-30 min (dominated by dbSNP download + annotation pass).
With --skip-rsid: ~5-10 min.
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
GIAB_TBI_URL = f"{GIAB_BASE}/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi"

CLINVAR_VCF_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
CLINVAR_TBI_URL = (
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi"
)

DBSNP_VCF_URL = (
    "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz"
)
DBSNP_TBI_URL = (
    "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz.tbi"
)

# --- RefSeq accession → chr name mapping (GRCh38.p14) ---
# dbSNP uses RefSeq contig names; we query by RefSeq name so we don't need to
# rewrite the 15 GB file.

CHR_TO_REFSEQ = {
    "1": "NC_000001.11",
    "2": "NC_000002.12",
    "3": "NC_000003.12",
    "4": "NC_000004.12",
    "5": "NC_000005.10",
    "6": "NC_000006.12",
    "7": "NC_000007.14",
    "8": "NC_000008.11",
    "9": "NC_000009.12",
    "10": "NC_000010.11",
    "11": "NC_000011.10",
    "12": "NC_000012.12",
    "13": "NC_000013.11",
    "14": "NC_000014.9",
    "15": "NC_000015.10",
    "16": "NC_000016.10",
    "17": "NC_000017.11",
    "18": "NC_000018.10",
    "19": "NC_000019.10",
    "20": "NC_000020.11",
    "21": "NC_000021.9",
    "22": "NC_000022.11",
    "X": "NC_000023.11",
    "Y": "NC_000024.10",
    "MT": "NC_012920.1",
}

# Reverse map for reference
REFSEQ_TO_CHR = {v: k for k, v in CHR_TO_REFSEQ.items()}


def fix_chrom(chrom: str) -> str:
    """Add 'chr' prefix if missing. GIAB uses bare numbers (1, 2, ..., X, Y)."""
    if chrom.startswith("chr"):
        return chrom
    return f"chr{chrom}"


def parse_clinvar_info(info_str: str) -> dict[str, str]:
    """Extract ClinVar fields from a VCF INFO string.

    Returns a dict with keys CLNSIG, CLNDN, CLNREVSTAT (if present).
    """
    result = {}
    for field in info_str.split(";"):
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        if key in ("CLNSIG", "CLNDN", "CLNREVSTAT"):
            result[key] = value
    return result


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


def lookup_rsid(
    dbsnp_tbx: pysam.TabixFile, chrom: str, pos: int, ref: str, alt: str
) -> str | None:
    """Look up rsID from dbSNP for a variant.

    Args:
        dbsnp_tbx: Open TabixFile for dbSNP VCF.
        chrom: Chromosome with chr prefix (e.g. 'chr1').
        pos: 1-based position.
        ref: Reference allele.
        alt: Alternate allele.

    Returns:
        rsID string (e.g. 'rs4149056') or None if not found.
    """
    # Convert chr name to RefSeq accession for dbSNP query
    bare = chrom.replace("chr", "")
    refseq = CHR_TO_REFSEQ.get(bare)
    if not refseq:
        return None

    try:
        for line in dbsnp_tbx.fetch(refseq, pos - 1, pos):
            fields = line.split("\t")
            if len(fields) < 5:
                continue
            db_pos = int(fields[1])
            db_ref = fields[3]
            db_alts = fields[4].split(",")
            if db_pos == pos and db_ref == ref and alt in db_alts:
                db_id = fields[2]
                if db_id and db_id != ".":
                    return db_id
    except ValueError:
        # Unknown contig in dbSNP
        pass

    return None


def lookup_clinvar(
    clinvar_tbx: pysam.TabixFile, chrom: str, pos: int, ref: str, alt: str
) -> dict[str, str]:
    """Look up ClinVar annotation for a variant.

    Args:
        clinvar_tbx: Open TabixFile for ClinVar VCF.
        chrom: Chromosome with chr prefix (e.g. 'chr1').
        pos: 1-based position.
        ref: Reference allele.
        alt: Alternate allele.

    Returns:
        Dict with CLNSIG, CLNDN, CLNREVSTAT keys (empty dict if not found).
    """
    # ClinVar may use bare contig names (1, 2, ...) or chr-prefixed — try both
    bare = chrom[3:] if chrom.startswith("chr") else chrom
    query_chroms = (chrom,) if chrom == bare else (chrom, bare)
    for query_chrom in query_chroms:
        try:
            for line in clinvar_tbx.fetch(query_chrom, pos - 1, pos):
                fields = line.split("\t")
                if len(fields) < 8:
                    continue
                cv_pos = int(fields[1])
                cv_ref = fields[3]
                cv_alts = fields[4].split(",")
                if cv_pos == pos and cv_ref == ref and alt in cv_alts:
                    return parse_clinvar_info(fields[7])
        except ValueError:
            # Unknown contig name — try the other format
            continue

    return {}


def annotate_giab(
    giab_vcf_path: Path,
    output_vcf_path: Path,
    clinvar_path: Path,
    dbsnp_path: Path | None,
) -> None:
    """Single-pass annotation of GIAB VCF.

    Reads GIAB VCF line-by-line, fixes chr prefix, adds rsID from dbSNP,
    adds ClinVar fields, writes annotated VCF.
    """
    # Open reference databases
    clinvar_tbx = pysam.TabixFile(str(clinvar_path))
    dbsnp_tbx = pysam.TabixFile(str(dbsnp_path)) if dbsnp_path else None

    # We write to an uncompressed temp file, then compress + index
    temp_vcf = output_vcf_path.with_suffix("")  # remove .gz
    if temp_vcf.suffix != ".vcf":
        temp_vcf = output_vcf_path.parent / (
            output_vcf_path.stem.replace(".vcf", "") + "_temp.vcf"
        )

    count = 0
    annotated_rsid = 0
    annotated_clinvar = 0

    with gzip.open(str(giab_vcf_path), "rt") as fin, open(str(temp_vcf), "w") as fout:
        for line in fin:
            if line.startswith("##"):
                # Pass through meta-information lines, fix contig names
                if line.startswith("##contig=<ID=") and not line.startswith(
                    "##contig=<ID=chr"
                ):
                    # Fix contig name: ##contig=<ID=1,...> → ##contig=<ID=chr1,...>
                    line = line.replace("##contig=<ID=", "##contig=<ID=chr", 1)
                fout.write(line)
                continue

            if line.startswith("#CHROM"):
                # Add INFO header lines for ClinVar fields before the #CHROM line
                fout.write(
                    "##INFO=<ID=CLNSIG,Number=.,Type=String,"
                    'Description="ClinVar clinical significance">\n'
                )
                fout.write(
                    "##INFO=<ID=CLNDN,Number=.,Type=String,"
                    'Description="ClinVar disease name">\n'
                )
                fout.write(
                    "##INFO=<ID=CLNREVSTAT,Number=.,Type=String,"
                    'Description="ClinVar review status">\n'
                )
                fout.write(line)
                continue

            # Data line
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                fout.write(line)
                continue

            # Fix chromosome prefix
            chrom = fix_chrom(fields[0])
            fields[0] = chrom

            pos = int(fields[1])
            ref = fields[3]
            alt = fields[4]

            # Lookup rsID from dbSNP if current ID is missing
            if dbsnp_tbx and (fields[2] == "." or not fields[2]):
                rsid = lookup_rsid(dbsnp_tbx, chrom, pos, ref, alt)
                if rsid:
                    fields[2] = rsid
                    annotated_rsid += 1

            # Lookup ClinVar
            clinvar_fields = lookup_clinvar(clinvar_tbx, chrom, pos, ref, alt)
            if clinvar_fields:
                # Append ClinVar fields to INFO
                info = fields[7]
                extra = ";".join(f"{k}={v}" for k, v in clinvar_fields.items())
                if info == ".":
                    fields[7] = extra
                else:
                    fields[7] = f"{info};{extra}"
                annotated_clinvar += 1

            fout.write("\t".join(fields) + "\n")

            count += 1
            if count % 100_000 == 0:
                rsid_msg = f", {annotated_rsid} rsIDs" if dbsnp_tbx else ""
                print(
                    f"  Processed {count:,} variants "
                    f"({annotated_clinvar} ClinVar{rsid_msg})...",
                    flush=True,
                )

    clinvar_tbx.close()
    if dbsnp_tbx:
        dbsnp_tbx.close()

    # Compress and index
    print(f"  Compressing and indexing ({count:,} total variants)...")
    if output_vcf_path.exists():
        output_vcf_path.unlink()
    tbi_path = Path(f"{output_vcf_path}.tbi")
    if tbi_path.exists():
        tbi_path.unlink()

    pysam.tabix_compress(str(temp_vcf), str(output_vcf_path))
    pysam.tabix_index(str(output_vcf_path), preset="vcf")
    temp_vcf.unlink()

    rsid_msg = f", {annotated_rsid:,} rsIDs added" if dbsnp_tbx else ""
    print(
        f"  Done: {count:,} variants, "
        f"{annotated_clinvar:,} ClinVar annotations{rsid_msg}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Pure-Python GIAB NA12878 setup for GeneChat"
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="./giab",
        help="Output directory (default: ./giab)",
    )
    parser.add_argument(
        "--skip-rsid",
        action="store_true",
        help="Skip dbSNP download (~15 GB). rsID lookups won't work.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    work_dir = output_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    output_vcf = output_dir / "HG001_annotated.vcf.gz"
    if output_vcf.exists() and Path(f"{output_vcf}.tbi").exists():
        print(f"Output already exists: {output_vcf}")
        print("Delete it to re-run annotation.")
        return

    # --- Step 1: Download GIAB VCF ---
    print("Step 1/4: Downloading GIAB NA12878 v4.2.1 GRCh38...")
    giab_vcf = work_dir / "HG001_raw.vcf.gz"
    giab_tbi = work_dir / "HG001_raw.vcf.gz.tbi"
    download_file(GIAB_VCF_URL, giab_vcf, "GIAB VCF (~120 MB)")
    download_file(GIAB_TBI_URL, giab_tbi, "GIAB VCF index")

    # --- Step 2: Download ClinVar ---
    print("Step 2/4: Downloading ClinVar...")
    clinvar_vcf = work_dir / "clinvar.vcf.gz"
    clinvar_tbi = work_dir / "clinvar.vcf.gz.tbi"
    download_file(CLINVAR_VCF_URL, clinvar_vcf, "ClinVar VCF (~100 MB)")
    download_file(CLINVAR_TBI_URL, clinvar_tbi, "ClinVar index")

    # --- Step 3: Download dbSNP (optional) ---
    dbsnp_vcf = None
    if args.skip_rsid:
        print("Step 3/4: Skipping dbSNP download (--skip-rsid)")
    else:
        print("Step 3/4: Downloading dbSNP (~15 GB, this takes a while)...")
        dbsnp_vcf = work_dir / "dbsnp.vcf.gz"
        dbsnp_tbi = work_dir / "dbsnp.vcf.gz.tbi"
        download_file(DBSNP_VCF_URL, dbsnp_vcf, "dbSNP VCF (~15 GB)")
        download_file(DBSNP_TBI_URL, dbsnp_tbi, "dbSNP index")

    # --- Step 4: Annotate ---
    print("Step 4/4: Annotating GIAB VCF (single pass)...")
    annotate_giab(giab_vcf, output_vcf, clinvar_vcf, dbsnp_vcf)

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
    print("GIAB NA12878 annotation complete!")
    print("=" * 50)
    print()
    print(f"Output: {output_vcf}")
    print(f"Index:  {output_vcf}.tbi")
    print()
    print("To run e2e tests:")
    print(f"  export GENECHAT_GIAB_VCF={output_vcf}")
    print("  uv run pytest tests/e2e/ -v")
    print()
    print("To use with Claude:")
    print(f"  export GENECHAT_VCF={output_vcf}")
    print()
    if args.skip_rsid:
        print(
            "NOTE: rsID lookups (e.g. 'tell me about rs4149056') won't work "
            "because dbSNP was skipped. Re-run without --skip-rsid to enable."
        )


if __name__ == "__main__":
    main()
