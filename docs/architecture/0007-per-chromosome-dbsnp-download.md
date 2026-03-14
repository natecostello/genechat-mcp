---
status: accepted
date: 2026-03-14
related ADRs:
  - [0001-patch-architecture.md](0001-patch-architecture.md)
---

# Per-Chromosome dbSNP Download via Remote Region Queries

## Context and Problem Statement

The dbSNP reference VCF (~28 GB compressed, ~1.1 billion variants) must be
downloaded and contig-renamed (RefSeq NC_* → chr*) before it can be used for
rsID annotation. On constrained environments like Fly.io (50 GB disk), the
download/rename pipeline faces a tension between disk budget and resumability:

- **File-based approach**: Download raw file (~28 GB), rename to chrfixed
  (~20 GB). Supports HTTP Range resume. Peak ~48 GB — exceeded the 50 GB
  volume and caused a disk-full failure in production (issue #53 in
  genechat-mcp-remote-demo).
- **Streaming approach** (PR #47): Pipe download directly through bcftools
  rename. Peak ~20 GB. Not resumable — gzip streams require decompression
  from byte 0; can't resume mid-block.

The streaming approach fits on disk but offers no recovery from failures during
the multi-hour download. Resume support is required.

## Decision Drivers

- **50 GB disk constraint**: Must stay well under 50 GB peak during the full
  `genechat init --gnomad --dbsnp --gwas` pipeline
- **Resumability**: A 2–3 hour download is fragile; failures must not require
  restarting from scratch
- **Bounded blast radius**: Individual failures should affect minutes of work,
  not hours
- **No upstream per-chromosome files**: NCBI publishes a single whole-genome
  dbSNP VCF per assembly — there are no per-chromosome splits available
- **bgzip + tabix index available**: The dbSNP file is bgzipped with a .tbi
  index (~3 MB), enabling HTTP Range random access via htslib

## Considered Options

1. **Accept restart-from-scratch** — Keep the streaming approach, add retry
   logic for transient HTTP errors within the stream
2. **Per-chromosome remote region queries** — Use bcftools + htslib HTTP Range
   requests to fetch one chromosome at a time from the remote server
3. **Bigger disk** — Increase Fly.io volume to 60+ GB to accommodate the
   file-based approach with HTTP resume

## Decision Outcome

Chosen option: **2 — Per-chromosome remote region queries**, because it
provides per-chromosome resumability within the existing disk budget, without
requiring infrastructure changes or accepting fragile multi-hour downloads.

Verified that bcftools supports remote region queries against the NCBI dbSNP
URL — chr22 (16M records) completed in 23 seconds locally:

```bash
bcftools view -r NC_000022.11 \
  "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/GCF_000001405.40.gz" \
  | bcftools annotate --rename-chrs refseq_to_chr.txt - -Oz -o chr22.vcf.gz
```

Plan: `docs/plans/per-chromosome-dbsnp.md` (created at 837d6ee, removed after implementation)

### Consequences

**Good:**
- Peak disk ~22 GB (one chromosome temp + growing output) — comfortable margin
  on 50 GB volumes
- Per-chromosome resume: on failure, skip completed chromosomes and retry only
  the failed one
- Each chromosome takes 1–5 minutes — bounded blast radius
- Progress reporting is natural: "chromosome 5/25"

**Bad:**
- 25 separate HTTP sessions instead of one continuous stream — slightly more
  connection overhead
- Depends on NCBI supporting HTTP Range requests against bgzipped files (they
  do today; htslib depends on this widely)
- Total download time may be slightly longer due to connection setup overhead

**Neutral:**
- Total data transferred is the same (~28 GB) — just fetched in 25 chunks
  instead of one stream
- Final output (chrfixed.vcf.gz + .tbi) is identical regardless of approach

## Confirmation

- Unit tests: mock bcftools and HTTP responses to verify per-chromosome
  pipeline, resume logic (skip completed chromosomes), and state file
  management
- Integration test: verify that `bcftools concat` of per-chromosome outputs
  produces a valid bgzipped VCF with correct contig names
- Disk budget: verify peak disk stays under 25 GB during dbSNP processing
  in the full annotation pipeline

## Pros and Cons of the Options

### Option 1: Accept restart-from-scratch

Keep the current streaming approach from PR #47. Add retry logic (exponential
backoff) for transient HTTP errors within the stream.

- Good: Simplest implementation — no architectural change
- Good: Lowest peak disk (~20 GB)
- Bad: A failure at hour 2 of a 3-hour download loses all progress
- Bad: No way to resume gzip stream from arbitrary byte offset
- Bad: Retry logic only helps transient errors, not connection drops or
  server timeouts

### Option 2: Per-chromosome remote region queries

Use htslib's HTTP Range support to fetch individual chromosomes from the
remote bgzipped+tabix-indexed dbSNP file.

- Good: Per-chromosome resumability — failure loses 1–5 minutes, not hours
- Good: Peak disk ~22 GB — comfortable margin on 50 GB
- Good: Natural progress reporting ("chromosome 5/25")
- Good: Each chromosome is independently retryable
- Bad: 25 HTTP sessions instead of 1 — slightly more overhead
- Bad: Depends on NCBI's HTTP Range support (well-established, htslib relies
  on it widely)
- Bad: More complex implementation (state tracking, concat step)

### Option 3: Bigger disk

Increase Fly.io volume to 60+ GB. Use the file-based approach with HTTP Range
resume on the raw download.

- Good: Full HTTP resume support on the download
- Good: Simple implementation — no architectural change
- Bad: Doesn't solve the problem — just moves the threshold
- Bad: Increases infrastructure cost (~$0.90/month more)
- Bad: Other users with constrained disks still can't use dbSNP
- Bad: Peak ~48 GB still leaves minimal headroom

## More Information

- GitHub issue: natecostello/genechat-mcp#49
- Related demo repo issue: natecostello/genechat-mcp-remote-demo#53
- PR #47: Streaming dbSNP + progress reporting (current approach)
- PR #50: Implementation
- Disk usage analysis: baseline 3.5 GB → peak 28 GB → final 28.1 GB for
  full init pipeline
