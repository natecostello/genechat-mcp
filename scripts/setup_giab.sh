#!/bin/bash
# setup_giab.sh — Download and annotate GIAB NA12878 (HG001) for GeneChat e2e testing
#
# NOTE: For a Python-only alternative that requires no external tools (no bcftools,
# Java, SnpEff), use setup_giab.py instead:
#
#   uv run python scripts/setup_giab.py [OUTPUT_DIR] [--skip-rsid]
#
# The Python setup provides ClinVar + dbSNP rsID annotation. This shell script
# additionally provides SnpEff functional annotation (ANN field) and optional
# gnomAD frequencies. See README.md for a comparison table.
#
# Usage:
#   bash scripts/setup_giab.sh [OUTPUT_DIR]
#
# Prerequisites:
#   - bcftools >= 1.17 (conda install -c bioconda bcftools)
#   - Java 8+ (for SnpEff/SnpSift)
#   - SnpEff/SnpSift >= 5.2 (https://pcingola.github.io/SnpEff/)
#   - htslib (bgzip, tabix — usually comes with bcftools)
#
# Optional environment variables:
#   GNOMAD_VCF   — Path to gnomAD af-only VCF for frequency annotation
#   SNPEFF_JAR   — Path to snpEff.jar (default: snpEff in PATH)
#   SNPSIFT_JAR  — Path to SnpSift.jar (default: SnpSift in PATH)
#
# Output: $OUTPUT_DIR/HG001_annotated.vcf.gz + .tbi (~5 GB downloads, ~30 min annotation)

set -euo pipefail

OUTPUT_DIR="${1:-./giab}"
mkdir -p "$OUTPUT_DIR"
WORK_DIR="$OUTPUT_DIR/work"
mkdir -p "$WORK_DIR"

# --- Helper functions ---

log() { echo "==> $(date '+%H:%M:%S') $*"; }

check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: '$1' not found in PATH. Please install it first."
        exit 1
    fi
}

download_if_missing() {
    local url="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        log "Already exists: $dest"
    else
        log "Downloading: $(basename "$dest")"
        curl -fSL --progress-bar -o "$dest" "$url"
    fi
}

# --- Check prerequisites ---

log "Checking prerequisites..."
check_cmd bcftools
check_cmd bgzip
check_cmd tabix
check_cmd java
check_cmd curl

# Determine SnpEff/SnpSift commands
if [ -n "${SNPEFF_JAR:-}" ]; then
    SNPEFF_CMD="java -Xmx4g -jar $SNPEFF_JAR"
else
    check_cmd snpEff
    SNPEFF_CMD="snpEff"
fi

if [ -n "${SNPSIFT_JAR:-}" ]; then
    SNPSIFT_CMD="java -Xmx4g -jar $SNPSIFT_JAR"
else
    check_cmd SnpSift
    SNPSIFT_CMD="SnpSift"
fi

log "All prerequisites found."

# --- Step 1: Download GIAB NA12878 VCF ---

GIAB_BASE="https://ftp-trace.ncbi.nlm.nih.gov/giab/ftp/release/NA12878_HG001/NISTv4.2.1/GRCh38"
GIAB_VCF="$WORK_DIR/HG001_raw.vcf.gz"
GIAB_TBI="$WORK_DIR/HG001_raw.vcf.gz.tbi"

log "Step 1/6: Downloading GIAB NA12878 v4.2.1 GRCh38..."
download_if_missing \
    "$GIAB_BASE/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz" \
    "$GIAB_VCF"
download_if_missing \
    "$GIAB_BASE/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz.tbi" \
    "$GIAB_TBI"

# --- Step 2: Fix chromosome prefixes (1 → chr1) ---

CHR_FIXED="$WORK_DIR/HG001_chrfixed.vcf.gz"
if [ -f "$CHR_FIXED" ]; then
    log "Step 2/6: Chromosome prefix fix already done."
else
    log "Step 2/6: Fixing chromosome prefixes (1 → chr1)..."
    CHR_MAP="$WORK_DIR/chr_rename.txt"
    for i in $(seq 1 22); do
        echo "$i chr$i"
    done > "$CHR_MAP"
    echo "X chrX" >> "$CHR_MAP"
    echo "Y chrY" >> "$CHR_MAP"
    echo "MT chrMT" >> "$CHR_MAP"

    bcftools annotate --rename-chrs "$CHR_MAP" "$GIAB_VCF" -Oz -o "$CHR_FIXED"
    tabix -p vcf "$CHR_FIXED"
    rm -f "$CHR_MAP"
fi

# --- Step 3: Download reference databases ---

log "Step 3/6: Downloading reference databases..."

# ClinVar VCF
CLINVAR_VCF="$WORK_DIR/clinvar.vcf.gz"
download_if_missing \
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz" \
    "$CLINVAR_VCF"
download_if_missing \
    "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi" \
    "$CLINVAR_VCF.tbi"

# dbSNP VCF (needed for rsID annotation — raw GIAB has '.' in ID column)
DBSNP_VCF="$WORK_DIR/dbsnp.vcf.gz"
download_if_missing \
    "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz" \
    "$DBSNP_VCF"
download_if_missing \
    "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz.tbi" \
    "$DBSNP_VCF.tbi"

# SnpEff database
log "Downloading SnpEff GRCh38 database (if not cached)..."
$SNPEFF_CMD download -v GRCh38.p14 || log "WARNING: SnpEff download may have failed. Continuing..."

# --- Step 4: SnpEff functional annotation ---

