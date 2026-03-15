# Plan: Parallel Per-Chromosome Annotation (#66)

ADR: [0010-parallel-annotation.md](../architecture/0010-parallel-annotation.md)

## Overview

Parallelize gnomAD and dbSNP annotation across chromosomes in `--fast` mode
using `ProcessPoolExecutor` and per-chromosome temp SQLite databases.

## Scope

- gnomAD and dbSNP only (ClinVar is fast enough; SnpEff has JVM memory concerns)
- `--fast` mode only (non-fast remains sequential)
- No new CLI flags (parallelism is implicit in `--fast`)

---

## 1. New module: `src/genechat/parallel.py`

### Worker functions (must be top-level for pickling)

**`annotate_gnomad_chromosome(chrom, vcf_path, gnomad_file, temp_db_path, chr_rename_map_path)`**
- Creates lightweight temp SQLite DB with schema: `(chrom TEXT, pos INT, ref TEXT, alt TEXT, af REAL, af_grpmax REAL, PRIMARY KEY(chrom, pos, ref, alt))`
- Runs `bcftools annotate -a {gnomad_file} -c INFO/AF,INFO/AF_grpmax -r chr{chrom} {vcf_path}`
- Pipes through `bcftools annotate --rename-chrs` if `chr_rename_map_path` is set
- Parses VCF stream, inserts rows into temp DB
- Returns `(chrom, row_count, temp_db_path)`

**`annotate_dbsnp_chromosome(chrom, vcf_path, dbsnp_vcf, temp_db_path, chr_rename_map_path)`**
- Creates temp DB with schema: `(chrom TEXT, pos INT, ref TEXT, alt TEXT, rsid TEXT, PRIMARY KEY(chrom, pos, ref, alt))`
- Runs `bcftools annotate -a {dbsnp_vcf} -c ID -r chr{chrom} {vcf_path}`
- Pipes through rename if needed
- Returns `(chrom, row_count, temp_db_path)`

### Merge function

**`merge_temp_databases(main_db_path, results, layer)`**
- Opens main PatchDB
- For each `(chrom, count, temp_path)`:
  - `ATTACH DATABASE temp_path AS temp`
  - gnomAD: `UPDATE variants SET af = ..., af_grpmax = ... FROM temp.results WHERE ...`
  - dbSNP: `UPDATE variants SET rsid = ... FROM temp.results WHERE ... AND variants.rsid IS NULL`
  - `DETACH temp`
- Deletes temp files after merge
- Returns total rows merged

### Orchestrator

**`run_parallel_annotation(vcf_path, patch_db_path, chroms, source, fast_args, chr_rename_map, progress_callback)`**
- Determines worker count: `min(cpu_count, len(chroms), 8)`
- Creates temp directory for per-chromosome DBs
- Submits tasks via `ProcessPoolExecutor`
- Uses `as_completed()` for progress reporting: `"chr1 complete: 45,231 variants [4/24]"`
- Calls `merge_temp_databases()` after all complete
- Returns total rows
- `finally:` cleans up temp directory

---

## 2. Modify `cli.py` — wire `fast` to annotation functions

### `_annotate_gnomad(..., fast=False)`
- When `fast=True`: call `run_parallel_annotation(source="gnomad", ...)`
- When `fast=False`: existing sequential code (unchanged)

### `_annotate_dbsnp(..., fast=False)`
- When `fast=True`: call `run_parallel_annotation(source="dbsnp", ...)`
- When `fast=False`: existing sequential code (unchanged)
- Note: dbSNP currently processes the entire file in one pass. The parallel
  path splits into per-chromosome runs using `bcftools annotate -r chrN`

### `_run_annotate()`
- Pass `fast=fast` to `_annotate_gnomad()` and `_annotate_dbsnp()`

---

## 3. Modify `patch.py` — add merge support

Add `merge_from_temp_db(temp_path, layer)` method to PatchDB, or keep merge
logic in `parallel.py` using raw `sqlite3` (simpler, avoids PatchDB dependency
in workers).

---

## 4. Tests

### `tests/test_parallel.py` (new)

| Test | What it verifies |
|------|------------------|
| `test_gnomad_worker_produces_temp_db` | Mock bcftools → temp DB has correct rows |
| `test_dbsnp_worker_produces_temp_db` | Same for dbSNP |
| `test_merge_gnomad_updates_af` | Merge applies AF/AF_grpmax to main DB |
| `test_merge_dbsnp_updates_rsid` | Merge applies rsID where null |
| `test_merge_preserves_other_annotations` | SnpEff/ClinVar columns untouched |
| `test_worker_failure_cleanup` | Failed worker → temp files cleaned up |
| `test_worker_count_respects_limits` | min(cpu, chroms, MAX_WORKERS) |
| `test_bare_contig_rename_in_worker` | chr_rename_map piped correctly |

### `tests/test_cli.py` (additions)

| Test | What it verifies |
|------|------------------|
| `test_annotate_fast_gnomad_parallel` | `--fast` dispatches to parallel path |
| `test_annotate_fast_dbsnp_parallel` | Same for dbSNP |
| `test_annotate_non_fast_sequential` | Without `--fast`, sequential path used |

---

## 5. Documentation updates

| File | Change |
|------|--------|
| `docs/architecture/0010-parallel-annotation.md` | Update PENDING with plan commit hash |
| `docs/architecture/README.md` | Add ADR-0010 row |
| `CLAUDE.md` | Note parallel annotation in architecture section |
| `README.md` | Update `--fast` description to mention parallelization |

---

## 6. Verification

- `uv run pytest` — all tests pass
- `uv run ruff check . && uv run ruff format --check .` — clean
- `uv run genechat annotate --help` — no new flags (parallelism is implicit)
- Parity: parallel produces same patch.db content as sequential
