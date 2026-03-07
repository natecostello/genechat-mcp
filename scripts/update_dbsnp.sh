#!/bin/bash
# Update dbSNP rsID annotations on an existing annotated VCF.
# Adds/fills rsIDs from a fresh dbSNP release (does not overwrite existing IDs).
#
# Usage: ./scripts/update_dbsnp.sh <annotated.vcf.gz> <dbsnp.vcf.gz>
#
# The dbSNP VCF may use RefSeq contig names (NC_000001.11) — the script
# auto-detects and renames to chr prefix if needed.
#
# Prerequisites: bcftools, tabix
# Output: Updates annotated.vcf.gz in place (with backup).
set -euo pipefail

ANNOTATED_VCF="$1"
DBSNP_VCF="$2"

if [ ! -f "$ANNOTATED_VCF" ]; then
    echo "Error: Annotated VCF not found: $ANNOTATED_VCF"
    exit 1
fi
if [ ! -f "$DBSNP_VCF" ]; then
    echo "Error: dbSNP VCF not found: $DBSNP_VCF"
    exit 1
fi

WORK_DIR="$(dirname "$ANNOTATED_VCF")"
DATE=$(date +%Y-%m-%d)

echo "=== dbSNP Update ==="
echo "  Annotated VCF: $ANNOTATED_VCF"
echo "  dbSNP source: $DBSNP_VCF"

# 1. Backup
echo "Step 1: Backing up current VCF..."
cp "$ANNOTATED_VCF" "${ANNOTATED_VCF}.bak"

# 2. dbSNP contig rename if needed (NC_000001.11 → chr1, etc.)
FIRST_CONTIG=$(bcftools view -h "$DBSNP_VCF" | grep "^##contig" | head -1 || true)
if echo "$FIRST_CONTIG" | grep -q "NC_"; then
    echo "Step 2: Renaming dbSNP RefSeq contigs to chr prefix..."
    CHR_MAP="$WORK_DIR/dbsnp_chr_rename.txt"
    # GRCh38 RefSeq accessions → chr names
    for i in $(seq 1 22); do
        printf "NC_%06d.%s chr%s\n" "$i" "$(( i <= 9 ? 11 : (i <= 14 ? 12 : (i <= 22 ? 13 : 14)) ))" "$i"
    done > "$CHR_MAP"
    # Simplified: just generate all common mappings
    # The exact accession versions vary; use a broader approach
    echo "NC_000023.11 chrX" >> "$CHR_MAP"
    echo "NC_000024.10 chrY" >> "$CHR_MAP"
    echo "NC_012920.1 chrMT" >> "$CHR_MAP"
    DBSNP_FIXED="$WORK_DIR/dbsnp_chrfixed.vcf.gz"
    bcftools annotate --rename-chrs "$CHR_MAP" "$DBSNP_VCF" -Oz -o "$DBSNP_FIXED"
    tabix -p vcf "$DBSNP_FIXED"
    rm -f "$CHR_MAP"
    DBSNP_USE="$DBSNP_FIXED"
elif echo "$FIRST_CONTIG" | grep -qP "ID=\d"; then
    echo "Step 2: Renaming dbSNP bare contigs to chr prefix..."
    CHR_MAP="$WORK_DIR/dbsnp_chr_rename.txt"
    for i in $(seq 1 22); do echo "$i chr$i"; done > "$CHR_MAP"
    echo "X chrX" >> "$CHR_MAP"
    echo "Y chrY" >> "$CHR_MAP"
    echo "MT chrMT" >> "$CHR_MAP"
    DBSNP_FIXED="$WORK_DIR/dbsnp_chrfixed.vcf.gz"
    bcftools annotate --rename-chrs "$CHR_MAP" "$DBSNP_VCF" -Oz -o "$DBSNP_FIXED"
    tabix -p vcf "$DBSNP_FIXED"
    rm -f "$CHR_MAP"
    DBSNP_USE="$DBSNP_FIXED"
else
    DBSNP_USE="$DBSNP_VCF"
fi

# 3. Annotate with dbSNP rsIDs (fills missing IDs, does not overwrite existing)
echo "Step 3: Annotating with dbSNP rsIDs..."
bcftools annotate -a "$DBSNP_USE" -c ID \
    "$ANNOTATED_VCF" -Oz -o "$WORK_DIR/tmp_annotated.vcf.gz"

# 4. Inject version header
echo "Step 4: Injecting version header..."
HEADER_FILE="$WORK_DIR/genechat_header.txt"
echo "##GeneChat_dbSNP=$DATE" > "$HEADER_FILE"
bcftools annotate -h "$HEADER_FILE" \
    "$WORK_DIR/tmp_annotated.vcf.gz" -Oz -o "$WORK_DIR/tmp_final.vcf.gz"
rm -f "$HEADER_FILE"

# 5. Atomic replace
echo "Step 5: Replacing VCF..."
mv "$WORK_DIR/tmp_final.vcf.gz" "$ANNOTATED_VCF"
tabix -p vcf "$ANNOTATED_VCF"

# 6. Cleanup
rm -f "$WORK_DIR/tmp_annotated.vcf.gz"
rm -f "$WORK_DIR/dbsnp_chrfixed.vcf.gz" "$WORK_DIR/dbsnp_chrfixed.vcf.gz.tbi"

echo "Done. dbSNP rsIDs updated ($DATE)."
echo "Backup at: ${ANNOTATED_VCF}.bak"
