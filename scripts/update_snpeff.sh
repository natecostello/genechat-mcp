#!/bin/bash
# Update SnpEff functional annotations on an existing annotated VCF.
# Strips old ANN field and re-runs SnpEff (per-chromosome to avoid OOM).
#
# Usage: ./scripts/update_snpeff.sh <annotated.vcf.gz>
#
# Optional environment variables:
#   SNPEFF_DB — SnpEff database name (auto-detected if not set)
#
# Prerequisites: bcftools, tabix, snpEff, bgzip
# Output: Updates annotated.vcf.gz in place (with backup).
set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <annotated.vcf.gz>" >&2
    exit 1
fi

for cmd in bcftools tabix snpEff bgzip; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: Required command '$cmd' not found in PATH" >&2
        exit 1
    fi
done

ANNOTATED_VCF="$1"

if [ ! -f "$ANNOTATED_VCF" ]; then
    echo "Error: Annotated VCF not found: $ANNOTATED_VCF"
    exit 1
fi

WORK_DIR="$(dirname "$ANNOTATED_VCF")"
DATE=$(date +%Y-%m-%d)

# Auto-detect SnpEff database
if [ -z "${SNPEFF_DB:-}" ]; then
    SNPEFF_VERSION=$(snpEff -version 2>&1 | head -1 || true)
    if echo "$SNPEFF_VERSION" | grep -q "4\.3"; then
        SNPEFF_DB="GRCh38.86"
    else
        SNPEFF_DB="GRCh38.p14"
    fi
    echo "Auto-detected SnpEff database: $SNPEFF_DB"
fi

echo "=== SnpEff Update ==="
echo "  Annotated VCF: $ANNOTATED_VCF"
echo "  Database: $SNPEFF_DB"

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

# 2. Strip old ANN field
echo "Step 2: Stripping old SnpEff annotations..."
bcftools annotate -x INFO/ANN \
    "$ANNOTATED_VCF" -Oz -o "$WORK_DIR/tmp_stripped.vcf.gz"
tabix -p vcf "$WORK_DIR/tmp_stripped.vcf.gz"

# 3. Per-chromosome SnpEff annotation
echo "Step 3: Running SnpEff per-chromosome..."
mapfile -t CHROMS < <(bcftools view -h "$WORK_DIR/tmp_stripped.vcf.gz" \
    | grep "^##contig" | sed 's/.*ID=\([^,>]*\).*/\1/' \
    | grep -E '^[A-Za-z0-9._-]+$')

SNPEFF_WORK="$WORK_DIR/snpeff_work"
mkdir -p "$SNPEFF_WORK"
CHR_FILES=()
for CHR in "${CHROMS[@]}"; do
    echo "  SnpEff annotating $CHR..."
    CHR_OUT="$SNPEFF_WORK/${CHR}_ann.vcf.gz"
    bcftools view -r "$CHR" "$WORK_DIR/tmp_stripped.vcf.gz" \
        | snpEff ann "$SNPEFF_DB" - \
        | bgzip > "$CHR_OUT"
    CHR_FILES+=("$CHR_OUT")
done

# 4. Concat per-chromosome results
echo "Step 4: Concatenating results..."
bcftools concat "${CHR_FILES[@]}" -Oz -o "$WORK_DIR/tmp_annotated.vcf.gz"

# 5. Inject version header
echo "Step 5: Injecting version header..."
HEADER_FILE="$WORK_DIR/genechat_header.txt"
echo "##GeneChat_SnpEff=${SNPEFF_DB}_${DATE}" > "$HEADER_FILE"
bcftools annotate -h "$HEADER_FILE" \
    "$WORK_DIR/tmp_annotated.vcf.gz" -Oz -o "$WORK_DIR/tmp_final.vcf.gz"
rm -f "$HEADER_FILE"

# 6. Atomic replace
echo "Step 6: Replacing VCF..."
mv "$WORK_DIR/tmp_final.vcf.gz" "$ANNOTATED_VCF"
tabix -p vcf "$ANNOTATED_VCF"

# 7. Cleanup
rm -f \
    "$WORK_DIR/tmp_stripped.vcf.gz" \
    "$WORK_DIR/tmp_stripped.vcf.gz.tbi" \
    "$WORK_DIR/tmp_stripped.vcf.gz.csi" \
    "$WORK_DIR/tmp_annotated.vcf.gz" \
    "$WORK_DIR/tmp_annotated.vcf.gz.tbi" \
    "$WORK_DIR/tmp_annotated.vcf.gz.csi"
rm -rf "$SNPEFF_WORK"

echo "Done. SnpEff updated ($SNPEFF_DB, $DATE)."
echo "Backup at: ${ANNOTATED_VCF}.${BACKUP_SUFFIX}"
