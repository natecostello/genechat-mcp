---
status: proposed
date: 2026-03-14
related ADRs:
  - [0007-per-chromosome-dbsnp-download.md](0007-per-chromosome-dbsnp-download.md)
---

# Fast Annotation Mode (`--fast`)

## Context and Problem Statement

ADR-0007 introduced per-chromosome dbSNP download via htslib HTTP Range
requests to fit within a 50 GB disk budget. This approach provides excellent
resumability and bounded disk usage (~22 GB peak), but is ~20x slower than
bulk download + local processing on disk-unconstrained machines.

Observed on Fly.io `shared-cpu-2x` (IAD region):
- Per-chromosome dbSNP: 60–80 min/chromosome × 25 = **25+ hours**
- `/proc/stat` breakdown: 48.6% CPU steal, 44.5% idle (HTTP wait), 5.4% user
- ClinVar bulk download from the same NCBI server: 235 MB/s
- ADR-0007 local benchmark: chr22 in 23 seconds

The idle time is caused by htslib's block-by-block HTTP Range requests — each
64 KB bgzip block requires a separate round trip to NCBI. On shared CPUs with
high steal, these round trips dominate wall-clock time.

gnomAD's incremental mode (download one chromosome, annotate, delete) has a
similar but smaller impact: annotation waits for each per-chromosome download
instead of annotating from pre-cached local files.

The intended deployment workflow on Fly.io is to temporarily scale the machine
to a performance class with expanded rootfs (`fly machine update --vm-size
performance-2x --rootfs-size 60`), run annotation, then scale back down. This
workflow needs a matching "fast" annotation mode in genechat.

## Decision Drivers

- **20x wall-clock penalty** on shared-cpu machines for the disk-safe default
- **Fly.io supports temporary scaling**: `--vm-size` and `--rootfs-size` flags
  allow ephemeral large machines for annotation
- **Piped download avoids raw file on disk**: `curl | bcftools annotate
  --rename-chrs` writes only the output (~28 GB peak), not raw + output
  (~56 GB peak)
- **Backward compatibility**: disk-constrained users (laptops, small VMs) must
  keep the current default behavior
- **Simplicity**: one flag, not a matrix of per-source mode options

## Considered Options

1. **`--fast` flag on `init` and `annotate`** — bulk/piped downloads, no
   per-chromosome splitting for dbSNP, non-incremental gnomAD
2. **Automatic mode selection** — detect available disk and choose mode
3. **Separate `download-refs` command** — decouple reference acquisition from
   annotation, let users pre-stage files
4. **Do nothing** — users pre-stage references manually

## Decision Outcome

Chosen option: **1 — `--fast` flag**, because it's explicit, simple, and
backward-compatible. Automatic detection (option 2) is fragile — available
disk is hard to probe reliably across platforms. A separate download command
(option 3) is useful but orthogonal — `--fast` can be added now and a
`download-refs` command later if needed.

Plan: `docs/plans/fast-annotation-mode.md` (created at 78e0da3)

### Consequences

**Good:**
- ~20x faster annotation on capable hardware (~1–2 hours vs 25+ hours)
- Same final output (patch.db, metadata) regardless of mode
- Enables a clean Fly.io workflow: scale up → `init --fast` → scale down
- No breaking changes to default behavior

**Bad:**
- ~180 GB peak disk with `--fast` (vs ~30 GB default) — requires user to
  ensure sufficient space
- dbSNP piped download is not resumable (acceptable when annotation takes
  minutes, not hours)
- Two code paths to maintain for dbSNP download

**Neutral:**
- gnomAD non-incremental mode already exists (it's the default when files are
  pre-cached); `--fast` just triggers the pre-download explicitly

## Confirmation

- Unit tests: mock bcftools/curl, verify piped dbSNP produces correct output
- Unit tests: verify `--fast` triggers non-incremental gnomAD path
- Integration test: `--fast` on a test VCF produces identical patch.db content
  to default mode
- Disk budget: verify `--fast` peak stays under 180 GB (dbSNP 28 GB + gnomAD
  150 GB) and default stays under 30 GB

## Pros and Cons of the Options

### Option 1: `--fast` flag

- Good: Explicit opt-in — no surprises for disk-constrained users
- Good: One flag controls all sources — simple mental model
- Good: Backward-compatible — default behavior unchanged
- Bad: Two code paths for dbSNP (piped bulk vs per-chromosome)
- Bad: User must know they have enough disk

### Option 2: Automatic mode selection

- Good: Zero-config — users don't need to think about it
- Bad: `shutil.disk_usage()` is unreliable (tmpfs, overlayfs, quotas)
- Bad: Threshold choice is arbitrary — what's "enough" disk?
- Bad: Surprising behavior changes when disk conditions change

### Option 3: Separate `download-refs` command

- Good: Full user control over reference acquisition
- Good: Enables pre-staging, caching, sharing references across genomes
- Bad: More complex user workflow (two commands instead of one)
- Bad: Doesn't solve the annotation speed problem on its own
- Neutral: Could be added later as a complement to `--fast`

### Option 4: Do nothing

- Good: No code changes
- Bad: Users must manually download and place reference files
- Bad: Undocumented, error-prone process

## More Information

- GitHub issue: #55
- ADR-0007: Per-chromosome dbSNP download (the current default approach)
- Fly.io `--rootfs-size` and `--vm-size` flags for temporary scaling
- Observed performance data from genechat-mcp-remote-demo deployment
