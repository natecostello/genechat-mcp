#!/bin/bash
# Update gnomAD frequency annotations on an existing annotated VCF.
# Strips old AF fields and re-annotates from per-chromosome gnomAD exome VCFs.
#
# Usage: GNOMAD_DIR=/path/to/gnomad_exomes_v4 ./scripts/update_gnomad.sh <annotated.vcf.gz>
#
# Environment variables:
#   GNOMAD_DIR — Directory containing per-chromosome gnomAD v4 exome VCFs (required)
#   GNOMAD_VERSION — Version string for header (default: auto-detected from filenames)
#
# Prerequisites: bcftools, tabix
# Output: Updates annotated.vcf.gz in place (with backup).
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: GNOMAD_DIR=/path/to/gnomad_exomes_v4 $0 <annotated.vcf.gz>" >&2
    exit 1
fi

ANNOTATED_VCF="$1"

if [ ! -f "$ANNOTATED_VCF" ]; then
    echo "Error: Annotated VCF not found: $ANNOTATED_VCF"
    exit 1
fi
if [ -z "${GNOMAD_DIR:-}" ] || [ ! -d "${GNOMAD_DIR}" ]; then
    echo "Error: Set GNOMAD_DIR to the directory containing per-chromosome gnomAD VCFs"
    exit 1
fi

WORK_DIR="$(dirname "$ANNOTATED_VCF")"

# Auto-detect GNOMAD_VERSION from a representative VCF filename if not provided
if [ -z "${GNOMAD_VERSION:-}" ]; then
    SAMPLE_FILE="$(find "$GNOMAD_DIR" -maxdepth 1 -type f -name '*.vcf.*' 2>/dev/null | head -n 1 || true)"
    if [ -n "$SAMPLE_FILE" ]; then
        SAMPLE_BASENAME="$(basename "$SAMPLE_FILE")"
        DETECTED_VERSION="$(printf '%s\n' "$SAMPLE_BASENAME" | sed -n 's/.*\(v[0-9][0-9]*\(\.[0-9][0-9]*\)*\).*/\1/p' | head -n 1)"
        if [ -n "$DETECTED_VERSION" ]; then
            GNOMAD_VERSION="$DETECTED_VERSION"
        else
            GNOMAD_VERSION="unknown"
        fi
    else
        GNOMAD_VERSION="unknown"
    fi
fi

DATE=$(date +%Y-%m-%d)

echo "=== gnomAD Update ==="
echo "  Annotated VCF: $ANNOTATED_VCF"
echo "  gnomAD source: $GNOMAD_DIR"
echo "  gnomAD version: $GNOMAD_VERSION"

# 1. Backup (VCF + index) with timestamp to preserve history
BACKUP_SUFFIX="bak.$(date +%Y%m%d_%H%M%S)"
echo "Step 1: Backing up current VCF..."
cp "$ANNOTATED_VCF" "${ANNOTATED_VCF}.${BACKUP_SUFFIX}"
if [ -f "${ANNOTATED_VCF}.tbi" ]; then
    cp "${ANNOTATED_VCF}.tbi" "${ANNOTATED_VCF}.${BACKUP_SUFFIX}.tbi"
fi
if [ -f "${ANNOTATED_VCF}.csi" ]; then
    cp "${ANNOTATED_VCF}.csi" "${ANNOTATED_VCF}.${BACKUP_SUFFIX}.csi"
fi

# 2. Strip old frequency fields
echo "Step 2: Stripping old AF annotations..."
bcftools annotate -x INFO/AF,INFO/AF_grpmax,INFO/AF_popmax \
    "$ANNOTATED_VCF" -Oz -o "$WORK_DIR/tmp_stripped.vcf.gz"

