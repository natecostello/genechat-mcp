#!/bin/bash
# Update dbSNP rsID annotations on an existing annotated VCF.
# Fills missing rsIDs from a fresh dbSNP release (does not overwrite existing IDs).
#
# Usage: ./scripts/update_dbsnp.sh <annotated.vcf.gz> <dbsnp.vcf.gz>
#
# The dbSNP VCF may use RefSeq contig names (NC_000001.11) — the script
# auto-detects and renames to chr prefix if needed.
#
# Prerequisites: bcftools, tabix
# Output: Updates annotated.vcf.gz in place (with backup).
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <annotated.vcf.gz> <dbsnp.vcf.gz>" >&2
    exit 1
fi

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

# 1. Backup (VCF + index)
echo "Step 1: Backing up current VCF..."
cp "$ANNOTATED_VCF" "${ANNOTATED_VCF}.bak"
if [ -f "${ANNOTATED_VCF}.tbi" ]; then
    cp "${ANNOTATED_VCF}.tbi" "${ANNOTATED_VCF}.bak.tbi"
fi
if [ -f "${ANNOTATED_VCF}.csi" ]; then
    cp "${ANNOTATED_VCF}.csi" "${ANNOTATED_VCF}.bak.csi"
fi

# 2. dbSNP contig rename if needed
FIRST_CONTIG=$(bcftools view -h "$DBSNP_VCF" | grep "^##contig" | head -1 || true)
if echo "$FIRST_CONTIG" | grep -q "NC_"; then
    echo "Step 2: Renaming dbSNP RefSeq contigs to chr prefix..."
    CHR_MAP="$WORK_DIR/dbsnp_chr_rename.txt"
    # GRCh38 RefSeq accessions → chr names (explicit mapping; versions are not sequential)
    cat > "$CHR_MAP" <<'EOF'
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
EOF
    DBSNP_FIXED="$WORK_DIR/dbsnp_chrfixed.vcf.gz"
    bcftools annotate --rename-chrs "$CHR_MAP" "$DBSNP_VCF" -Oz -o "$DBSNP_FIXED"
    tabix -p vcf "$DBSNP_FIXED"
    rm -f "$CHR_MAP"
    DBSNP_USE="$DBSNP_FIXED"
elif echo "$FIRST_CONTIG" | grep -Eq "ID=[0-9]"; then
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

# 3. Annotate with dbSNP rsIDs (fills missing IDs only, preserves existing)
echo "Step 3: Annotating with dbSNP rsIDs..."
bcftools annotate -a "$DBSNP_USE" -c ID -i 'ID="."' \
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
