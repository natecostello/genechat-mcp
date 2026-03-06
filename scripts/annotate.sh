#!/bin/bash
# One-time VCF annotation pipeline: SnpEff → ClinVar → gnomAD
# Usage: ./scripts/annotate.sh input.vcf.gz [output_dir]
#
# Prerequisites:
#   macOS:  brew install bcftools brewsci/bio/snpeff
#   Linux:  conda install -c bioconda bcftools snpsift
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
SnpSift annotate "$CLINVAR_VCF" "$OUTPUT_DIR/step1_snpeff.vcf" > "$OUTPUT_DIR/step2_clinvar.vcf"

echo "Step 3: gnomAD frequency annotation..."
SnpSift annotate -info AF,AF_popmax "$GNOMAD_VCF" "$OUTPUT_DIR/step2_clinvar.vcf" > "$OUTPUT_DIR/annotated.vcf"

echo "Step 4: Compress and index..."
bgzip "$OUTPUT_DIR/annotated.vcf"
tabix -p vcf "$OUTPUT_DIR/annotated.vcf.gz"

rm -f "$OUTPUT_DIR/step1_snpeff.vcf" "$OUTPUT_DIR/step2_clinvar.vcf"
echo "Done: $OUTPUT_DIR/annotated.vcf.gz"
