#!/bin/bash
# Update ClinVar annotations on an existing annotated VCF.
# Strips old ClinVar fields and re-annotates with a fresh ClinVar release.
#
# Usage: ./scripts/update_clinvar.sh <annotated.vcf.gz> <clinvar.vcf.gz>
#
# Prerequisites: bcftools, tabix
# Output: Updates annotated.vcf.gz in place (with backup).
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <annotated.vcf.gz> <clinvar.vcf.gz>" >&2
    exit 1
fi

ANNOTATED_VCF="$1"
CLINVAR_VCF="$2"

if [ ! -f "$ANNOTATED_VCF" ]; then
    echo "Error: Annotated VCF not found: $ANNOTATED_VCF"
    exit 1
fi
if [ ! -f "$CLINVAR_VCF" ]; then
    echo "Error: ClinVar VCF not found: $CLINVAR_VCF"
    exit 1
fi

WORK_DIR="$(dirname "$ANNOTATED_VCF")"
DATE=$(date +%Y-%m-%d)

echo "=== ClinVar Update ==="
echo "  Annotated VCF: $ANNOTATED_VCF"
echo "  ClinVar source: $CLINVAR_VCF"

# 1. Backup (VCF + index)
echo "Step 1: Backing up current VCF..."
cp "$ANNOTATED_VCF" "${ANNOTATED_VCF}.bak"
if [ -f "${ANNOTATED_VCF}.tbi" ]; then
    cp "${ANNOTATED_VCF}.tbi" "${ANNOTATED_VCF}.bak.tbi"
fi
if [ -f "${ANNOTATED_VCF}.csi" ]; then
    cp "${ANNOTATED_VCF}.csi" "${ANNOTATED_VCF}.bak.csi"
fi

# 2. Strip old ClinVar fields
echo "Step 2: Stripping old ClinVar annotations..."
bcftools annotate -x INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
    "$ANNOTATED_VCF" -Oz -o "$WORK_DIR/tmp_stripped.vcf.gz"

# 3. ClinVar contig rename if needed (bare 1,2,... → chr1,chr2,...)
FIRST_CONTIG=$(bcftools view -h "$CLINVAR_VCF" | grep "^##contig" | head -1 || true)
if echo "$FIRST_CONTIG" | grep -Eq "ID=[0-9]"; then
    echo "  Renaming ClinVar contigs to chr prefix..."
    CHR_MAP="$WORK_DIR/clinvar_chr_rename.txt"
    for i in $(seq 1 22); do echo "$i chr$i"; done > "$CHR_MAP"
    echo "X chrX" >> "$CHR_MAP"
    echo "Y chrY" >> "$CHR_MAP"
    echo "MT chrMT" >> "$CHR_MAP"
    CLINVAR_FIXED="$WORK_DIR/clinvar_chrfixed.vcf.gz"
    bcftools annotate --rename-chrs "$CHR_MAP" "$CLINVAR_VCF" -Oz -o "$CLINVAR_FIXED"
    tabix -p vcf "$CLINVAR_FIXED"
    rm -f "$CHR_MAP"
    CLINVAR_USE="$CLINVAR_FIXED"
else
    CLINVAR_USE="$CLINVAR_VCF"
fi

# 4. Re-annotate with fresh ClinVar
echo "Step 3: Annotating with fresh ClinVar..."
bcftools annotate -a "$CLINVAR_USE" \
    -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
    "$WORK_DIR/tmp_stripped.vcf.gz" -Oz -o "$WORK_DIR/tmp_annotated.vcf.gz"

# 5. Inject version header
echo "Step 4: Injecting version header..."
HEADER_FILE="$WORK_DIR/genechat_header.txt"
echo "##GeneChat_ClinVar=$DATE" > "$HEADER_FILE"
bcftools annotate -h "$HEADER_FILE" \
    "$WORK_DIR/tmp_annotated.vcf.gz" -Oz -o "$WORK_DIR/tmp_final.vcf.gz"
rm -f "$HEADER_FILE"

# 6. Atomic replace
echo "Step 5: Replacing VCF..."
mv "$WORK_DIR/tmp_final.vcf.gz" "$ANNOTATED_VCF"
tabix -p vcf "$ANNOTATED_VCF"

# 7. Cleanup
rm -f "$WORK_DIR/tmp_stripped.vcf.gz" "$WORK_DIR/tmp_annotated.vcf.gz"
rm -f "$WORK_DIR/clinvar_chrfixed.vcf.gz" "$WORK_DIR/clinvar_chrfixed.vcf.gz.tbi"

echo "Done. ClinVar updated to $DATE."
echo "Backup at: ${ANNOTATED_VCF}.bak"
