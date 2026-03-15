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
- Creates lightweight temp SQLite DB with table `results`: `CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, af REAL, af_grpmax REAL, PRIMARY KEY(chrom, pos, ref, alt))`
- Region arg uses input VCF's contig style: `-r chr{chrom}` for chr-prefixed VCFs, `-r {chrom}` for bare-contig VCFs. The orchestrator passes a `contig_prefix` flag based on `_detect_bare_contigs()`.
- If `chr_rename_map_path` is set (bare-contig VCF), pipes through `bcftools annotate --rename-chrs` **before** the annotation step so contigs match the gnomAD reference (which uses chr-prefixed names)
- Parses VCF stream, normalizes chrom to bare form via `normalize_chrom()` before inserting into temp DB (matching PatchDB convention)
- Returns `(chrom, row_count, temp_db_path)`

**`annotate_dbsnp_chromosome(chrom, vcf_path, dbsnp_vcf, temp_db_path, chr_rename_map_path)`**
- Creates temp DB with table `results`: `CREATE TABLE results (chrom TEXT, pos INT, ref TEXT, alt TEXT, rsid TEXT, PRIMARY KEY(chrom, pos, ref, alt))`
- Region arg uses input VCF's contig style (same logic as gnomAD worker)
- If `chr_rename_map_path` is set, pipes through rename before annotation
- Normalizes chrom to bare form before inserting into temp DB
- Returns `(chrom, row_count, temp_db_path)`

### Merge function

**`merge_temp_databases(main_db_path, results, layer)`**
- Opens main PatchDB
- For each `(chrom, count, temp_path)`:
  - `ATTACH DATABASE temp_path AS temp`
  - gnomAD: `UPDATE annotations SET af = ..., af_grpmax = ... FROM temp.results WHERE annotations.chrom = temp.results.chrom AND ...` (both sides use bare chrom names)
  - dbSNP: `UPDATE annotations SET rsid = ..., rsid_source = 'dbsnp' FROM temp.results WHERE ... AND annotations.rsid IS NULL`
  - `DETACH temp`
- Requires SQLite >= 3.33 for `UPDATE...FROM` syntax (Python 3.11+ bundles >= 3.39)
- Deletes temp files after merge
- Returns total rows merged

### Orchestrator

**`run_parallel_annotation(vcf_path, patch_db_path, chroms, source, fast_args, chr_rename_map, progress_callback)`**
- Determines worker count: `min(cpu_count, len(chroms), MAX_WORKERS)` where `MAX_WORKERS = 8`
- Creates temp directory for per-chromosome DBs
- Submits tasks via `ProcessPoolExecutor`
- Uses `as_completed()` for progress reporting: `"chr1 complete: 45,231 variants [4/N]"` (N varies: gnomAD=24, dbSNP=25)
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
| `docs/architecture/0010-parallel-annotation.md` | Already done (commit hash 45b2ed1) |
| `docs/architecture/README.md` | Add ADR-0010 row |
| `CLAUDE.md` | Note parallel annotation in architecture section |
| `README.md` | Update `--fast` description to mention parallelization |

---

## 6. Verification

- `uv run pytest` — all tests pass
- `uv run ruff check . && uv run ruff format --check .` — clean
- `uv run genechat annotate --help` — no new flags (parallelism is implicit)
- Parity: parallel produces same patch.db content as sequential