# 3. Inject AF headers
AF_HEADERS="$WORK_DIR/gnomad_headers.txt"
echo '##INFO=<ID=AF,Number=A,Type=Float,Description="Alternate allele frequency">' > "$AF_HEADERS"
echo '##INFO=<ID=AF_grpmax,Number=A,Type=Float,Description="Maximum allele frequency across genetic ancestry groups">' >> "$AF_HEADERS"
bcftools annotate -h "$AF_HEADERS" "$WORK_DIR/tmp_stripped.vcf.gz" -Oz -o "$WORK_DIR/tmp_with_headers.vcf.gz"
tabix -p vcf "$WORK_DIR/tmp_with_headers.vcf.gz"
rm -f "$AF_HEADERS"

# 4. Per-chromosome gnomAD annotation
echo "Step 3: Annotating per-chromosome with gnomAD..."
mapfile -t CHROMS < <(bcftools view -h "$WORK_DIR/tmp_with_headers.vcf.gz" \
    | grep "^##contig" | sed 's/.*ID=\([^,>]*\).*/\1/' \
    | grep -E '^[A-Za-z0-9._-]+$')

GNOMAD_WORK="$WORK_DIR/gnomad_work"
mkdir -p "$GNOMAD_WORK"
CHR_FILES=()
for CHR in "${CHROMS[@]}"; do
    # Find gnomAD file for this chromosome (supports any version/naming)
    GNOMAD_CHR_VCF="$(find "$GNOMAD_DIR" -maxdepth 1 -type f \
        -name "*sites.${CHR}.vcf.*" ! -name "*.tbi" ! -name "*.csi" 2>/dev/null | head -n 1 || true)"
    CHR_OUT="$GNOMAD_WORK/${CHR}.vcf.gz"
    if [ -n "$GNOMAD_CHR_VCF" ] && [ -f "$GNOMAD_CHR_VCF" ]; then
        # Ensure gnomAD VCF is indexed for bcftools annotate -a
        if [ ! -f "${GNOMAD_CHR_VCF}.tbi" ] && [ ! -f "${GNOMAD_CHR_VCF}.csi" ]; then
            echo "  Indexing gnomAD $CHR VCF..."
            tabix -p vcf "$GNOMAD_CHR_VCF"
        fi
        echo "  Annotating $CHR with gnomAD..."
        bcftools annotate -a "$GNOMAD_CHR_VCF" \
            -c INFO/AF,INFO/AF_grpmax \
            <(bcftools view -r "$CHR" "$WORK_DIR/tmp_with_headers.vcf.gz") \
            -Oz -o "$CHR_OUT"
    else
        echo "  No gnomAD file for $CHR, passing through."
        bcftools view -r "$CHR" "$WORK_DIR/tmp_with_headers.vcf.gz" -Oz -o "$CHR_OUT"
    fi
    CHR_FILES+=("$CHR_OUT")
done
bcftools concat "${CHR_FILES[@]}" -Oz -o "$WORK_DIR/tmp_annotated.vcf.gz"

# 5. Inject version header
echo "Step 4: Injecting version header..."
HEADER_FILE="$WORK_DIR/genechat_header.txt"
echo "##GeneChat_gnomAD=${GNOMAD_VERSION}_${DATE}" > "$HEADER_FILE"
bcftools annotate -h "$HEADER_FILE" \
    "$WORK_DIR/tmp_annotated.vcf.gz" -Oz -o "$WORK_DIR/tmp_final.vcf.gz"
rm -f "$HEADER_FILE"

# 6. Atomic replace
echo "Step 5: Replacing VCF..."
mv "$WORK_DIR/tmp_final.vcf.gz" "$ANNOTATED_VCF"
tabix -p vcf "$ANNOTATED_VCF"

# 7. Cleanup
rm -f "$WORK_DIR/tmp_stripped.vcf.gz" "$WORK_DIR/tmp_with_headers.vcf.gz" "$WORK_DIR/tmp_with_headers.vcf.gz.tbi"
rm -f "$WORK_DIR/tmp_annotated.vcf.gz"
rm -rf "$GNOMAD_WORK"

echo "Done. gnomAD updated ($GNOMAD_VERSION, $DATE)."
echo "Backup at: ${ANNOTATED_VCF}.${BACKUP_SUFFIX}"
