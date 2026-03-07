#!/bin/bash
# Convenience wrapper to run incremental annotation updates.
#
# Usage: ./scripts/update_annotations.sh <annotated.vcf.gz> [options]
#
# Options:
#   --clinvar <clinvar.vcf.gz>   Update ClinVar annotations
#   --gnomad                     Update gnomAD frequencies (requires GNOMAD_DIR env var)
#   --snpeff                     Update SnpEff functional annotations
#   --dbsnp <dbsnp.vcf.gz>       Update dbSNP rsID annotations
#   --all                        Run all updates (ClinVar + gnomAD + SnpEff + dbSNP)
#
# When using --all, ClinVar and dbSNP paths can be provided via env vars:
#   CLINVAR_VCF — Path to ClinVar VCF (required for --clinvar and --all)
#   DBSNP_VCF   — Path to dbSNP VCF (required for --dbsnp and --all)
#   GNOMAD_DIR  — Directory of per-chromosome gnomAD VCFs (required for --gnomad and --all)
#
# If no flags are specified, nothing runs. Use --clinvar for the most common update.
#
# Examples:
#   ./scripts/update_annotations.sh data/annotated.vcf.gz --clinvar references/clinvar.vcf.gz
#   GNOMAD_DIR=./references/gnomad ./scripts/update_annotations.sh data/annotated.vcf.gz --gnomad
#   CLINVAR_VCF=refs/clinvar.vcf.gz DBSNP_VCF=refs/dbsnp.vcf.gz GNOMAD_DIR=refs/gnomad \
#       ./scripts/update_annotations.sh data/annotated.vcf.gz --all
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
CLINVAR_VCF_ARG=""
DBSNP_VCF_ARG=""

# Parse flags
while [ $# -gt 0 ]; do
    case "$1" in
        --clinvar)
            DO_CLINVAR=true
            CLINVAR_VCF_ARG="${2:-}"
            if [ -n "$CLINVAR_VCF_ARG" ] && [ "${CLINVAR_VCF_ARG:0:2}" != "--" ]; then
                shift
            else
                CLINVAR_VCF_ARG=""
            fi
            ;;
        --gnomad)  DO_GNOMAD=true ;;
        --snpeff)  DO_SNPEFF=true ;;
        --dbsnp)
            DO_DBSNP=true
            DBSNP_VCF_ARG="${2:-}"
            if [ -n "$DBSNP_VCF_ARG" ] && [ "${DBSNP_VCF_ARG:0:2}" != "--" ]; then
                shift
            else
                DBSNP_VCF_ARG=""
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

# No flags specified
if ! $DO_CLINVAR && ! $DO_GNOMAD && ! $DO_SNPEFF && ! $DO_DBSNP; then
    echo "No flags specified. Use --clinvar, --gnomad, --snpeff, --dbsnp, or --all."
    exit 1
fi

# Resolve ClinVar path: CLI arg > env var
CLINVAR_RESOLVED="${CLINVAR_VCF_ARG:-${CLINVAR_VCF:-}}"
# Resolve dbSNP path: CLI arg > env var
DBSNP_RESOLVED="${DBSNP_VCF_ARG:-${DBSNP_VCF:-}}"

# Run updates in dependency-safe order
if $DO_SNPEFF; then
    echo ""
    bash "$SCRIPT_DIR/update_snpeff.sh" "$ANNOTATED_VCF"
fi

if $DO_CLINVAR; then
    if [ -z "$CLINVAR_RESOLVED" ]; then
        echo "Error: --clinvar requires a ClinVar VCF path (as argument or CLINVAR_VCF env var)"
        exit 1
    fi
    echo ""
    bash "$SCRIPT_DIR/update_clinvar.sh" "$ANNOTATED_VCF" "$CLINVAR_RESOLVED"
fi

if $DO_GNOMAD; then
    echo ""
    bash "$SCRIPT_DIR/update_gnomad.sh" "$ANNOTATED_VCF"
fi

if $DO_DBSNP; then
    if [ -z "$DBSNP_RESOLVED" ]; then
        echo "Error: --dbsnp requires a dbSNP VCF path (as argument or DBSNP_VCF env var)"
        exit 1
    fi
    echo ""
    bash "$SCRIPT_DIR/update_dbsnp.sh" "$ANNOTATED_VCF" "$DBSNP_RESOLVED"
fi

echo ""
echo "=== All requested updates complete ==="
