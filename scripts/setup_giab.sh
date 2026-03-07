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
#   macOS:  brew install bcftools brewsci/bio/snpeff
#   Linux:  conda install -c bioconda bcftools snpeff
#   Manual: bcftools >= 1.17, Java 8+, SnpEff >= 4.3
#
# Optional environment variables:
#   SNPEFF_DB    — SnpEff database name (default: auto-detect)
#                  brew SnpEff 4.3t → GRCh38.86, SnpEff 5.x → GRCh38.p14
#   JAVA_MEM     — Java heap size for SnpEff (default: -Xmx4g)
#   GNOMAD_DIR   — Directory of per-chromosome gnomAD v4 exome VCFs (preferred)
#   GNOMAD_VCF   — Path to single gnomAD af-only VCF for frequency annotation (legacy)
#   SNPEFF_JAR   — Path to snpEff.jar (default: snpEff in PATH)
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
# Per-chromosome annotation needs ~4 GB heap. Override with JAVA_MEM env var.
JAVA_MEM="${JAVA_MEM:--Xmx4g}"
if [ -n "${SNPEFF_JAR:-}" ]; then
    SNPEFF_CMD="java $JAVA_MEM -jar $SNPEFF_JAR"
else
    check_cmd snpEff
    SNPEFF_CMD="snpEff $JAVA_MEM"
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

# SnpEff database — auto-detect name if not specified
if [ -z "${SNPEFF_DB:-}" ]; then
    SNPEFF_VERSION=$($SNPEFF_CMD -version 2>&1 | head -1 || true)
    if echo "$SNPEFF_VERSION" | grep -q "4\.3"; then
        SNPEFF_DB="GRCh38.86"
    else
        SNPEFF_DB="GRCh38.p14"
    fi
    log "Auto-detected SnpEff database: $SNPEFF_DB (version: $SNPEFF_VERSION)"
fi

# Download SnpEff database if not already installed (no-op if present)
log "Ensuring SnpEff $SNPEFF_DB database is available..."
$SNPEFF_CMD download -v "$SNPEFF_DB" || log "WARNING: SnpEff download may have failed. Continuing..."

# --- Step 4: SnpEff functional annotation (per-chromosome) ---
#
# SnpEff loads chromosome sequences cumulatively and never releases them,
# causing OOM on whole-genome VCFs. We split by chromosome, annotate each
# independently (fresh JVM per chromosome), then concatenate. If any
# chromosome fails, only that one needs to be re-run.

SNPEFF_DIR="$WORK_DIR/snpeff_by_chr"
STEP1_VCF="$WORK_DIR/step1_snpeff.vcf.gz"

if [ -f "$STEP1_VCF" ] || [ -f "$WORK_DIR/step2_dbsnp.vcf.gz" ]; then
    log "Step 4/6: SnpEff annotation already done."
else
    mkdir -p "$SNPEFF_DIR"
    CHROMS="chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10 chr11 chr12 chr13 chr14 chr15 chr16 chr17 chr18 chr19 chr20 chr21 chr22 chrX"
    TOTAL=$(echo $CHROMS | wc -w | tr -d ' ')
    COUNT=0

    STEP4_START=$(date +%s)
    for CHR in $CHROMS; do
        COUNT=$((COUNT + 1))
        CHR_OUT="$SNPEFF_DIR/${CHR}_snpeff.vcf.gz"
        if [ -f "$CHR_OUT" ]; then
            log "Step 4/6: [$COUNT/$TOTAL] $CHR already annotated, skipping."
            continue
        fi
        log "Step 4/6: [$COUNT/$TOTAL] Annotating $CHR..."
        CHR_START=$(date +%s)
        bcftools view -r "$CHR" "$CHR_FIXED" \
            | $SNPEFF_CMD ann "$SNPEFF_DB" \
            | bgzip -c > "${CHR_OUT}.tmp"
        mv "${CHR_OUT}.tmp" "$CHR_OUT"
        CHR_ELAPSED=$(( $(date +%s) - CHR_START ))
        log "Step 4/6: [$COUNT/$TOTAL] $CHR done in ${CHR_ELAPSED}s"
    done
    STEP4_ELAPSED=$(( $(date +%s) - STEP4_START ))
    log "Step 4/6: All chromosomes annotated in ${STEP4_ELAPSED}s"

    # Concatenate all chromosomes
    log "Step 4/6: Concatenating per-chromosome results..."
    CHR_FILES=""
    for CHR in $CHROMS; do
        CHR_FILES="$CHR_FILES $SNPEFF_DIR/${CHR}_snpeff.vcf.gz"
    done
    bcftools concat $CHR_FILES -Oz -o "$STEP1_VCF"
    tabix -p vcf "$STEP1_VCF"
    log "Step 4/6: SnpEff annotation complete."
