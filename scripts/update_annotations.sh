#!/bin/bash
# Convenience wrapper to run incremental annotation updates.
#
# Usage: ./scripts/update_annotations.sh <annotated.vcf.gz> [options]
#
# Options:
#   --clinvar <clinvar.vcf.gz>   Update ClinVar annotations (default if no flags)
#   --gnomad                     Update gnomAD frequencies (requires GNOMAD_DIR env var)
#   --snpeff                     Update SnpEff functional annotations
#   --dbsnp <dbsnp.vcf.gz>       Update dbSNP rsID annotations
#   --all                        Run all updates (requires all reference files)
#
# Examples:
#   ./scripts/update_annotations.sh data/annotated.vcf.gz --clinvar references/clinvar.vcf.gz
#   GNOMAD_DIR=./references/gnomad ./scripts/update_annotations.sh data/annotated.vcf.gz --all
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <annotated.vcf.gz> [--clinvar <clinvar.vcf.gz>] [--gnomad] [--snpeff] [--dbsnp <dbsnp.vcf.gz>] [--all]"
    exit 1
fi

ANNOTATED_VCF="$1"
shift

DO_CLINVAR=false
DO_GNOMAD=false
DO_SNPEFF=false
DO_DBSNP=false
CLINVAR_VCF=""
DBSNP_VCF=""

# Parse flags
while [ $# -gt 0 ]; do
    case "$1" in
        --clinvar)
            DO_CLINVAR=true
            CLINVAR_VCF="${2:-}"
            if [ -n "$CLINVAR_VCF" ] && [ "${CLINVAR_VCF:0:2}" != "--" ]; then
                shift
            else
                CLINVAR_VCF=""
            fi
            ;;
        --gnomad)  DO_GNOMAD=true ;;
        --snpeff)  DO_SNPEFF=true ;;
        --dbsnp)
            DO_DBSNP=true
            DBSNP_VCF="${2:-}"
            if [ -n "$DBSNP_VCF" ] && [ "${DBSNP_VCF:0:2}" != "--" ]; then
                shift
            else
                DBSNP_VCF=""
            fi
            ;;
        --all)
            DO_CLINVAR=true
            DO_GNOMAD=true
            DO_SNPEFF=true
            DO_DBSNP=true
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# Default: ClinVar only
if ! $DO_CLINVAR && ! $DO_GNOMAD && ! $DO_SNPEFF && ! $DO_DBSNP; then
    echo "No flags specified. Use --clinvar, --gnomad, --snpeff, --dbsnp, or --all."
    exit 1
fi

# Run updates in dependency-safe order
if $DO_SNPEFF; then
    echo ""
    bash "$SCRIPT_DIR/update_snpeff.sh" "$ANNOTATED_VCF"
fi

if $DO_CLINVAR; then
    if [ -z "$CLINVAR_VCF" ]; then
        echo "Error: --clinvar requires a ClinVar VCF path"
        exit 1
    fi
    echo ""
    bash "$SCRIPT_DIR/update_clinvar.sh" "$ANNOTATED_VCF" "$CLINVAR_VCF"
fi

if $DO_GNOMAD; then
    echo ""
    bash "$SCRIPT_DIR/update_gnomad.sh" "$ANNOTATED_VCF"
fi

if $DO_DBSNP; then
    if [ -z "$DBSNP_VCF" ]; then
        echo "Error: --dbsnp requires a dbSNP VCF path"
        exit 1
    fi
    echo ""
    bash "$SCRIPT_DIR/update_dbsnp.sh" "$ANNOTATED_VCF" "$DBSNP_VCF"
fi

echo ""
echo "=== All requested updates complete ==="
