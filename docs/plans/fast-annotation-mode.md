# Fast Annotation Mode (`--fast`) — Implementation Plan

**ADR:** [0009-fast-annotation-mode.md](../architecture/0009-fast-annotation-mode.md)
**Issue:** #55

## Summary

Add a `--fast` flag to `genechat init` and `genechat annotate` that uses
bulk downloads instead of the default disk-efficient approaches:

- **dbSNP**: Download full file via `download_file()` + `_file_based_dbsnp_rename()`
  instead of per-chromosome remote region queries
- **gnomAD**: Pre-download all chromosomes before annotation so it runs
  non-incrementally (from local files) instead of download-annotate-delete

Trade-off: ~180 GB peak disk (vs ~30 GB default), ~20x faster.

## Changes

1. `download.py` — `download_dbsnp(fast=True)` branch: bulk download + file-based rename
2. `cli.py` — `--fast` option on `init` and `annotate` commands
3. `cli.py` — `_run_annotate(fast=True)`: gnomAD pre-download + dbSNP fast passthrough
4. Tests: 5 new tests covering fast-mode code paths
5. Docs: ADR-0007 status update, ADR-0009 plan reference, README/CLAUDE.md updates