fi

# --- Step 5: dbSNP rsID annotation ---

STEP2_VCF="$WORK_DIR/step2_dbsnp.vcf.gz"
if [ -f "$STEP2_VCF" ] || [ -f "$WORK_DIR/step3_clinvar.vcf.gz" ]; then
    log "Step 5a/6: dbSNP annotation already done."
else
    log "Step 5a/6: Annotating rsIDs from dbSNP..."
    STEP5A_START=$(date +%s)
    # dbSNP uses RefSeq contig names (NC_000001.11 etc.), need to remap
    # First check if dbSNP uses chr prefix or RefSeq names
    FIRST_CONTIG=$(bcftools view -h "$DBSNP_VCF" | grep "^##contig" | head -1 || true)
    if echo "$FIRST_CONTIG" | grep -q "NC_"; then
        # dbSNP uses RefSeq names — need chr-name mapping
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
            bcftools annotate --rename-chrs "$DBSNP_CHR_MAP" "$DBSNP_VCF" -Oz -o "${DBSNP_RENAMED}.tmp"
            mv "${DBSNP_RENAMED}.tmp" "$DBSNP_RENAMED"
            tabix -p vcf "$DBSNP_RENAMED"
        fi
        rm -f "$DBSNP_CHR_MAP"
        # Use bcftools annotate (not SnpSift) for rsID — much faster, avoids
        # SnpSift 4.3t CLNHGVS parsing errors with modern dbSNP/ClinVar.
        bcftools annotate -a "$DBSNP_RENAMED" -c ID "$STEP1_VCF" -Oz -o "${STEP2_VCF}.tmp"
    else
        bcftools annotate -a "$DBSNP_VCF" -c ID "$STEP1_VCF" -Oz -o "${STEP2_VCF}.tmp"
    fi
    mv "${STEP2_VCF}.tmp" "$STEP2_VCF"
    tabix -p vcf "$STEP2_VCF"
    STEP5A_ELAPSED=$(( $(date +%s) - STEP5A_START ))
    log "Step 5a/6: dbSNP annotation done in ${STEP5A_ELAPSED}s"
fi

# --- Step 5b: ClinVar annotation ---
# Use bcftools annotate (not SnpSift) to avoid CLNHGVS parsing errors with SnpSift 4.3t.

STEP3_VCF="$WORK_DIR/step3_clinvar.vcf.gz"
if [ -f "$STEP3_VCF" ]; then
    log "Step 5b/6: ClinVar annotation already done."
else
    log "Step 5b/6: Annotating with ClinVar..."
    STEP5B_START=$(date +%s)
    # ClinVar uses bare chromosome names (1, 2, ...) — rename to chr prefix
    CLINVAR_RENAMED="$WORK_DIR/clinvar_chrfixed.vcf.gz"
    if [ ! -f "$CLINVAR_RENAMED" ]; then
        log "   Renaming ClinVar contigs to chr prefix..."
        CLINVAR_CHR_MAP="$WORK_DIR/clinvar_chr_rename.txt"
        for i in $(seq 1 22); do
            echo "$i chr$i"
        done > "$CLINVAR_CHR_MAP"
        echo "X chrX" >> "$CLINVAR_CHR_MAP"
        echo "Y chrY" >> "$CLINVAR_CHR_MAP"
        echo "MT chrMT" >> "$CLINVAR_CHR_MAP"
        bcftools annotate --rename-chrs "$CLINVAR_CHR_MAP" "$CLINVAR_VCF" -Oz -o "${CLINVAR_RENAMED}.tmp"
        mv "${CLINVAR_RENAMED}.tmp" "$CLINVAR_RENAMED"
        tabix -p vcf "$CLINVAR_RENAMED"
        rm -f "$CLINVAR_CHR_MAP"
    fi
    bcftools annotate -a "$CLINVAR_RENAMED" \
        -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
        "$STEP2_VCF" -Oz -o "${STEP3_VCF}.tmp"
    mv "${STEP3_VCF}.tmp" "$STEP3_VCF"
    tabix -p vcf "$STEP3_VCF"
    STEP5B_ELAPSED=$(( $(date +%s) - STEP5B_START ))
    log "Step 5b/6: ClinVar annotation done in ${STEP5B_ELAPSED}s"
fi

# --- Step 5c: Optional gnomAD annotation ---

