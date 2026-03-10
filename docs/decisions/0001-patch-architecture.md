---
status: accepted
date: 2026-03-07
---

# Use raw VCF + SQLite patch.db instead of re-annotating the VCF

## Context and Problem Statement

GeneChat's annotation pipeline (SnpEff, ClinVar, gnomAD, dbSNP) baked all annotations into a modified VCF file. Updating a single annotation layer required re-running the entire pipeline (~30 min), and the 2 GB annotated VCF duplicated the raw VCF on disk. We needed a way to update annotations incrementally without touching the user's raw VCF.

## Considered Options

1. **Re-annotate the full VCF each time** -- Simple but slow (~30 min), destructive (overwrites previous annotations), and doubles disk usage.
2. **Raw VCF + SQLite patch database** -- Keep the raw VCF untouched, store annotations in a separate SQLite "patch" database, join at query time on (chrom, pos, ref, alt).
3. **Variant database only (no VCF at runtime)** -- Import all variants into SQLite. Loses pysam's efficient indexed access and requires duplicating all genotype data.

## Decision Outcome

Chosen option: "Raw VCF + SQLite patch database", because it enables incremental annotation updates (add gnomAD without re-running SnpEff), keeps the raw VCF pristine, and reuses the same proven tools (bcftools, SnpEff) -- just piping their output to SQLite instead of bgzip.

### Consequences

- Good, because annotation layers can be added, updated, or cleared independently
- Good, because the raw VCF is never modified -- users can verify their original data
- Good, because patch generation uses the same bcftools/SnpEff commands, guaranteeing functional equivalence with the annotated-VCF approach (verified by parity tests)
- Bad, because VCFEngine now has dual-mode complexity (legacy annotated VCF vs raw+patch)
- Bad, because query-time joins add a dict lookup per variant (negligible in practice)

## More Information

Implemented in PR #21. Original planning doc preserved in git history at `docs/patch-architecture-plan.md`.
