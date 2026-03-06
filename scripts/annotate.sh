#!/bin/bash
# One-time VCF annotation pipeline: SnpEff → ClinVar → gnomAD
# Usage: ./scripts/annotate.sh input.vcf.gz [output_dir]
#
# Prerequisites:
#   macOS:  brew install bcftools brewsci/bio/snpeff
#   Linux:  conda install -c bioconda bcftools snpeff
#   Also:   CLINVAR_VCF env var pointing to ClinVar reference VCF
#
# Optional environment variables:
#   SNPEFF_DB  — SnpEff database name (auto-detected if not set)
#   GNOMAD_DIR — Directory of per-chromosome gnomAD v4 exome VCFs (preferred)
#   GNOMAD_VCF — Path to single gnomAD VCF (legacy fallback)
#
# gnomAD is optional — if neither GNOMAD_DIR nor GNOMAD_VCF is set, the
# pipeline skips frequency annotation and produces a VCF without AF fields.
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
if [ -n "${GNOMAD_DIR:-}" ] && [ -d "${GNOMAD_DIR}" ]; then
    # Per-chromosome gnomAD v4 exome annotation
    echo "  Using per-chromosome gnomAD exomes from: $GNOMAD_DIR"
    CHROMS=$(bcftools view -h "$OUTPUT_DIR/step2_clinvar.vcf.gz" \
        | grep "^##contig" | sed 's/.*ID=\([^,>]*\).*/\1/' | sort -V)

    # Inject AF/AF_grpmax headers into source so all per-chrom outputs share
    # the same header, even chromosomes without a gnomAD file.
    AF_HEADERS="$OUTPUT_DIR/gnomad_headers.txt"
    echo '##INFO=<ID=AF,Number=A,Type=Float,Description="Alternate allele frequency">' > "$AF_HEADERS"
    echo '##INFO=<ID=AF_grpmax,Number=A,Type=Float,Description="Maximum allele frequency across genetic ancestry groups">' >> "$AF_HEADERS"
    STEP2_WITH_HEADERS="$OUTPUT_DIR/step2_with_headers.vcf.gz"
    bcftools annotate -h "$AF_HEADERS" "$OUTPUT_DIR/step2_clinvar.vcf.gz" -Oz -o "$STEP2_WITH_HEADERS"
    tabix -p vcf "$STEP2_WITH_HEADERS"
    rm -f "$AF_HEADERS"

    # First pass: annotate per-chrom into temp files, then concat
    GNOMAD_WORK="$OUTPUT_DIR/gnomad_work"
    mkdir -p "$GNOMAD_WORK"
    CHR_FILES=""
    for CHR in $CHROMS; do
        # Map chrN → gnomAD filename (gnomAD uses chrN in v4 exome filenames)
        GNOMAD_CHR_VCF="$GNOMAD_DIR/gnomad.exomes.v4.1.sites.${CHR}.vcf.bgz"
        CHR_OUT="$GNOMAD_WORK/${CHR}.vcf.gz"
        if [ -f "$GNOMAD_CHR_VCF" ]; then
            echo "  Annotating $CHR with gnomAD..."
            bcftools annotate -a "$GNOMAD_CHR_VCF" \
                -c INFO/AF,INFO/AF_grpmax \
                <(bcftools view -r "$CHR" "$STEP2_WITH_HEADERS") \
                -Oz -o "$CHR_OUT"
        else
            echo "  No gnomAD file for $CHR, passing through unannotated."
            bcftools view -r "$CHR" "$STEP2_WITH_HEADERS" -Oz -o "$CHR_OUT"
        fi
        CHR_FILES="$CHR_FILES $CHR_OUT"
    done
    bcftools concat $CHR_FILES -Oz -o "$OUTPUT_DIR/annotated.vcf.gz"
    rm -rf "$GNOMAD_WORK"
    rm -f "$STEP2_WITH_HEADERS" "$STEP2_WITH_HEADERS.tbi"

elif [ -n "${GNOMAD_VCF:-}" ] && [ -f "${GNOMAD_VCF}" ]; then
    # Legacy: single gnomAD VCF
    echo "  Using single gnomAD VCF: $GNOMAD_VCF"
    bcftools annotate -a "$GNOMAD_VCF" \
        -c INFO/AF,INFO/AF_popmax \
        "$OUTPUT_DIR/step2_clinvar.vcf.gz" -Oz -o "$OUTPUT_DIR/annotated.vcf.gz"

else
    echo "  WARNING: No gnomAD data (neither GNOMAD_DIR nor GNOMAD_VCF set)."
    echo "  Skipping frequency annotation. smart_filter in query_gene will use ClinVar-only mode."
    cp "$OUTPUT_DIR/step2_clinvar.vcf.gz" "$OUTPUT_DIR/annotated.vcf.gz"
fi

echo "Step 4: Indexing..."
tabix -p vcf "$OUTPUT_DIR/annotated.vcf.gz"

rm -f "$OUTPUT_DIR/step1_snpeff.vcf" "$OUTPUT_DIR/step2_clinvar.vcf.gz"
rm -f "$OUTPUT_DIR/clinvar_chrfixed.vcf.gz" "$OUTPUT_DIR/clinvar_chrfixed.vcf.gz.tbi"
echo "Done: $OUTPUT_DIR/annotated.vcf.gz"