FINAL_VCF="$WORK_DIR/annotated.vcf.gz"
if [ -n "${GNOMAD_DIR:-}" ] && [ -d "${GNOMAD_DIR}" ]; then
    # Per-chromosome gnomAD v4 exome annotation
    log "Step 5c/6: Annotating with per-chromosome gnomAD exomes from: $GNOMAD_DIR"
    STEP5C_START=$(date +%s)
    # Inject AF/AF_grpmax headers so all per-chrom outputs share the same header
    AF_HEADERS="$WORK_DIR/gnomad_headers.txt"
    echo '##INFO=<ID=AF,Number=A,Type=Float,Description="Alternate allele frequency">' > "$AF_HEADERS"
    echo '##INFO=<ID=AF_grpmax,Number=A,Type=Float,Description="Maximum allele frequency across genetic ancestry groups">' >> "$AF_HEADERS"
    STEP3_WITH_HEADERS="$WORK_DIR/step3_with_headers.vcf.gz"
    bcftools annotate -h "$AF_HEADERS" "$STEP3_VCF" -Oz -o "$STEP3_WITH_HEADERS"
    tabix -p vcf "$STEP3_WITH_HEADERS"
    rm -f "$AF_HEADERS"

    # Extract contig IDs and validate (only allow alphanumeric, underscore, dash, dot)
    GNOMAD_WORK="$WORK_DIR/gnomad_work"
    mkdir -p "$GNOMAD_WORK"
    mapfile -t VCF_CHROMS < <(bcftools view -h "$STEP3_WITH_HEADERS" \
        | grep "^##contig" | sed 's/.*ID=\([^,>]*\).*/\1/' \
        | grep -E '^[A-Za-z0-9._-]+$')
    CHR_FILES=()
    for CHR in "${VCF_CHROMS[@]}"; do
        GNOMAD_CHR_VCF="$GNOMAD_DIR/gnomad.exomes.v4.1.sites.${CHR}.vcf.bgz"
        CHR_OUT="$GNOMAD_WORK/${CHR}.vcf.gz"
        if [ -f "$GNOMAD_CHR_VCF" ]; then
            log "   Annotating $CHR with gnomAD..."
            bcftools annotate -a "$GNOMAD_CHR_VCF" \
                -c INFO/AF,INFO/AF_grpmax \
                <(bcftools view -r "$CHR" "$STEP3_WITH_HEADERS") \
                -Oz -o "$CHR_OUT"
        else
            log "   No gnomAD file for $CHR, passing through."
            bcftools view -r "$CHR" "$STEP3_WITH_HEADERS" -Oz -o "$CHR_OUT"
        fi
        CHR_FILES+=("$CHR_OUT")
    done
    bcftools concat "${CHR_FILES[@]}" -Oz -o "${FINAL_VCF}.tmp"
    mv "${FINAL_VCF}.tmp" "$FINAL_VCF"
    tabix -p vcf "$FINAL_VCF"
    rm -rf "$GNOMAD_WORK"
    rm -f "$STEP3_WITH_HEADERS" "$STEP3_WITH_HEADERS.tbi"
    STEP5C_ELAPSED=$(( $(date +%s) - STEP5C_START ))
    log "Step 5c/6: gnomAD annotation done in ${STEP5C_ELAPSED}s"
elif [ -n "${GNOMAD_VCF:-}" ] && [ -f "${GNOMAD_VCF}" ]; then
    log "Step 5c/6: Annotating with gnomAD frequencies (single VCF)..."
    bcftools annotate -a "$GNOMAD_VCF" \
        -c INFO/AF,INFO/AF_popmax \
        "$STEP3_VCF" -Oz -o "${FINAL_VCF}.tmp"
    mv "${FINAL_VCF}.tmp" "$FINAL_VCF"
    tabix -p vcf "$FINAL_VCF"
else
    log "Step 5c/6: Skipping gnomAD (neither GNOMAD_DIR nor GNOMAD_VCF set). Copying ClinVar output..."
    cp "$STEP3_VCF" "$FINAL_VCF"
    cp "$STEP3_VCF.tbi" "$FINAL_VCF.tbi" 2>/dev/null || tabix -p vcf "$FINAL_VCF"
fi

# --- Step 6: Finalize ---

OUTPUT_VCF="$OUTPUT_DIR/HG001_annotated.vcf.gz"
if [ -f "$OUTPUT_VCF" ]; then
    log "Step 6/6: Output already exists: $OUTPUT_VCF"
else
    log "Step 6/6: Copying final VCF to output..."
    cp "$FINAL_VCF" "$OUTPUT_VCF"
    cp "$FINAL_VCF.tbi" "$OUTPUT_VCF.tbi" 2>/dev/null || tabix -p vcf "$OUTPUT_VCF"
fi

# --- Cleanup intermediate and raw download files ---

log "Cleaning up work directory..."
if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" && "$WORK_DIR" == "$OUTPUT_DIR"/work ]]; then
    rm -rf "$WORK_DIR"
else
    log "Skipping cleanup: WORK_DIR ('$WORK_DIR') did not pass safety checks"
fi

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
