#!/bin/bash
# Download reference databases for GeneChat annotation pipeline.
# Usage: ./scripts/setup_references.sh [output_dir]
#
# Downloads:
#   - ClinVar VCF (GRCh38)
#   - SnpEff database (auto-detected version)
#
# NOTE: gnomAD must be downloaded manually due to size (~30GB).
# See: https://gnomad.broadinstitute.org/downloads
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

# gnomAD
echo ""
echo "Step 3: gnomAD (manual download required)"
echo "gnomAD is too large for automated download (~30GB)."
echo "Download from: https://gnomad.broadinstitute.org/downloads"
echo "Place the VCF at: $OUTPUT_DIR/gnomad.genomes.vcf.bgz"
echo ""
echo "For annotation, set environment variables:"
echo "  export CLINVAR_VCF=$OUTPUT_DIR/clinvar.vcf.gz"
echo "  export GNOMAD_VCF=$OUTPUT_DIR/gnomad.genomes.vcf.bgz"

echo ""
echo "=== Setup complete ==="
