# Plan: Per-Chromosome dbSNP Download via Remote Region Queries

Replace the single-stream dbSNP download with per-chromosome remote region
queries using htslib's HTTP Range support. Provides per-chromosome resumability
within the 50 GB disk budget.

ADR: [0007-per-chromosome-dbsnp-download.md](../architecture/0007-per-chromosome-dbsnp-download.md)
Issue: #49

---

## 1. Download Pipeline (download.py)

### 1.1 New constant: DBSNP_CONTIGS

**Action:** ADD
**Files:** `src/genechat/download.py`

Add an ordered list of the 25 RefSeq contig accessions with their chr mappings.
Reuse the existing `_write_refseq_chr_map()` data but as a structured constant
instead of just a file-writing helper.

```python
DBSNP_CONTIGS = [
    ("NC_000001.11", "chr1"),
    ("NC_000002.12", "chr2"),
    ...
    ("NC_000024.10", "chrY"),
    ("NC_012920.1", "chrMT"),
]
```

### 1.2 New function: _download_dbsnp_chromosome()

**Action:** ADD
**Files:** `src/genechat/download.py`

Downloads and renames a single chromosome from the remote dbSNP file:

```
bcftools view -r <refseq_contig> <remote_url> \
  | bcftools annotate --rename-chrs <chr_map> - -Oz -o <per_chrom_tmp>
```

- Takes: contig name, chr name, remote URL, chr_map path, output dir
- Returns: path to per-chromosome bgzipped VCF
- Includes progress reporting via ProgressLine
- On failure: cleans up partial output, raises

### 1.3 New function: _concat_dbsnp_chromosomes()

**Action:** ADD
**Files:** `src/genechat/download.py`

Concatenates per-chromosome VCFs into the final chrfixed file:

```
bcftools concat chr1.vcf.gz chr2.vcf.gz ... -Oz -o dbsnp_chrfixed.vcf.gz
tabix -p vcf dbsnp_chrfixed.vcf.gz
```

- Writes to tmp, atomically replaces final
- Cleans up per-chromosome files after successful concat

### 1.4 Resume state tracking

**Action:** ADD
**Files:** `src/genechat/download.py`

A JSON state file (`dbsnp_progress.json`) in the dbSNP directory tracks:

```json
{
  "completed_contigs": ["NC_000001.11", "NC_000002.12", ...]
}
```

- On startup: read state file, skip completed contigs
- After each chromosome completes: update state file
- After successful concat: delete state file
- On `--force`: ignore existing state (start with empty completed set)

### 1.5 Rewrite download_dbsnp()

**Action:** MODIFY
**Files:** `src/genechat/download.py`

Replace the current streaming/file-based dual-path with:

1. Check if chrfixed already exists (skip if not forced)
2. Write chr_map file
3. Load or create resume state
4. For each contig not in completed list:
   a. Call `_download_dbsnp_chromosome()`
   b. Update state file
   c. Report overall progress ("chromosome 5/25")
5. Call `_concat_dbsnp_chromosomes()`
6. Clean up state file, chr_map, per-chromosome temps
7. Return path to chrfixed

### 1.6 Remove _stream_dbsnp_rename()

**Action:** DELETE
**Files:** `src/genechat/download.py`

No longer needed — replaced by per-chromosome approach.

### 1.7 Keep _delete_dbsnp_raw() and file-based fallback logic

**Action:** KEEP (for now)
**Files:** `src/genechat/download.py`

If a raw dbSNP file already exists on disk (from a previous legacy download),
still use the file-based rename + delete path. This handles the case where
a user already has the raw file and shouldn't re-download.

---

## 2. Progress Reporting

### 2.1 Per-chromosome progress

**Action:** ADD
**Files:** `src/genechat/download.py`

Each chromosome reports:
- Overall: `"dbSNP: chromosome 5/25 (chr5)"`
- Per-chromosome download: bytes transferred, speed, ETA (via ProgressLine)

### 2.2 Integration with sub_step progress (PR #54)

**Action:** CONSIDER
**Files:** `src/genechat/download.py`, `src/genechat/cli.py`

If PR #54's sub_step tracking has been ported from the demo repo, integrate
with it. Each chromosome becomes a sub_step. If not yet ported, design the
progress reporting to be compatible with future sub_step integration:
- Use a consistent callback pattern
- Report chromosome index and total count

---

## 3. Annotation Step (cli.py)

### 3.1 No changes to _annotate_dbsnp()

**Action:** NONE
**Files:** `src/genechat/cli.py`

The annotation step reads the local chrfixed file via `bcftools annotate -a`.
This is unchanged — the file is identical regardless of how it was built.

---

## 4. Tests

### 4.1 Unit tests for per-chromosome download

**Action:** ADD
**Files:** `tests/test_download.py`

- `test_download_dbsnp_chromosome_pipeline`: Mock bcftools + HTTP, verify
  per-chromosome VCF is written with correct contig names
- `test_download_dbsnp_resume_skips_completed`: Create state file with some
  contigs marked complete, verify they're skipped
- `test_download_dbsnp_resume_retries_failed`: Verify incomplete chromosome
  (no output file) is retried even if state says started
- `test_download_dbsnp_concat`: Verify concat produces valid output and
  cleans up per-chromosome files
- `test_download_dbsnp_state_file_cleanup`: Verify state file is deleted
  after successful concat
- `test_download_dbsnp_force_ignores_state`: Verify --force deletes state
  file and starts fresh

### 4.2 Update existing tests

**Action:** MODIFY
**Files:** `tests/test_download.py`

- Update `test_streaming_path_when_no_raw` — replace with per-chromosome
  equivalent
- Update `test_file_based_deletes_raw_after_rename` — keep for legacy
  raw-file fallback path

---

## 5. Cleanup

### 5.1 Remove stale streaming test

**Action:** MODIFY
**Files:** `tests/test_download.py`

Replace `test_streaming_path_when_no_raw` with per-chromosome tests.

### 5.2 Update CLAUDE.md if needed

**Action:** CHECK
**Files:** `CLAUDE.md`

Verify architecture section still accurately describes the dbSNP download
flow after the change.

---

## Verification

- [ ] `bcftools view -r <contig> <remote_url>` works for all 25 contigs
- [ ] Per-chromosome VCFs have correct chr-prefixed contig names
- [ ] `bcftools concat` produces a valid, indexed VCF identical to the
      single-stream output
- [ ] Resume: interrupting mid-download and restarting skips completed
      chromosomes
- [ ] Peak disk stays under 25 GB during dbSNP processing
- [ ] All existing tests pass
- [ ] New unit tests cover resume, concat, cleanup, and force paths
- [ ] ruff check + format pass
