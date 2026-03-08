# Incremental Annotation Updates

Annotations are stored in a SQLite patch database (`patch.db`), separate from the raw VCF. Each annotation layer can be updated independently using `genechat annotate`.

> **Invocation:** Commands below assume `genechat` is on your PATH. In a clone-based setup, prefix with `uv run` (e.g., `uv run genechat annotate --clinvar`).

## Background

| Layer | What changes | Release cadence | Update command |
|-------|-------------|-----------------|----------------|
| ClinVar | Variant reclassifications (VUS→Pathogenic, etc.) | Monthly | `genechat annotate --clinvar` |
| gnomAD | Population allele frequencies | Major releases every 1-2 years | `genechat annotate --gnomad` |
| SnpEff | Gene models, transcript definitions | Tied to Ensembl (~2/year) | `genechat annotate --snpeff` |
| dbSNP | rsID identifiers for variants | Major releases | `genechat annotate --dbsnp` |
| GWAS Catalog | New association study results | Weekly | `uv run python scripts/build_gwas_db.py` |
| Seed data | PGx (CPIC) + PRS (PGS Catalog) | When APIs update | `uv run python scripts/build_seed_data.py` |

## How It Works

Each annotation layer writes to distinct columns in `patch.db` with no cross-dependencies:

| Layer | patch.db columns | Depends on other layers? |
|-------|-----------------|--------------------------|
| SnpEff | `effect`, `impact`, `gene`, `hgvs_c`, `hgvs_p`, `transcript` | No (reads REF/ALT only) |
| ClinVar | `clnsig`, `clndn`, `clnrevstat` | No (matches on CHROM/POS/REF/ALT) |
| gnomAD | `af`, `af_grpmax` | No (matches on CHROM/POS/REF/ALT) |
| dbSNP | `rsid`, `rsid_source` | No (stored per variant, independent of other layers) |

Because the columns are independent, any single layer can be updated in isolation without overwriting other layers. Base rows in `patch.db` are populated by the initial SnpEff run using an UPSERT, and subsequent ClinVar/gnomAD (and other layer) updates use targeted `UPDATE` statements that only modify their own columns, preserving all other annotation layers.

## Updating Individual Layers

### ClinVar (highest priority)

ClinVar reclassifications are the most clinically impactful updates. Recommended: every 3-6 months.

```bash
# Re-download references (ClinVar + SnpEff DB by default), then re-annotate ClinVar only
genechat download --force
genechat annotate --clinvar
```

### gnomAD

Only needed on major gnomAD releases (v4→v5). Recommended: when a new major version ships.

```bash
genechat download --gnomad
genechat annotate --gnomad
```

### SnpEff

Only needed when Ensembl releases new gene models. Recommended: annually.

```bash
genechat annotate --snpeff
```

### All layers at once

`--all` runs SnpEff, ClinVar, gnomAD (if installed), and dbSNP (if installed):

```bash
genechat annotate --all
```

## Checking for Updates

`genechat update` shows installed reference versions and automatically checks ClinVar against the latest available release. For other sources (gnomAD, SnpEff, dbSNP), it reports the installed state but may show "check unavailable" when no programmatic version check exists:

```bash
genechat update           # Check ClinVar for newer versions; report other layer status
genechat update --apply   # Download newer ClinVar and re-annotate (other layers unchanged)
```

## Viewing Current State

```bash
genechat status           # Shows VCF info, patch.db layers, reference versions
```

## Recommended Update Cadence

| What | How often | Command | Time |
|------|-----------|---------|------|
| ClinVar | Every 3-6 months | `genechat annotate --clinvar` | ~3 min |
| Seed data | When CPIC/PGS sources update | `uv run python scripts/build_seed_data.py` | ~5 min |
| GWAS Catalog | Every 6-12 months | `uv run python scripts/build_gwas_db.py` | ~2 min |
| gnomAD | On major releases only | `genechat annotate --gnomad` | ~15 min |
| SnpEff | Annually | `genechat annotate --snpeff` | ~20 min |
| Full rebuild | Only if starting from a new raw VCF | `genechat init <vcf>` | ~30 min |
