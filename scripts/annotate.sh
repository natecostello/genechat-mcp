#!/bin/bash
# One-time VCF annotation pipeline: SnpEff → ClinVar → gnomAD
# Usage: ./scripts/annotate.sh input.vcf.gz [output_dir]
#
# Prerequisites:
#   macOS:  brew install bcftools brewsci/bio/snpeff
#   Linux:  conda install -c bioconda bcftools snpeff
#   Also:   CLINVAR_VCF and GNOMAD_VCF env vars pointing to reference VCFs
#
# Optional: SNPEFF_DB — SnpEff database name (auto-detected if not set)
set -euo pipefail

INPUT_VCF="$1"
OUTPUT_DIR="${2:-.}"

if [ ! -f "$INPUT_VCF" ]; then
    echo "Error: Input VCF not found: $INPUT_VCF"
    exit 1
fi

if [ -z "${CLINVAR_VCF:-}" ]; then
    echo "Error: Set CLINVAR_VCF environment variable to ClinVar VCF path"
    exit 1
fi

if [ -z "${GNOMAD_VCF:-}" ]; then
    echo "Error: Set GNOMAD_VCF environment variable to gnomAD VCF path"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Auto-detect SnpEff database if not specified
if [ -z "${SNPEFF_DB:-}" ]; then
    SNPEFF_VERSION=$(snpEff -version 2>&1 | head -1 || true)
    if echo "$SNPEFF_VERSION" | grep -q "4\.3"; then
        SNPEFF_DB="GRCh38.86"
    else
        SNPEFF_DB="GRCh38.p14"
    fi
    echo "Auto-detected SnpEff database: $SNPEFF_DB"
fi

echo "Step 1: SnpEff functional annotation..."
snpEff ann -v "$SNPEFF_DB" "$INPUT_VCF" > "$OUTPUT_DIR/step1_snpeff.vcf"

echo "Step 2: ClinVar annotation..."
# ClinVar may use bare contig names (1, 2, ...) — check and rename if needed
FIRST_CONTIG=$(bcftools view -h "$CLINVAR_VCF" | grep "^##contig" | head -1 || true)
if echo "$FIRST_CONTIG" | grep -qP "ID=\d"; then
    echo "  Renaming ClinVar contigs to chr prefix..."
    CHR_MAP="$OUTPUT_DIR/clinvar_chr_rename.txt"
    for i in $(seq 1 22); do echo "$i chr$i"; done > "$CHR_MAP"
    echo "X chrX" >> "$CHR_MAP"
    echo "Y chrY" >> "$CHR_MAP"
    echo "MT chrMT" >> "$CHR_MAP"
    CLINVAR_FIXED="$OUTPUT_DIR/clinvar_chrfixed.vcf.gz"
    bcftools annotate --rename-chrs "$CHR_MAP" "$CLINVAR_VCF" -Oz -o "$CLINVAR_FIXED"
    tabix -p vcf "$CLINVAR_FIXED"
    rm -f "$CHR_MAP"
    CLINVAR_USE="$CLINVAR_FIXED"
else
    CLINVAR_USE="$CLINVAR_VCF"
fi
bcftools annotate -a "$CLINVAR_USE" \
    -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
    "$OUTPUT_DIR/step1_snpeff.vcf" -Oz -o "$OUTPUT_DIR/step2_clinvar.vcf.gz"

echo "Step 3: gnomAD frequency annotation..."
bcftools annotate -a "$GNOMAD_VCF" \
    -c INFO/AF,INFO/AF_popmax \
    "$OUTPUT_DIR/step2_clinvar.vcf.gz" -Oz -o "$OUTPUT_DIR/annotated.vcf.gz"

echo "Step 4: Indexing..."
tabix -p vcf "$OUTPUT_DIR/annotated.vcf.gz"

rm -f "$OUTPUT_DIR/step1_snpeff.vcf" "$OUTPUT_DIR/step2_clinvar.vcf.gz"
rm -f "$OUTPUT_DIR/clinvar_chrfixed.vcf.gz" "$OUTPUT_DIR/clinvar_chrfixed.vcf.gz.tbi"
echo "Done: $OUTPUT_DIR/annotated.vcf.gz"
