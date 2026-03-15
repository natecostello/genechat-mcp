---
status: accepted
date: 2026-03-15
related ADRs:
  - [0009-fast-annotation-mode.md](0009-fast-annotation-mode.md)
  - [0001-patch-architecture.md](0001-patch-architecture.md)
---

# Parallel Per-Chromosome Annotation in `--fast` Mode

## Context and Problem Statement

ADR-0009 introduced `--fast` mode for bulk reference downloads. ADR-0009
estimated ~1-2 hours total on capable hardware, but observed performance on
`performance-2x` (2 vCPU, 4 GB RAM) is ~8-10 hours — the download phase is
fast, but the sequential annotation steps dominate wall-clock time.

Each chromosome is processed one at a time for both gnomAD and dbSNP. On
multi-core machines, the pipeline is limited by single-threaded bcftools
processing and SQLite writes. gnomAD annotation across 24 contigs (1-22, X, Y)
takes ~6 hours sequentially; dbSNP across 25 contigs (adds MT) takes ~2
hours. Parallelizing across contigs could reduce this to ~1-2 hours total.

**MT contig edge case:** Mitochondrial contig naming varies — user VCFs may use
`chrM`, `chrMT`, `M`, or `MT`. dbSNP uses `chrMT`. Per-chromosome region
filtering must detect the actual MT contig name from the input VCF header,
not derive it via string concatenation (e.g., `chr` + `MT` → `chrMT` would
silently miss variants in `chrM` VCFs).

## Decision Drivers

- **Sequential bottleneck**: Each chromosome's annotation is independent
  (different reference file region, different patch.db rows), yet they run
  serially
- **SQLite write contention**: PatchDB uses WAL mode (concurrent readers OK),
  but concurrent writers cause `SQLITE_BUSY` even for different rows (page-level
  locking)
- **`--fast` guarantees local files**: All reference files are pre-downloaded,
  so all chromosomes are available simultaneously
- **Memory budget**: `performance-2x` has 4 GB RAM; each bcftools process uses
  ~50-200 MB
- **Correctness**: Final patch.db must be identical regardless of execution order

## Considered Options

1. **Per-chromosome temp databases, merge at end** — each worker writes to an
   isolated temp SQLite file; a single-threaded merge step applies results to
   the main patch.db after all workers complete
2. **WAL mode + busy-timeout retry** — multiple workers write directly to the
   main patch.db with `PRAGMA busy_timeout` to handle contention
3. **Writer queue with single commit thread** — workers produce results via a
   multiprocessing queue; a dedicated thread consumes and writes to patch.db

## Decision Outcome

Chosen option: **1 — Per-chromosome temp databases**, because it eliminates all
write contention during the parallel phase and produces deterministic results.

Plan: `docs/plans/parallel-annotation.md` (created at 45b2ed1)

### Consequences

**Good:**
- Zero SQLite write contention during parallel phase
- Deterministic results — merge order does not affect final state
- Simple worker functions: create temp DB, run bcftools, write results, return
- Failure isolation — one worker's crash does not corrupt the main patch.db
- Works with any number of workers without tuning lock timeouts

**Bad:**
- Additional disk for temp databases (~120 MB total, negligible vs 180 GB peak)
- Merge step adds a sequential phase after parallel work completes
- More complex code path vs sequential (two paths to maintain in `--fast` mode)

**Neutral:**
- Non-fast mode is completely untouched — no risk of regression
- `ProcessPoolExecutor` is stdlib (`concurrent.futures`), no new dependencies

## Confirmation

- Unit tests: worker functions produce correct temp DB content from mocked
  bcftools output
- Unit tests: merge step correctly applies gnomAD AF/AF_grpmax and dbSNP rsID
  updates without clobbering other annotations
- Parity test: `--fast` parallel produces identical patch.db content to
  sequential annotation on the same VCF
- Memory test: verify peak RSS stays under 4 GB with 2 workers on
  `performance-2x`

## Pros and Cons of the Options

### Option 1: Per-chromosome temp databases

- Good: Zero write contention — each worker has exclusive access to its DB
- Good: Clean failure semantics — discard temp DB on worker error
- Good: Merge is a simple single-threaded ATTACH + INSERT/UPDATE
- Bad: ~120 MB additional temp disk (negligible)
- Bad: Merge adds a sequential phase (~30s for 24-25 contigs)

### Option 2: WAL mode + busy-timeout retry

- Good: Simpler architecture — no temp databases or merge step
- Good: Already have WAL mode enabled
- Bad: `SQLITE_BUSY` retries are non-deterministic and degrade under contention
- Bad: Page-level locking means different chromosomes can still conflict
- Bad: Hard to tune `busy_timeout` — too low = errors, too high = serialization

### Option 3: Writer queue with single commit thread

- Good: Single writer eliminates contention
- Good: Workers stay simple (just produce tuples)
- Bad: Queue becomes a bottleneck if workers produce faster than consumer writes
- Bad: Complex coordination: queue draining, backpressure, shutdown ordering
- Bad: Over-engineered for 24-25 contigs with moderate write volume

## More Information

- GitHub issue: #66
- ADR-0009: Fast annotation mode (`--fast` flag)
- ADR-0001: Patch architecture (SQLite overlay design)
- `concurrent.futures.ProcessPoolExecutor` stdlib docs
