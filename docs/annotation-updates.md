# Incremental Annotation Updates

The annotation pipeline (`annotate.sh`) is a linear chain that must be re-run from scratch. This document describes how to update each annotation layer independently, so you can stay current without re-running the full pipeline.

## Background

| Layer | What changes | Release cadence | Re-annotation cost today |
|-------|-------------|-----------------|--------------------------|
| ClinVar | Variant reclassifications (VUS->Pathogenic, etc.) | Monthly | Full pipeline (~30 min) |
| gnomAD | Population allele frequencies | Major releases every 1-2 years | Full pipeline (~30 min) |
| SnpEff | Gene models, transcript definitions | Tied to Ensembl (~2/year) | Full pipeline (~30 min) |
| dbSNP | rsID assignments for new variants | Quarterly | `setup_giab.sh` test data only (~30 min) |
| GWAS Catalog | New association study results | Weekly | `build_gwas_db.py` (~2 min, already incremental) |
| Seed data | PGx (CPIC) + PRS (PGS Catalog) | When APIs update | `build_seed_data.py` (~5 min, already incremental) |

## Design: Layer-Independent Re-annotation

`bcftools annotate` can **strip** specific INFO fields (`-x`) and **re-stamp** them from a fresh reference (`-a`, `-c`). Each annotation layer writes to distinct INFO fields with no cross-dependencies:

| Layer | INFO fields owned | Depends on other layers? |
|-------|-------------------|--------------------------|
| SnpEff | `ANN` | No (reads REF/ALT only) |
| ClinVar | `CLNSIG`, `CLNDN`, `CLNREVSTAT`, `CLNVC` | No (matches on CHROM/POS/REF/ALT) |
| gnomAD | `AF`, `AF_grpmax` (or `AF_popmax`) | No (matches on CHROM/POS/REF/ALT) |
| dbSNP | `ID` column | No (matches on CHROM/POS/REF/ALT) |

Because the fields are independent, any single layer can be updated in isolation.

## Planned Scripts

### `scripts/update_clinvar.sh` (highest priority)

ClinVar reclassifications are the most clinically impactful updates. Recommended: every 3-6 months.

```
1. Download latest ClinVar VCF (setup_references.sh already does this)
2. Strip old ClinVar fields:
   bcftools annotate -x INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
       annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
3. Re-annotate with fresh ClinVar (with contig rename if needed) to a temp file:
   bcftools annotate -a clinvar_new.vcf.gz \
       -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
       tmp_stripped.vcf.gz -Oz -o tmp_annotated.vcf.gz
4. Atomically replace the existing annotated VCF:
   mv tmp_annotated.vcf.gz annotated.vcf.gz
5. Re-index: tabix -p vcf annotated.vcf.gz
6. Clean up temp files
```

Estimated time: 2-5 minutes. Preserves all SnpEff, gnomAD, and dbSNP annotations.

### `scripts/update_gnomad.sh`

Only needed on major gnomAD releases (v4->v5). Recommended: when a new major version ships.

```
1. Strip old frequency fields:
   bcftools annotate -x INFO/AF,INFO/AF_grpmax,INFO/AF_popmax \
       annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
2. Re-annotate per-chromosome (same logic as annotate.sh step 3)
3. Re-index
```

Estimated time: 10-20 minutes (per-chromosome gnomAD annotation dominates).

### `scripts/update_snpeff.sh`

Only needed when Ensembl releases new gene models. Recommended: annually.

```
1. Download new SnpEff database: snpEff download GRCh38.pXX
2. Strip old ANN field:
   bcftools annotate -x INFO/ANN annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
3. Re-run SnpEff on stripped VCF (writes new ANN field)
4. Re-index
```

Estimated time: 15-30 minutes (SnpEff is the slowest step). Consider per-chromosome parallelism (already proven in the full pipeline).

### `scripts/update_dbsnp.sh`

Only needed if the original annotation was done without dbSNP, or on a new dbSNP release.

```
1. Download latest dbSNP VCF + rename contigs to chr prefix
2. bcftools annotate -a dbsnp_new.vcf.gz -c ID \
       annotated.vcf.gz -Oz -o tmp_updated.vcf.gz
3. mv + re-index
```

Note: unlike the others, dbSNP primarily uses the `ID` column (not INFO), so `-x` stripping isn't needed here.

Estimated time: 5-10 minutes.

### `scripts/update_annotations.sh` (convenience wrapper)

```
Usage: ./scripts/update_annotations.sh [--clinvar] [--gnomad] [--snpeff] [--dbsnp] [--all]

Runs only the requested update layers in the correct order.
Default (no flags): --clinvar only (the most common update).
```

## Implementation Considerations

- **Atomic writes**: All scripts write to a temp file, then `mv` to the final path -- never overwrite in place.
- **Backup**: Before any update, copy the current `annotated.vcf.gz` to `annotated.vcf.gz.bak`.
- **Validation**: After re-annotation, spot-check a known variant (e.g., rs4149056 should still have SLCO1B1 in ANN and drug_response in CLNSIG).
- **Version tracking**: Write `##GeneChat_*` header lines into the VCF recording which database versions were used and when:
  ```
  ##GeneChat_ClinVar=2026-03-01
  ##GeneChat_gnomAD=v4.1
  ##GeneChat_SnpEff=GRCh38.p14
  ##GeneChat_dbSNP=b156
  ```
  The `genome_summary` tool reads these headers and reports annotation freshness.

## Recommended Update Cadence

| What | How often | Script | Time |
|------|-----------|--------|------|
| ClinVar | Every 3-6 months | `update_clinvar.sh` | ~3 min |
| Seed data | When CPIC/PGS sources update | `build_seed_data.py` | ~5 min |
| GWAS Catalog | Every 6-12 months | `build_gwas_db.py` | ~2 min |
| gnomAD | On major releases only | `update_gnomad.sh` | ~15 min |
| SnpEff | Annually | `update_snpeff.sh` | ~20 min |
| dbSNP | Annually | `update_dbsnp.sh` | ~7 min |
| Full re-annotation | Only if starting from a new raw VCF | `annotate.sh` | ~30 min |
