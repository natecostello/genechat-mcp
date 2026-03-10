---
status: accepted
date: 2026-03-07
related ADRs:
  - "[0002 Multi-genome support](0002-multi-genome-support.md) — each genome gets its own patch.db"
  - "[0003 Pip-installable package](0003-pip-installable-package.md) — patch.db is per-user, distinct from the shipped lookup_tables.db"
---

# Use raw VCF + SQLite patch.db instead of re-annotating the VCF

## Context and Problem Statement

GeneChat's annotation pipeline (SnpEff, ClinVar, gnomAD, dbSNP) baked all annotations into a modified VCF file. Updating a single annotation layer required re-running the entire pipeline (~30 min), and the 2 GB annotated VCF duplicated the raw VCF on disk. We needed a way to update annotations incrementally without touching the user's raw VCF.

## Decision Drivers

* Annotation updates must be incremental — adding gnomAD shouldn't require re-running SnpEff
* The user's raw VCF must never be modified — they need to verify their original data
* The solution must reuse existing tools (bcftools, SnpEff) rather than inventing new parsers
* Disk usage should not double (raw + annotated copy)

## Considered Options

* Re-annotate the full VCF each time
* Raw VCF + SQLite patch database
* Variant database only (no VCF at runtime)

## Decision Outcome

Chosen option: "Raw VCF + SQLite patch database", because it enables incremental annotation updates, keeps the raw VCF pristine, and reuses the same proven tools — just piping their output to SQLite instead of bgzip.

Plan: `docs/patch-architecture-plan.md` (created at `ccd9915`, last version before deletion at `5b22dd7~1`)

### Consequences

* Good, because annotation layers can be added, updated, or cleared independently
* Good, because the raw VCF is never modified — users can verify their original data
* Good, because patch generation uses the same bcftools/SnpEff commands, guaranteeing functional equivalence with the annotated-VCF approach (verified by parity tests before legacy removal)
* Neutral, because query-time joins add a dict lookup per variant (negligible in practice)

### Confirmation

Functional equivalence was verified by parity tests (`tests/test_parity.py`) that compared annotated-VCF output against raw-VCF+patch.db output for all query methods. These tests were removed after legacy mode was deleted in PR #33.

## Pros and Cons of the Options

### Re-annotate the full VCF each time

Simple approach: run the full pipeline end-to-end whenever any annotation source changes.

* Good, because it is simple — single pipeline, single output file
* Bad, because it is slow (~30 min per full run)
* Bad, because it is destructive — overwrites previous annotations
* Bad, because it doubles disk usage (raw VCF + annotated VCF)

### Raw VCF + SQLite patch database

Keep the raw VCF untouched, store annotations in a separate SQLite "patch" database, join at query time on (chrom, pos, ref, alt).

* Good, because annotation layers are independent — add, update, or clear any layer without touching others
* Good, because the raw VCF is never modified
* Good, because bcftools/SnpEff output can be piped directly to SQLite
* Neutral, because query-time dict lookup adds minimal overhead
* Bad, because it initially required dual-mode complexity in VCFEngine (resolved by removing legacy mode in PR #33)

### Variant database only (no VCF at runtime)

Import all variants and genotypes into SQLite, eliminating the VCF dependency at runtime.

* Good, because everything is in one database — simple queries
* Bad, because it loses pysam's efficient tabix-indexed random access
* Bad, because it requires duplicating all genotype data (~2 GB)
* Bad, because it diverges from standard bioinformatics tooling

## More Information

Implemented in PR #21 (merged 2026-03-07). Legacy annotated-VCF mode was removed in PR #33 after all CLI workflows were confirmed to create a patch.db, eliminating the dual-mode complexity.