STEP1_VCF="$WORK_DIR/step1_snpeff.vcf"
if [ -f "$STEP1_VCF" ] || [ -f "$WORK_DIR/step2_dbsnp.vcf" ]; then
    log "Step 4/6: SnpEff annotation already done."
else
    log "Step 4/6: Running SnpEff functional annotation (this takes ~15 min)..."
    $SNPEFF_CMD ann -v GRCh38.p14 "$CHR_FIXED" > "$STEP1_VCF"
fi

# --- Step 5: dbSNP rsID annotation ---

STEP2_VCF="$WORK_DIR/step2_dbsnp.vcf"
if [ -f "$STEP2_VCF" ] || [ -f "$WORK_DIR/step3_clinvar.vcf" ]; then
    log "Step 5a/6: dbSNP annotation already done."
else
    log "Step 5a/6: Annotating rsIDs from dbSNP (this takes ~10 min)..."
    # dbSNP uses RefSeq contig names (NC_000001.11 etc.), need to remap
    # First check if dbSNP uses chr prefix or RefSeq names
    FIRST_CONTIG=$(bcftools view -h "$DBSNP_VCF" | grep "^##contig" | head -1 || true)
    if echo "$FIRST_CONTIG" | grep -q "NC_"; then
        # dbSNP uses RefSeq names — need chr-name mapping for SnpSift
        log "   dbSNP uses RefSeq contig names, creating mapping..."
        DBSNP_CHR_MAP="$WORK_DIR/dbsnp_chr_rename.txt"
        # Map RefSeq accessions to chr names
        cat > "$DBSNP_CHR_MAP" << 'CHRMAP'
NC_000001.11 chr1
NC_000002.12 chr2
NC_000003.12 chr3
NC_000004.12 chr4
NC_000005.10 chr5
NC_000006.12 chr6
NC_000007.14 chr7
NC_000008.11 chr8
NC_000009.12 chr9
NC_000010.11 chr10
NC_000011.10 chr11
NC_000012.12 chr12
NC_000013.11 chr13
NC_000014.9 chr14
NC_000015.10 chr15
NC_000016.10 chr16
NC_000017.11 chr17
NC_000018.10 chr18
NC_000019.10 chr19
NC_000020.11 chr20
NC_000021.9 chr21
NC_000022.11 chr22
NC_000023.11 chrX
NC_000024.10 chrY
NC_012920.1 chrMT
CHRMAP
        # Rename dbSNP contigs to match our VCF
        DBSNP_RENAMED="$WORK_DIR/dbsnp_chrfixed.vcf.gz"
        if [ ! -f "$DBSNP_RENAMED" ]; then
            log "   Renaming dbSNP contigs to chr prefix..."
            bcftools annotate --rename-chrs "$DBSNP_CHR_MAP" "$DBSNP_VCF" -Oz -o "$DBSNP_RENAMED"
            tabix -p vcf "$DBSNP_RENAMED"
        fi
        rm -f "$DBSNP_CHR_MAP"
        $SNPSIFT_CMD annotate -id "$DBSNP_RENAMED" "$STEP1_VCF" > "$STEP2_VCF"
    else
        $SNPSIFT_CMD annotate -id "$DBSNP_VCF" "$STEP1_VCF" > "$STEP2_VCF"
    fi
fi

# --- Step 5b: ClinVar annotation ---

STEP3_VCF="$WORK_DIR/step3_clinvar.vcf"
if [ -f "$STEP3_VCF" ]; then
    log "Step 5b/6: ClinVar annotation already done."
else
    log "Step 5b/6: Annotating with ClinVar..."
    $SNPSIFT_CMD annotate "$CLINVAR_VCF" "$STEP2_VCF" > "$STEP3_VCF"
fi

# --- Step 5c: Optional gnomAD annotation ---

FINAL_VCF="$WORK_DIR/annotated.vcf"
if [ -n "${GNOMAD_VCF:-}" ] && [ -f "${GNOMAD_VCF}" ]; then
    log "Step 5c/6: Annotating with gnomAD frequencies..."
    $SNPSIFT_CMD annotate -info AF,AF_popmax "$GNOMAD_VCF" "$STEP3_VCF" > "$FINAL_VCF"
else
    log "Step 5c/6: Skipping gnomAD (GNOMAD_VCF not set). Copying ClinVar output..."
    cp "$STEP3_VCF" "$FINAL_VCF"
fi

# --- Step 6: Compress, index, and finalize ---

OUTPUT_VCF="$OUTPUT_DIR/HG001_annotated.vcf.gz"
if [ -f "$OUTPUT_VCF" ]; then
    log "Step 6/6: Output already exists: $OUTPUT_VCF"
else
    log "Step 6/6: Compressing and indexing final VCF..."
    bgzip -c "$FINAL_VCF" > "$OUTPUT_VCF"
    tabix -p vcf "$OUTPUT_VCF"
fi

# --- Cleanup intermediate files (optional) ---

log "Cleaning up intermediate files..."
rm -f "$STEP1_VCF" "$STEP2_VCF" "$STEP3_VCF" "$FINAL_VCF"

# --- Done ---

echo ""
log "============================================"
log "GIAB NA12878 annotation complete!"
log "============================================"
echo ""
echo "Output: $OUTPUT_VCF"
echo "Index:  $OUTPUT_VCF.tbi"
echo ""
echo "To run e2e tests:"
echo "  export GENECHAT_GIAB_VCF=$OUTPUT_VCF"
echo "  uv run pytest tests/e2e/ -v"
echo ""
echo "To run fast tests only (no full-VCF scans):"
echo "  uv run pytest tests/e2e/ -v -m 'not slow'"
