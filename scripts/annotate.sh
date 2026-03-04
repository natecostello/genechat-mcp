#!/bin/bash
# One-time VCF annotation pipeline: SnpEff → ClinVar → gnomAD
# Usage: ./scripts/annotate.sh input.vcf.gz [output_dir]
#
# Prerequisites:
#   - SnpEff/SnpSift >= 5.2
#   - ClinVar VCF (set CLINVAR_VCF env var)
#   - gnomAD VCF (set GNOMAD_VCF env var)
#   - bgzip and tabix (htslib)
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

echo "Step 1: SnpEff functional annotation..."
snpEff ann -v GRCh38.p14 "$INPUT_VCF" > "$OUTPUT_DIR/step1_snpeff.vcf"

echo "Step 2: ClinVar annotation..."
SnpSift annotate "$CLINVAR_VCF" "$OUTPUT_DIR/step1_snpeff.vcf" > "$OUTPUT_DIR/step2_clinvar.vcf"

echo "Step 3: gnomAD frequency annotation..."
SnpSift annotate -info AF,AF_popmax "$GNOMAD_VCF" "$OUTPUT_DIR/step2_clinvar.vcf" > "$OUTPUT_DIR/annotated.vcf"

echo "Step 4: Compress and index..."
bgzip "$OUTPUT_DIR/annotated.vcf"
tabix -p vcf "$OUTPUT_DIR/annotated.vcf.gz"

rm -f "$OUTPUT_DIR/step1_snpeff.vcf" "$OUTPUT_DIR/step2_clinvar.vcf"
echo "Done: $OUTPUT_DIR/annotated.vcf.gz"
