#!/bin/bash
# Download reference databases for GeneChat annotation pipeline.
# Usage: ./scripts/setup_references.sh [output_dir]
#
# Downloads:
#   - ClinVar VCF (GRCh38)
#   - SnpEff database (auto-detected version)
#   - gnomAD v4 exome frequencies (optional, ~8 GB)
#
# NOTE: gnomAD genome VCF (~30 GB) must still be downloaded manually.
# gnomAD v4 exome VCF (~8 GB) can be downloaded automatically below.
set -euo pipefail

OUTPUT_DIR="${1:-./references}"
mkdir -p "$OUTPUT_DIR"

echo "=== GeneChat Reference Setup ==="

# ClinVar VCF
echo ""
echo "Step 1: Downloading ClinVar VCF (GRCh38)..."
CLINVAR_URL="https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
CLINVAR_TBI_URL="https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz.tbi"

if [ -f "$OUTPUT_DIR/clinvar.vcf.gz" ]; then
    echo "ClinVar VCF already exists, skipping download."
else
    curl -L -o "$OUTPUT_DIR/clinvar.vcf.gz" "$CLINVAR_URL"
    curl -L -o "$OUTPUT_DIR/clinvar.vcf.gz.tbi" "$CLINVAR_TBI_URL"
    echo "ClinVar downloaded: $OUTPUT_DIR/clinvar.vcf.gz"
fi

# SnpEff database
echo ""
echo "Step 2: Downloading SnpEff database..."
if command -v snpEff &>/dev/null; then
    if [ -z "${SNPEFF_DB:-}" ]; then
        SNPEFF_VERSION=$(snpEff -version 2>&1 | head -1 || true)
        if echo "$SNPEFF_VERSION" | grep -q "4\.3"; then
            SNPEFF_DB="GRCh38.86"
        else
            SNPEFF_DB="GRCh38.p14"
        fi
        echo "Auto-detected SnpEff database: $SNPEFF_DB"
    fi
    snpEff download -v "$SNPEFF_DB"
    echo "SnpEff database downloaded."
else
    echo "WARNING: snpEff not found in PATH. Install first:"
    echo "  macOS:  brew install brewsci/bio/snpeff"
    echo "  Linux:  conda install -c bioconda snpsift"
fi

# gnomAD v4 exome frequencies (per-chromosome)
echo ""
echo "Step 3: gnomAD v4 exome frequencies (~8 GB)"
GNOMAD_DIR="$OUTPUT_DIR/gnomad_exomes_v4"
GNOMAD_BASE="https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/exomes"

if [ -d "$GNOMAD_DIR" ] && [ "$(ls "$GNOMAD_DIR"/*.vcf.bgz 2>/dev/null | wc -l)" -ge 22 ]; then
    echo "gnomAD exome files already exist in $GNOMAD_DIR, skipping."
else
    echo "gnomAD v4 exome VCFs provide population allele frequencies per chromosome."
    echo "Total download: ~8 GB (24 files). This enables smart_filter in query_gene."
    echo ""
    read -r -p "Download gnomAD v4 exome VCFs? [y/N] " response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        mkdir -p "$GNOMAD_DIR"
        CHROMS="1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 X Y"
        for CHR in $CHROMS; do
            VCF_FILE="gnomad.exomes.v4.1.sites.chr${CHR}.vcf.bgz"
            TBI_FILE="${VCF_FILE}.tbi"
            if [ -f "$GNOMAD_DIR/$VCF_FILE" ]; then
                echo "  Already exists: $VCF_FILE"
            else
                echo "  Downloading: $VCF_FILE"
                curl -fSL --progress-bar -o "$GNOMAD_DIR/$VCF_FILE" \
                    "$GNOMAD_BASE/$VCF_FILE"
            fi
            if [ -f "$GNOMAD_DIR/$TBI_FILE" ]; then
                echo "  Already exists: $TBI_FILE"
            else
                echo "  Downloading: $TBI_FILE"
                curl -fSL --progress-bar -o "$GNOMAD_DIR/$TBI_FILE" \
                    "$GNOMAD_BASE/$TBI_FILE"
            fi
        done
        echo ""
        echo "gnomAD exome download complete."
    else
        echo "Skipping gnomAD exome download."
        echo "You can download later by re-running this script, or manually from:"
        echo "  https://gnomad.broadinstitute.org/downloads#v4-exomes"
    fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "For annotation, set environment variables:"
echo "  export CLINVAR_VCF=$OUTPUT_DIR/clinvar.vcf.gz"
if [ -d "$GNOMAD_DIR" ]; then
    echo "  export GNOMAD_DIR=$GNOMAD_DIR"
fi
