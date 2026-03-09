# Plan: Patch Architecture — Raw VCF + Annotation Patch (v4)

## Overview

Replace the pre-annotated VCF with a **raw VCF + patch.db** model. The raw VCF stays untouched. All annotations (SnpEff, ClinVar, gnomAD, dbSNP) are stored in a SQLite "patch" database. At query time, the engine joins the raw VCF genotypes with the patch annotations on (chrom, pos, ref, alt).

**Key design decision:** Patch generation uses the **same proven tools** (bcftools, SnpEff) that the current pipeline uses. We pipe their output through a Python parser that extracts annotations into SQLite instead of writing a modified VCF. This means:
- bcftools handles all allele matching, normalization, and contig renaming
- SnpEff handles all functional annotation via Java
- We do NOT reimplement any variant matching logic in Python
- The only new code parses VCF text output and INSERTs into SQLite

## Functional Equivalence Guarantee

**The patch architecture produces identical results to the annotated VCF approach.** Here is why this is necessarily true, not just an aspiration:

1. **Same annotation engine, same inputs.** Both architectures run the exact same commands: `snpEff ann` for functional annotation, `bcftools annotate -a clinvar.vcf.gz -c INFO/CLNSIG,...` for ClinVar, etc. The raw VCF is the same. The reference databases are the same. bcftools/SnpEff produce the same output regardless of whether it's piped to `bgzip` or to a Python parser.

2. **Annotation matching happens in bcftools, not in our code.** The current pipeline: bcftools matches variants by (chrom, pos, ref, alt), adds INFO fields, writes an annotated VCF. The patch pipeline: bcftools does the same matching, adds the same INFO fields, writes the same VCF text — but instead of compressing to .vcf.gz, a Python parser extracts those fields into SQLite rows. The matching logic is byte-for-byte identical because it's the same bcftools binary doing the same work.

3. **The runtime join cannot fail.** The patch.db rows were extracted from bcftools/SnpEff processing the raw VCF. The (chrom, pos, ref, alt) keys in patch.db came directly from that VCF's records. When pysam reads the same raw VCF at runtime, it reads the same records with the same keys. There is no normalization, no contig renaming, no allele matching at query time — just a dict lookup on keys that are guaranteed to match because they came from the same file.

4. **The output dict is identical.** The variant dict structure (`chrom`, `pos`, `rsid`, `ref`, `alt`, `genotype`, `annotation`, `clinvar`, `population_freq`) is unchanged. All tool code consumes these dicts. No tool code changes.

### Verification: end-to-end parity test

To prove this claim mechanically, not just argue it:

```python
def test_patch_parity():
    """Annotated VCF and raw VCF + patch.db produce identical variant dicts."""
    # Engine A: current approach (annotated VCF)
    engine_a = VCFEngine(config_annotated)
    # Engine B: patch approach (raw VCF + patch.db)
    engine_b = VCFEngine(config_raw_plus_patch)

    # Compare on known test variants
    for rsid in ["rs4149056", "rs113993960", "rs1815739"]:
        assert engine_a.query_rsid(rsid) == engine_b.query_rsid(rsid)

    # Compare on gene regions
    for gene_region in ["chr12:21100000-21300000", "chr7:117500000-117700000"]:
        assert engine_a.query_region(gene_region) == engine_b.query_region(gene_region)

    # Compare ClinVar queries
    assert engine_a.query_clinvar("athogenic") == engine_b.query_clinvar("athogenic")
```

This test ships with the implementation. If it passes, the two architectures are functionally equivalent. If it fails, we fix the patch code until it passes.

---

## Current Architecture

```
raw.vcf.gz
    -> annotate.sh (SnpEff + bcftools annotate x 3, ~30 min)
    -> annotated.vcf.gz (2 GB, all annotations baked into INFO fields)
    -> VCFEngine reads one file, parses INFO fields per record
```

## Proposed Architecture

```
genechat init my.vcf.gz
    -> genechat add      (validate VCF, create index, write config — instant)
    -> genechat annotate (ClinVar + SnpEff DB to shared cache — ~5-10 min)
    -> genechat annotate  (pipe bcftools/SnpEff output -> SQLite — ~20-30 min)
    -> write MCP config snippet

Result:
    raw.vcf.gz (untouched)  +  my.patch.db (SQLite, ~500 MB - 1 GB)

At runtime (genechat serve):
    VCFEngine opens raw.vcf.gz (pysam) + patch.db (SQLite)
    Each query: pysam genotypes + patch annotations joined by (chrom, pos, ref, alt)
```

---

## CLI Commands

Seven commands: 4 plumbing primitives + 2 porcelain compositions + 1 server.

### Overview

| Command | Type | What it does | Runtime | Network? |
|---------|------|-------------|---------|----------|
| `genechat init <vcf>` | Porcelain | Full first-time setup | 25-35 min | Yes |
| `genechat add <vcf> [--label NAME]` | Plumbing | Register a VCF: validate, index, write config | ~1 sec | No |
| `genechat install [--gwas]` | Plumbing | Install genome-independent databases (GWAS) | ~2 min | Yes |
| `genechat annotate [--label NAME] [--clinvar\|...]` | Plumbing | Build/update patch.db for a registered VCF | 2-45 min | No |
| `genechat update [--apply]` | Plumbing | Check for newer refs; `--apply` downloads + re-annotates | 5 sec / 5-45 min | Yes |
| `genechat status` | Plumbing | Show genome info, annotation state, reference versions | ~1 sec | No |
| `genechat serve` / bare `genechat` | — | Start MCP server | Long-lived | No |

**Typical user lifecycle (4-command vocabulary for 95% of usage):**

```
genechat init my.vcf.gz      # day 1 (once, ~30 min)
genechat                     # daily (MCP client runs this as the server command)
genechat update --apply      # monthly (one command to check + download + re-annotate)
genechat status              # whenever confused about what's installed/current
```

---

### Porcelain: `genechat init <raw.vcf.gz> [--label NAME]`

The primary entry point. Does the whole job for first-time setup.

Composes: `add` + `download` + `annotate` + write MCP config snippet.

1. Validate VCF exists and is readable (pysam)
2. Check for index (.tbi/.csi), create if missing (pysam.tabix_index)
3. Register VCF in config (`add`)
4. Download recommended references — ClinVar + SnpEff DB (~1.7 GB) (`download`)
5. Build patch.db — all annotation steps (`annotate`)
6. Build lookup_tables.db if missing
7. Write config.toml to `~/.config/genechat/`
8. Print MCP JSON snippet

**Idempotent:** Re-running `init` detects completed steps and skips them. Safe to re-run after a partial failure (e.g., if annotation fails at minute 35, references are preserved, re-run picks up from annotation).

**On failure, prints recovery guidance:**
```
Error: Annotation failed (disk full). Your VCF is registered and references were downloaded.
To retry: genechat annotate
```

The optional `--label` flag names this genome in the config (default: derived from VCF filename). Invisible in v1 single-genome usage, enables `genechat add partner.vcf.gz --label partner` for future multi-VCF.

**Estimated time (first run):** ~25-35 min (downloads + annotation)
**Estimated time (re-run):** ~1 second (everything skipped)

---

### Plumbing: `genechat add <vcf> [--label NAME]`

Register a VCF file. Instant, no network, no heavy processing.

1. Validate VCF exists and is readable (pysam opens it)
2. Check for .tbi/.csi index, create if missing
3. Write entry to config.toml

This is the multi-VCF verb: `genechat add partner.vcf.gz --label partner` registers a second genome. In v1 with a single genome, `init` calls `add` internally and the user never invokes it directly.

**If VCF already registered:** Prints current status, no error (idempotent).

---

### Plumbing: `genechat install [--gwas] [--force]`

Install genome-independent reference databases. Currently supports GWAS Catalog only.

| Flag | What | Size | Time estimate |
|------|------|------|---------------|
| `--gwas` | GWAS Catalog associations | ~58 MB download, ~300 MB on disk | ~2 min |
| `--force` | Re-download even if files exist | — | — |

Annotation-layer databases (ClinVar, SnpEff, gnomAD, dbSNP) are downloaded automatically by `genechat annotate` — they are per-genome annotation dependencies, not standalone installs.

**Idempotent:** Skips files that already exist. `--force` overrides.

**References are shared across all genomes** — they're genome-build-specific (GRCh38), not sample-specific.

**Note on SnpEff DB:** This is the one download requiring Java. If Java/SnpEff are not installed, download succeeds for everything else and prints a warning. The `annotate` step will fail clearly if SnpEff is missing.

---

### Plumbing: `genechat annotate [options]`

Build or update the patch.db for a registered VCF. Compute-heavy, no network (references must already be downloaded).

| Flag | What happens |
|------|-------------|
| (no flags, first run) | Run all annotation steps for the registered VCF |
| (no flags, patch.db exists) | Print annotation status and exit |
| `--clinvar` | Re-annotate ClinVar layer only |
| `--gnomad` | Re-annotate gnomAD layer only |
| `--snpeff` | Re-annotate SnpEff layer only |
| `--dbsnp` | Re-annotate dbSNP layer only |
| `--all` | All layers |
| `--label NAME` | Select which genome to annotate (future multi-VCF) |

**When references are missing, fails with actionable guidance:**
```
$ genechat annotate
Error: ClinVar reference not found.
Run `genechat annotate` to download references and build annotations (~1.8 GB).
```

**When optional references are not installed, annotates what it can:**
```
$ genechat annotate
Building patch.db for genome "default" (/data/my.vcf.gz)...
  [1/4] SnpEff functional annotation... done (18 min)
  [2/4] ClinVar clinical significance... done (3 min)
  [3/4] gnomAD population frequencies... skipped (not installed)
        → Population frequency data will be unavailable. Run: genechat annotate --gnomad (~8 GB)
  [4/4] dbSNP rsID backfill... skipped (not installed)
        → Some variants will lack rsID identifiers. Run: genechat annotate --dbsnp (~20 GB)
Patch database: /data/my.patch.db (487 MB, 4,892,341 variants)
```

**Idempotent:** Completed annotation layers are skipped unless explicitly re-requested with `--clinvar`, `--snpeff`, etc.

Each annotation layer pipes bcftools/SnpEff output through a Python VCF line parser that extracts the relevant fields into patch.db.

#### First run (no patch.db exists) — all layers run:

**Step 1: SnpEff — functional annotation + rsID capture**

```bash
# What actually executes (per chromosome, to avoid OOM):
snpEff ann GRCh38.p14 <(bcftools view -r chr1 raw.vcf.gz) \
    | python -c "parse each line, extract ANN field + ID column, INSERT into patch.db"
```

- SnpEff reads the raw VCF (per chromosome), adds the ANN field
- SnpEff passes the ID column through unchanged — provider rsIDs are preserved
- Python parser reads SnpEff's stdout line by line
- For each variant line: extract (chrom, pos, ref, alt, rsid, ANN fields) and INSERT into patch.db
- **rsID capture:** The parser extracts the VCF ID column (col 2) for every record. If the raw VCF already has rsIDs from the sequencing provider, they are stored in patch.db immediately. Step 4 (dbSNP) only fills in records where rsid IS NULL.
- Per-chromosome processing avoids JVM OOM (proven pattern from current scripts)
- No intermediate VCF written to disk

**Time estimate: ~15-25 min** (SnpEff processing speed is the bottleneck, ~3K-5K variants/sec. 5M variants / 4K/sec = ~20 min. Per-chromosome overhead adds ~10-20%)

**External tools:** Java + SnpEff (subprocess)

**Step 2: ClinVar — clinical significance**

```bash
# What actually executes:
bcftools annotate -a clinvar_chrfixed.vcf.gz \
    -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
    raw.vcf.gz \
    | python -c "parse each line, extract CLNSIG/CLNDN/CLNREVSTAT, UPDATE patch.db"
```

- bcftools does the allele-aware matching and contig rename handling (same as current pipeline)
- Python parser reads bcftools stdout, extracts the ClinVar INFO fields
- For each variant that gained ClinVar fields: UPDATE the existing patch.db row (row was created in Step 1)
- ClinVar contig rename: if needed, run `bcftools annotate --rename-chrs` on ClinVar first (same as current `annotate.sh` logic)

**Time estimate: ~2-5 min** (bcftools annotation throughput: ~20K-50K variants/sec. 5M variants = ~100-250 sec. Add contig rename overhead and Python parsing.)

**External tools:** bcftools (subprocess)

**Step 3: gnomAD — population frequencies (if downloaded)**

```bash
# What actually executes (per chromosome):
bcftools annotate -a gnomad.exomes.v4.1.sites.chr1.vcf.bgz \
    -c INFO/AF,INFO/AF_grpmax \
    <(bcftools view -r chr1 raw.vcf.gz) \
    | python -c "parse each line, extract AF/AF_grpmax, UPDATE patch.db"
```

- Per-chromosome annotation (same pattern as current `annotate.sh`)
- bcftools handles the matching
- Python extracts AF and AF_grpmax from annotated output

**Time estimate: ~5-10 min** (24 chromosomes x bcftools annotate. gnomAD per-chrom files are large, tabix lookups take time. Current shell script takes ~10-15 min; this should be comparable since bcftools does the same work.)

**External tools:** bcftools (subprocess)

**Step 4: dbSNP — rsID backfill (if downloaded)**

```bash
# What actually executes:
bcftools annotate -a dbsnp_chrfixed.vcf.gz \
    -c ID \
    -i 'ID="."' \
    raw.vcf.gz \
    | python -c "parse each line, extract ID column, UPDATE patch.db WHERE rsid IS NULL"
```

- bcftools fills the ID column from dbSNP (only for records with ID=`.`)
- Python parser extracts the ID field for records where it changed from `.`
- Only updates `rsid` column in patch.db where rsid IS NULL (doesn't overwrite provider rsIDs captured in Step 1)
- dbSNP contig rename handled by bcftools (same GRCh38 RefSeq->chr map from current scripts)

**Time estimate: ~5-10 min** (dbSNP is ~20GB, bcftools needs to scan it. Current shell script takes ~5-10 min.)

**External tools:** bcftools (subprocess)

**Step 5: Build indexes + record metadata**

```sql
CREATE INDEX idx_ann_rsid ON annotations(rsid) WHERE rsid IS NOT NULL;
CREATE INDEX idx_ann_clnsig ON annotations(clnsig) WHERE clnsig IS NOT NULL;
CREATE INDEX idx_ann_gene ON annotations(gene) WHERE gene IS NOT NULL;
CREATE INDEX idx_ann_pos ON annotations(chrom, pos);

INSERT INTO patch_metadata VALUES ('snpeff', 'GRCh38.p14', '2026-03-07', 'complete');
INSERT INTO patch_metadata VALUES ('clinvar', '2026-03-07', '2026-03-07', 'complete');
-- etc.
```

**Time estimate: ~30-60 sec** (index creation on 5M rows)

**Step 6: Integrity verification**

After all annotation steps complete, run a count verification:

```python
# Count records in raw VCF
vcf_count = sum(1 for _ in pysam.VariantFile(raw_vcf))
# Count records in patch.db
patch_count = conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0]
# Every variant in the raw VCF should have a patch.db row (Step 1 processes all)
assert patch_count == vcf_count, f"Mismatch: VCF has {vcf_count}, patch.db has {patch_count}"
```

Also store a VCF fingerprint for staleness detection:

```python
# Store raw VCF identity in patch_metadata
import os
stat = os.stat(raw_vcf)
fingerprint = f"{stat.st_size}:{stat.st_mtime_ns}"
conn.execute("INSERT INTO patch_metadata VALUES ('vcf_fingerprint', ?, ?, 'complete')",
             (fingerprint, datetime.now().isoformat()))
```

At engine startup, compare stored fingerprint against current VCF. If mismatched, warn:
```
WARNING: raw VCF has changed since patch.db was built. Run `genechat annotate` to update.
```

#### Total first-run timing

| Minimum (ClinVar + SnpEff) | Full (all references) |
|---|---|
| ~20-30 min | ~30-45 min |

These estimates are **conservative** — we've been consistently surprised by how long things take. The current full pipeline takes ~30 min, and we're doing the same work with bcftools/SnpEff plus Python parsing overhead. First run may be **comparable or slightly slower** than the current pipeline due to the Python parsing layer.

#### Incremental update (patch.db exists):

```
genechat annotate --clinvar
  -> Downloads latest ClinVar VCF if stale
  -> Within a single transaction: clears clnsig/clndn/clnrevstat columns, re-runs Step 2, commits
  -> Time: ~2-5 min

genechat annotate --gnomad
  -> Downloads gnomAD VCFs if missing
  -> Within a single transaction: clears af/af_grpmax columns, re-runs Step 3, commits
  -> Time: ~5-10 min (+ download time if first run)

genechat annotate --snpeff
  -> Within a single transaction: clears gene/effect/impact/transcript/hgvs_c/hgvs_p columns, re-runs Step 1, commits
  -> Time: ~15-25 min

genechat annotate --dbsnp
  -> Downloads dbSNP VCF if missing
  -> Within a single transaction: clears rsid WHERE rsid_source='dbsnp', re-runs Step 4, commits
  -> Time: ~5-10 min (+ download time if first run)

genechat annotate --all
  -> All steps
  -> Time: ~30-45 min
```

`annotate` reads the VCF path from config (written by `init`/`add`). In a future multi-VCF setup, `--label` selects which genome to re-annotate. Or use `genechat update --apply` to check + download + re-annotate all stale sources in one command.

**Idempotency:** If patch.db exists and no flags specified, print status and exit:
```
Patch database: /path/to/patch.db (487 MB, 4,892,341 variants)
  SnpEff:  GRCh38.p14    (2026-03-01)  [complete]
  ClinVar: 2026-03-01                   [complete]
  gnomAD:  v4.1          (2026-03-01)  [complete]
  dbSNP:   2026-03-01                   [complete]
Use --clinvar, --snpeff, --gnomad, --dbsnp, or --all to update.
```

**Concurrent access safety:** patch.db uses WAL mode (set at creation). All incremental updates wrap clear + repopulate in a single transaction. The MCP server sees either the old data or the new data, never a partially-cleared state. WAL mode allows readers (MCP server) and writers (annotate command) to operate concurrently without blocking.

---

### Plumbing: `genechat update [--apply] [--clinvar|--gnomad|...]`

Check for newer versions of reference databases.

**Default (no flags): check-only, read-only.** Requires network (HTTP HEAD requests, no downloads).

```
$ genechat update
Checking for newer reference versions...

Source     Installed          Latest Available   Status
ClinVar   2026-01-15         2026-03-06         update available
gnomAD    v4.1               v4.1               up to date
SnpEff    GRCh38.p14         GRCh38.p14         up to date
dbSNP     Build 156          Build 157          update available (not installed)
GWAS      2026-02-20         2026-03-05         update available

2 installed source(s) can be updated. Apply with:
  genechat update --apply              # download + re-annotate all stale sources
  genechat update --apply --clinvar    # update ClinVar only
```

**With `--apply`: download newer references + re-annotate affected layers.** This is the single command for "make everything current" — composes `download` + `annotate` for stale sources. Eliminates the need for users to understand the dependency chain between commands.

```
$ genechat update --apply
Downloading ClinVar 2026-03-06... done (45 sec)
Downloading GWAS Catalog 2026-03-05... done (12 sec)
Re-annotating ClinVar layer... done (3 min)
Rebuilding GWAS associations... done (20 sec)
All sources up to date.
```

---

### Plumbing: `genechat status`

Show the current state of everything. No network, no changes.

```
$ genechat status
Genome: "default" (/data/my.vcf.gz)
  VCF:      valid, indexed (4.2M variants)
  Patch DB: /data/my.patch.db (487 MB, built 2026-03-01)

Annotations:
  SnpEff:   GRCh38.p14       (applied 2026-03-01)
  ClinVar:  2026-01-15       (applied 2026-03-01)
  gnomAD:   not installed
  dbSNP:    not installed
  GWAS:     2026-02-20       (applied 2026-03-01)

References: ~/.local/share/genechat/references/
  ClinVar VCF:  installed (2026-01-15)
  SnpEff DB:    installed (GRCh38.p14)
  gnomAD:       not installed — genechat annotate --gnomad
  dbSNP:        not installed — genechat annotate --dbsnp
  GWAS Catalog: installed (2026-02-20)

Run `genechat update` to check for newer versions.
```

Subsumes the "where am I?" question without requiring network access. Shows genome info, annotation state, reference versions, and actionable next steps.

---

### `genechat serve` / bare `genechat`

Starts the MCP server. Validates state at startup (VCF exists, patch.db exists, no stale fingerprint). Loads all registered genomes from config — each gets its own VCFEngine instance backed by its raw VCF + patch.db.

---

## Patch Database Schema

```sql
-- WAL mode for concurrent read/write safety
PRAGMA journal_mode=WAL;

-- One row per variant in the raw VCF.
-- Step 1 (SnpEff) creates ALL rows. Steps 2-4 UPDATE existing rows.
-- Key matches exactly what bcftools/SnpEff output: (chrom, pos, ref, alt)
-- This key is guaranteed to match pysam's view of the raw VCF because
-- the rows were extracted from processing that same VCF.
CREATE TABLE annotations (
    chrom TEXT NOT NULL,
    pos INTEGER NOT NULL,
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    -- rsID: from raw VCF ID column (Step 1) or dbSNP backfill (Step 4)
    rsid TEXT,
    rsid_source TEXT,  -- 'vcf' or 'dbsnp' (to know which to clear on update)
    -- SnpEff (Step 1)
    gene TEXT,
    effect TEXT,
    impact TEXT,
    transcript TEXT,
    hgvs_c TEXT,
    hgvs_p TEXT,
    -- ClinVar (Step 2)
    clnsig TEXT,
    clndn TEXT,
    clnrevstat TEXT,
    -- gnomAD (Step 3)
    af REAL,
    af_grpmax REAL,
    PRIMARY KEY (chrom, pos, ref, alt)
);

-- Partial indexes for fast lookups on sparse columns
CREATE INDEX idx_ann_rsid ON annotations(rsid) WHERE rsid IS NOT NULL;
CREATE INDEX idx_ann_clnsig ON annotations(clnsig) WHERE clnsig IS NOT NULL;
CREATE INDEX idx_ann_gene ON annotations(gene) WHERE gene IS NOT NULL;
CREATE INDEX idx_ann_pos ON annotations(chrom, pos);

-- Version tracking + completion status
CREATE TABLE patch_metadata (
    source TEXT PRIMARY KEY,   -- 'snpeff', 'clinvar', 'gnomad', 'dbsnp', 'vcf_fingerprint'
    version TEXT,              -- e.g. 'GRCh38.p14', 'v4.1', '<size>:<mtime>'
    updated_at TEXT,           -- ISO date
    status TEXT DEFAULT 'pending'  -- 'pending' or 'complete'
);
```

**Estimated size:**
- ~5M rows (one per variant in the raw VCF — Step 1 creates all rows)
- Most rows have SnpEff columns populated; ClinVar/gnomAD/dbSNP are sparse
- ~100-150 bytes per row average with overhead
- **~500 MB - 1 GB on disk** with indexes (conservative estimate)
- Compared to ~2 GB for the current annotated VCF
- During annotation, WAL file may add up to ~1 GB temporarily

---

## The VCF Line Parser

The core new code is a VCF line parser that reads bcftools/SnpEff stdout and extracts annotations. This is NOT a full VCF parser — it only needs to extract specific INFO fields from text lines.

```python
def parse_vcf_stream(stream, extract_fields: list[str]) -> Iterator[dict]:
    """Parse a VCF text stream, yielding dicts with (chrom, pos, ref, alt, rsid, {fields}).

    Skips header lines (starting with #).
    Extracts the ID column (rsid) and the requested INFO fields.
    """
    for line in stream:
        if line.startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t", 9)  # only split what we need
        chrom, pos, id_col, ref, alt = cols[0], int(cols[1]), cols[2], cols[3], cols[4]
        info = cols[7]

        extracted = {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}
        if id_col != ".":
            extracted["rsid"] = id_col

        for field in extract_fields:
            # Find exact field=value in semicolon-delimited INFO string.
            # Search for ;FIELD= or beginning-of-string FIELD= to avoid
            # substring collisions (e.g. AF vs AF_grpmax).
            value = _extract_info_field(info, field)
            if value is not None:
                extracted[field] = value

        yield extracted


def _extract_info_field(info: str, field: str) -> str | None:
    """Extract a specific INFO field value, avoiding substring collisions.

    Searches for the field preceded by ';' or at start of string,
    followed by '=', to prevent 'AF' matching 'AF_grpmax'.
    """
    target = f"{field}="
    # Check start of INFO string
    if info.startswith(target):
        start = len(target)
        end = info.find(";", start)
        return info[start:end] if end != -1 else info[start:]
    # Check after semicolons
    target = f";{field}="
    idx = info.find(target)
    if idx != -1:
        start = idx + len(target)
        end = info.find(";", start)
        return info[start:end] if end != -1 else info[start:]
    return None
```

The `_extract_info_field` function avoids the substring collision issue (e.g., `AF` matching inside `AF_grpmax`) by requiring the field name to appear at the start of the INFO string or after a semicolon delimiter.

---

## Engine Changes

### VCFEngine — one instance per genome:

```python
class VCFEngine:
    def __init__(self, vcf_path: Path, patch_db_path: Path | None = None, ...):
        """Each VCFEngine instance represents one genome (one VCF + its patch.db).

        The server creates one engine per genome in the config. Today that's
        always one. Multi-VCF support creates multiple engines.
        """
        self.vcf_path = vcf_path
        # ... existing validation ...

        # Open patch database if provided
        if patch_db_path and patch_db_path.exists():
            self._patch_conn = sqlite3.connect(f"file:{patch_db_path}?mode=ro", uri=True)
            self._patch_conn.row_factory = sqlite3.Row
            self._use_patch = True
            self._check_vcf_fingerprint()
        else:
            self._patch_conn = None
            self._use_patch = False
            # Backward compat: read annotations from VCF INFO (current behavior)
```

Note: the constructor takes explicit paths rather than a config object. This makes it natural to create multiple engines from a multi-genome config. The server wiring handles config -> engine instantiation.

### _record_to_dict changes:

Current: reads genotype + annotations from one pysam record (annotations baked into VCF INFO).
New: reads genotype from pysam, annotations from patch.db (pre-fetched for the region).

```python
def _record_to_dict(self, record, sample_idx, patch_row=None):
    # Genotype: always from raw VCF (unchanged)
    genotype = self._parse_genotype(record, sample_idx)

    alt = ",".join(record.alts) if record.alts else "."

    if patch_row:
        # Annotations from patch.db — already decomposed into columns
        rsid = patch_row["rsid"]
        annotation = {
            "gene": patch_row["gene"],
            "effect": patch_row["effect"],
            "impact": patch_row["impact"],
            "transcript": patch_row["transcript"],
            "hgvs_c": patch_row["hgvs_c"],
            "hgvs_p": patch_row["hgvs_p"],
        } if patch_row["gene"] else {}
        clinvar = parse_clinvar_fields(
            patch_row["clnsig"] or "", patch_row["clndn"] or "", patch_row["clnrevstat"] or ""
        )
        population_freq = _parse_freq(patch_row["af"], patch_row["af_grpmax"])
    else:
        # Backward compat: read from VCF INFO fields (current behavior)
        rsid = record.id if record.id and record.id != "." else None
        ann_raw = self._get_info_str(record, "ANN")
        annotation = parse_ann_field(ann_raw) if ann_raw else {}
        # ... (existing ClinVar/freq parsing, unchanged)

    return {
        "chrom": record.chrom, "pos": record.pos, "rsid": rsid,
        "ref": record.ref, "alt": alt,
        "genotype": genotype, "annotation": annotation,
        "clinvar": clinvar, "population_freq": population_freq,
    }
```

**The output dict is identical in both paths.** All tool code continues to work unchanged.

### query_rsid — from full scan to indexed lookup:

```python
def query_rsid(self, rsid):
    if self._use_patch:
        # SQLite index lookup: ~1ms for the query, ~5-10ms for pysam point fetch
        rows = self._patch_conn.execute(
            "SELECT chrom, pos, ref, alt FROM annotations WHERE rsid=?", (rsid,)
        ).fetchall()
        if not rows:
            return []
        # Point-fetch genotypes from raw VCF at matched positions
        variants = []
        for row in rows:
            region = f"{row['chrom']}:{row['pos']}-{row['pos']}"
            for v in self._fetch_and_parse(region=region):
                if v["ref"] == row["ref"] and v["alt"] == row["alt"]:
                    variants.append(v)
        return variants
    else:
        # Backward compat: full VCF scan (current behavior)
        ...
```

### query_clinvar — from full scan to SQLite query:

```python
def query_clinvar(self, significance, region=None):
    if self._use_patch:
        # SQLite query on indexed column
        if region:
            chrom, coords = region.split(":")
            start, end = coords.split("-")
            rows = self._patch_conn.execute(
                "SELECT chrom, pos, ref, alt FROM annotations "
                "WHERE clnsig IS NOT NULL AND clnsig LIKE ? "
                "AND chrom=? AND pos BETWEEN ? AND ?",
                (f"%{significance}%", chrom, int(start), int(end))
            ).fetchall()
        else:
            rows = self._patch_conn.execute(
                "SELECT chrom, pos, ref, alt FROM annotations "
                "WHERE clnsig IS NOT NULL AND clnsig LIKE ?",
                (f"%{significance}%",)
            ).fetchall()
        # Fetch genotypes from raw VCF at matched positions
        ...
    else:
        # Backward compat: full VCF scan (current behavior)
        ...
```

**Performance note on LIKE queries:** A genome-wide `WHERE clnsig LIKE '%pathogenic%'` scans the `clnsig` column of ~5M rows. This is ~0.5-2 seconds — faster than the current 2-5 second full VCF scan, but not the "~10-50ms" originally estimated in v2. For region-scoped ClinVar queries, the (chrom, pos) index makes it genuinely fast (~1-10ms).

### query_region — batch patch join:

```python
def query_region(self, region, include_filter=None):
    if self._use_patch:
        chrom, coords = region.split(":")
        start, end = coords.split("-")
        # Load all patch rows for the region in one query
        patch_rows = self._patch_conn.execute(
            "SELECT * FROM annotations WHERE chrom=? AND pos BETWEEN ? AND ?",
            (chrom, int(start), int(end))
        ).fetchall()
        patch_dict = {(r["pos"], r["ref"], r["alt"]): r for r in patch_rows}

        # Iterate raw VCF, join with in-memory patch dict
        variants = []
        with pysam.VariantFile(str(self.vcf_path)) as vcf:
            sample_idx = self._get_sample_index()
            for record in vcf.fetch(region=region):
                alt = ",".join(record.alts) if record.alts else "."
                patch = patch_dict.get((record.pos, record.ref, alt))
                parsed = self._record_to_dict(record, sample_idx, patch_row=patch)
                if parsed:
                    if include_filter and not self._matches_filter_from_patch(parsed, include_filter):
                        continue
                    variants.append(parsed)
        return variants
    else:
        # Backward compat: current behavior
        ...
```

### _matches_filter adaptation:

The current `_matches_filter` reads ANN from the pysam record. In the patch model, annotations are already in the variant dict (populated from patch.db). The `include_filter` check operates on the dict instead:

```python
def _matches_filter_from_patch(self, variant_dict, filt):
    """Check impact filter against variant dict (patch mode)."""
    search = filt
    match = re.search(r'~"([^"]+)"', filt)
    if match:
        search = match.group(1)
    impact = (variant_dict.get("annotation", {}).get("impact") or "").upper()
    return search.upper() in impact
```

Note: no tool currently passes `include_filter` to `query_region`. `query_gene` does its own filtering at the tool layer (query_gene.py lines 107-113) using the variant dict, which works identically regardless of data source.

### annotation_versions() adaptation:

Currently reads `##GeneChat_*` VCF header lines. In patch mode, reads from `patch_metadata` table:

```python
def annotation_versions(self, prefix="GeneChat_"):
    if self._use_patch:
        rows = self._patch_conn.execute(
            "SELECT source, version, updated_at FROM patch_metadata WHERE status='complete'"
        ).fetchall()
        return {r["source"]: f"{r['version']} ({r['updated_at']})" for r in rows}
    else:
        # Backward compat: read from VCF headers (current behavior)
        ...
```

---

## Addressing Devil's Advocate Concerns

### "Annotations could silently go missing" — why this applies equally to the current approach

The DA identified three scenarios. None are new risks introduced by the patch architecture:

| Concern | Current annotated VCF | Patch architecture | Same risk? |
|---------|----------------------|-------------------|------------|
| **Join key mismatch** | bcftools matches (chrom,pos,ref,alt) between reference and user VCF. If no match, annotation isn't added — INFO field stays empty. | Same bcftools matching. If no match, patch.db column stays NULL. | Yes — identical |
| **Multi-allelic decomposition** | If SnpEff decomposes multi-allelics (non-default), annotated VCF has different records than raw VCF. But we don't use that flag. | Same — we don't use decomposition flags. | Yes — identical |
| **ClinVar contig rename** | If rename fails, bcftools can't match, no ClinVar annotations added. | Same bcftools rename logic, same failure mode. | Yes — identical |

The patch architecture does NOT introduce any new matching, normalization, or contig-handling logic. All of that is done by the same bcftools/SnpEff commands. The only difference is the output destination.

### rsID handling: provider rsIDs vs dbSNP backfill

**Concern:** If dbSNP annotation isn't run, rsIDs from the raw VCF might not be searchable.

**Resolution:** Step 1 (SnpEff) processes every variant and the parser extracts the VCF ID column. Provider rsIDs are stored in patch.db with `rsid_source='vcf'` during Step 1. Step 4 (dbSNP) only updates records where `rsid IS NULL`, with `rsid_source='dbsnp'`. This matches the current behavior where bcftools `-c ID` only fills `.` entries.

### ClinVar LIKE query performance

**Concern:** `WHERE clnsig LIKE '%pathogenic%'` can't use the partial index, resulting in a full column scan.

**Resolution:** Acknowledged. Genome-wide ClinVar queries will be ~0.5-2 seconds (scanning 5M rows for non-NULL clnsig LIKE pattern), not the ~10-50ms originally claimed. This is still faster than the current 2-5 second full VCF scan. Region-scoped queries use the (chrom, pos) index and are genuinely fast.

For a future optimization, we could add a normalized `clinvar_terms` table for exact-match lookups. But the 0.5-2s performance is acceptable for v1.

### Concurrent access

**Concern:** MCP server reading while `annotate --clinvar` writes could see partially-cleared data.

**Resolution:** patch.db uses WAL mode. All incremental updates wrap clear + repopulate in a single SQLite transaction. Readers see the pre-update snapshot until COMMIT. No partial states are visible.

### Stale patch.db

**Concern:** If the raw VCF is replaced, patch.db becomes stale.

**Resolution:** VCF fingerprint (file size + mtime) stored in `patch_metadata` at annotation time. Checked at engine startup. Mismatch triggers a warning. This is actually *better* than the current approach, which has no staleness detection at all.

### Parsers at runtime

**Concern:** DA said "parsers still used by engine" — partially wrong.

**Correction:** In patch mode:
- `parse_genotype` — still used (genotype comes from raw VCF, unchanged)
- `parse_ann_field` — NOT used at runtime (annotations already decomposed in patch.db columns). Only used during annotation (Step 1 parser).
- `parse_clinvar_fields` — still used at runtime to build the clinvar dict from the three patch columns. This maintains the existing output format.

---

## What Changes, What Doesn't

### Files that change:
| File | Change |
|------|--------|
| `src/genechat/vcf_engine.py` | Open raw VCF + patch.db. `_record_to_dict` accepts optional patch_row. `query_rsid` and `query_clinvar` use SQLite indexes when patch available. Backward compat path preserved. |
| `src/genechat/cli.py` | Add `init`, `add`, `download`, `annotate`, `update`, `status`, `serve` subcommands. |
| `src/genechat/config.py` | Add `patch_db` path to genome config. VCFEngine takes explicit paths (multi-VCF ready). |
| `src/genechat/tools/genome_summary.py` | Read version info from `patch_metadata` table via engine. |
| `tests/conftest.py` | Test fixtures generate raw VCF + patch.db (in addition to annotated VCF for backward compat tests). |
| `tests/test_vcf_engine.py` | Tests run in both modes (annotated VCF and raw+patch) to verify parity. |
| `scripts/generate_test_vcf.py` | Also generate a raw VCF (without INFO annotations) + test patch.db. |

### Files that DON'T change (tool layer):
| File | Why |
|------|-----|
| `src/genechat/tools/query_gene.py` | Calls `engine.query_region()` — returns same dict format. Smart filter operates on dict fields, data source transparent. |
| `src/genechat/tools/query_pgx.py` | Calls `engine.query_region()`/`query_regions()` — transparent. |
| `src/genechat/tools/calculate_prs.py` | Calls `engine.query_region()` — transparent. |
| `src/genechat/tools/query_variant.py` | Calls `engine.query_rsid()`/`query_region()` — transparent. |
| `src/genechat/tools/query_variants.py` | Calls `engine.query_rsids()` — transparent. |
| `src/genechat/tools/query_clinvar.py` | Calls `engine.query_clinvar()` — transparent. |
| `src/genechat/tools/query_gwas.py` | Queries GWAS SQLite only, no VCF. |
| `src/genechat/tools/rebuild_database.py` | Operates on lookup_tables.db. |
| `src/genechat/lookup.py` | Reads lookup_tables.db. |
| `src/genechat/parsers/` | `parse_genotype` and `parse_clinvar_fields` still used at runtime. `parse_ann_field` used only during annotation. |

### Files removed (after backward compat period):
| File | Replaced by |
|------|-------------|
| `scripts/annotate.sh` | `genechat annotate` |
| `scripts/update_clinvar.sh` | `genechat annotate --clinvar` |
| `scripts/update_gnomad.sh` | `genechat annotate --gnomad` |
| `scripts/update_snpeff.sh` | `genechat annotate --snpeff` |
| `scripts/update_dbsnp.sh` | `genechat annotate --dbsnp` |
| `scripts/update_annotations.sh` | `genechat annotate --all` |
| `scripts/setup_references.sh` | `genechat annotate` (auto-downloads references) |

### New files:
| File | ~Lines | What |
|------|--------|------|
| `src/genechat/patch.py` | ~400 | PatchDB class: create schema (WAL mode), parse VCF streams, run bcftools/SnpEff subprocesses, populate/update tables, fingerprint check, integrity verification |
| `src/genechat/download.py` | ~150 | Download reference databases with progress. Shared cache management. |
| `src/genechat/update.py` | ~100 | Version checking: HTTP HEAD checks for staleness, print status table |
| `tests/test_patch.py` | ~200 | Tests for patch generation (mock subprocess, verify SQLite contents) |
| `tests/test_parity.py` | ~100 | End-to-end parity test: annotated VCF output == raw+patch output |

---

## Timing Summary

### First-time setup

| Step | Current pipeline | Patch pipeline | Why similar |
|------|-----------------|----------------|-------------|
| SnpEff | ~15-20 min | ~15-25 min | Same SnpEff work + Python parse overhead |
| ClinVar | ~2-5 min | ~2-5 min | Same bcftools work + Python parse overhead |
| gnomAD | ~10-15 min | ~5-10 min | Same bcftools, but no intermediate VCF compression |
| dbSNP | ~5-10 min | ~5-10 min | Same bcftools work |
| Index/finalize | ~1 min (tabix) | ~1-2 min (CREATE INDEX + integrity check) | Comparable |
| **Total** | **~30-45 min** | **~30-45 min** | **Same order of magnitude** |

**Honest assessment:** First-run setup time will be **comparable to the current pipeline**, not faster. The Python parsing layer adds overhead. The win is NOT in first-run speed — it's in the update story, runtime performance, and simpler UX.

### Incremental updates

| Update | Current | Patch | Improvement |
|--------|---------|-------|-------------|
| ClinVar | ~3-5 min (strip + re-annotate + reindex VCF) | ~2-5 min (bcftools | parse -> UPDATE, single transaction) | Modest, but atomic and concurrent-safe |
| gnomAD | ~10-15 min (strip + per-chrom re-annotate + concat + reindex) | ~5-10 min (per-chrom bcftools | parse -> UPDATE) | ~2x faster (no VCF concat/compress) |
| SnpEff | ~15-30 min (strip + per-chrom SnpEff + concat + reindex) | ~15-25 min (per-chrom SnpEff | parse -> UPDATE) | Modest |

### Runtime query performance

| Query | Current | Patch | Improvement |
|-------|---------|-------|-------------|
| `query_variant("rs4149056")` | ~2-5 sec (full VCF scan) | ~5-10 ms (SQLite index + pysam point fetch) | **~500x** |
| `query_variants(["rs1","rs2",...])` | ~2-5 sec (full VCF scan) | ~5-10 ms per rsID | **~500x** |
| `query_gene("BRCA1")` | ~20-50 ms | ~20-60 ms | Comparable |
| `query_clinvar("pathogenic")` genome-wide | ~2-5 sec (full VCF scan) | ~0.5-2 sec (SQLite column scan) | **~2-5x** |
| `query_clinvar("pathogenic")` with region | ~20-50 ms | ~1-10 ms | **~5-20x** |
| `genome_summary()` stats | ~2-5 sec | ~2-5 sec (still scans raw VCF for counts) | Same |
| `calculate_prs(trait)` | ~50-200 ms | ~50-200 ms | Same |

---

## Risk Assessment

### 1. VCF line parser correctness
The parser reads text output from bcftools/SnpEff. Both produce standard VCF. The parser only extracts specific INFO fields — it does NOT need to handle the full VCF spec.

- **Multi-value INFO fields:** ANN contains commas and pipes. The `_extract_info_field` function extracts the raw field value (everything between `ANN=` and the next `;`). The existing `parse_ann_field()` handles the internal ANN parsing during Step 1.
- **Substring collisions:** The `_extract_info_field` function requires the field name at string start or after `;`, preventing `AF` from matching `AF_grpmax`.

### 2. SnpEff per-chromosome streaming
SnpEff is run per-chromosome to avoid OOM (proven pattern). The Python parser reads stdout in real-time. If Python falls behind:
- **Risk:** Pipe buffer fills, SnpEff blocks, slowdown but no data loss.
- **Mitigation:** Python INSERT batching (every 10K rows) keeps the parser fast. SQLite INSERT throughput is ~50K-100K rows/sec with WAL mode.

### 3. Partial annotation failure
If the process crashes during Step 2 (ClinVar), patch.db has SnpEff annotations but no ClinVar.
- **Risk:** User runs `genechat serve` with incomplete patch.
- **Mitigation:** Each step sets `status='pending'` in `patch_metadata` before starting, `status='complete'` after. Because the entire step runs in a single transaction, a crash means the transaction rolls back — the columns stay in their pre-update state (either populated from a previous run, or NULL from initial creation). At startup, engine checks for any `status='pending'` and warns.

### 4. Disk space
- patch.db: ~500 MB - 1 GB
- WAL file during annotation: up to ~1 GB (temporary)
- Raw VCF: ~800 MB - 1.5 GB (compressed)
- Total during annotation: ~2.5 - 3.5 GB
- Total at rest: ~1.3 - 2.5 GB
- Current (annotated VCF): ~2 GB
- **Net: comparable disk usage.** The raw VCF must be kept regardless (user's source file).

### 5. Backward compatibility
Users with existing annotated VCFs:
- **Approach:** Support both modes. If config has `patch_db` pointing to a valid patch.db, use patch mode. Otherwise, use current behavior (read annotations from VCF INFO).
- **Detection:** Check if `patch_db` is in config, not VCF header sniffing.
- **Migration:** Users run `genechat init raw.vcf.gz` when ready. No rush. Existing annotated VCF setups continue to work indefinitely.

### 6. Two files to manage
Users now have raw.vcf.gz + patch.db instead of one annotated.vcf.gz.
- **Mitigation:** patch.db lives next to the raw VCF by convention (same directory). `genechat init` sets this up. patch.db is regenerable — if lost, just re-run `genechat annotate`. The raw VCF is the irreplaceable file.

---

## Implementation Phases

### Phase 1: Engine refactor + patch.py (core)
- Create `src/genechat/patch.py`:
  - `PatchDB` class: open/create SQLite with WAL mode, schema creation
  - `parse_vcf_stream()` + `_extract_info_field()`: the VCF line parser
  - `run_snpeff_to_patch()`: subprocess + parse (extracts ANN + ID column)
  - `run_bcftools_annotate_to_patch()`: subprocess + parse (parameterized for ClinVar/gnomAD/dbSNP)
  - `verify_integrity()`: count comparison + fingerprint storage
- Refactor `VCFEngine` to accept optional PatchDB
  - If PatchDB provided: join annotations from patch
  - If not: read annotations from VCF INFO (backward compat)
- Update `_record_to_dict`, `query_rsid`, `query_rsids`, `query_clinvar`
- Adapt `_matches_filter` for patch mode (check dict instead of pysam record)
- Update `annotation_versions()` to read from `patch_metadata` in patch mode
- Update test fixtures: `generate_test_vcf.py` produces raw VCF + test patch.db
- Update `tests/test_vcf_engine.py` and `tests/conftest.py`
- Create `tests/test_parity.py`: end-to-end parity verification
- **All 142+ existing tests must pass in both modes**

### Phase 2: CLI subcommands
- Add all 7 subcommands to `cli.py`: `init`, `add`, `download`, `annotate`, `update`, `status`, `serve`
- Create `src/genechat/download.py` for reference downloads with progress
- Create `src/genechat/update.py` for version checking (HTTP HEAD)
- `init` composes `add` + `download` + `annotate` + config write
- `update --apply` composes `download` + `annotate` for stale sources
- Update README and docs

### Phase 3: Clean up
- Remove shell scripts (annotate.sh, update_*.sh, setup_references.sh)
- Update CLAUDE.md
- Update README.md to reflect current state (new CLI subcommands, patch architecture, simplified setup flow)
- Update GIAB e2e test setup (generate GIAB patch.db)

---

## Data Source Versioning and Update Detection

### Version schemes by source

| Source | Version Scheme | Release Cadence | "Latest" URL | Programmatic check |
|--------|---------------|-----------------|--------------|-------------------|
| **ClinVar** | Date-based (`YYYYMMDD`) | Monthly (1st Thursday) | `clinvar.vcf.gz` (no date suffix) at FTP root is always current | HTTP HEAD `Last-Modified` on `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz` |
| **gnomAD** | Semantic (`v4.1`) | Irregular, ~1/year | None — version baked into URL path | `gsutil ls gs://gcp-public-data--gnomad/release/` or watch gnomAD blog |
| **SnpEff** | Tool: semantic (`5.4`), DB: Ensembl/RefSeq release (`GRCh38.p14`) | Irregular (months to years) | `snpEff_latest_core.zip` for tool binary | GitHub Releases API (`pcingola/SnpEff`) |
| **dbSNP** | Build number (`Build 157`) | Irregular, 1-3 year gaps | `https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/` always current | HTTP HEAD `Last-Modified` on `latest_release/` |
| **GWAS Catalog** | Date-based (`YYYY/MM/DD` dirs) | Weekly | `https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/` | HTTP HEAD `Last-Modified` on `releases/latest/` |

None use semantic versioning in the npm/semver sense. ClinVar and GWAS Catalog are date-stamped, gnomAD is major.minor, dbSNP is build numbers, SnpEff is a mix.

### How versions are tracked

`patch_metadata` stores the version and date for each annotation source:

```sql
-- After annotation:
SELECT source, version, updated_at, status FROM patch_metadata;

source           version        updated_at    status
snpeff           GRCh38.p14     2026-03-07    complete
clinvar          2026-03-06     2026-03-07    complete
gnomad           v4.1           2026-03-07    complete
dbsnp            Build 157      2026-03-07    complete
vcf_fingerprint  8234567:...    2026-03-07    complete
```

Version values are captured during annotation:
- **ClinVar:** Parse the `##fileDate=YYYYMMDD` header line from the ClinVar VCF
- **gnomAD:** Parse from the gnomAD filename pattern (`gnomad.exomes.v4.1.sites...`)
- **SnpEff:** Capture from `snpEff -version` output + the DB name used
- **dbSNP:** Parse from the `##dbSNP_BUILD_ID=` header line in the dbSNP VCF
- **GWAS Catalog:** Store the `Last-Modified` date from the download

### `genechat update` — check for and apply reference updates

See the CLI Commands section above for full details. Implementation:
1. Read `patch_metadata` for installed versions
2. For ClinVar/dbSNP/GWAS: HTTP HEAD on "latest" URL, compare `Last-Modified` against `updated_at`
3. For gnomAD: compare installed version string against a hardcoded latest (updated with each GeneChat release), or optionally `gsutil ls` if available
4. For SnpEff: query GitHub Releases API for latest release tag
5. Default: print status table. With `--apply`: download stale references + re-annotate affected layers.

### Practical update cadence

| Source | How often to update | Why |
|--------|-------------------|-----|
| **ClinVar** | Every 3-6 months | Monthly releases, but variant reclassifications accumulate slowly. Most impactful for pathogenic variant queries. |
| **gnomAD** | When a new major version drops (~yearly) | Frequency data changes meaningfully only with new releases. |
| **SnpEff** | Rarely | Functional annotation logic is stable. Update if a specific gene model bug is fixed. |
| **dbSNP** | Rarely (every 1-3 years) | rsID assignments are stable. New builds add novel variants, rarely change existing ones. |
| **GWAS Catalog** | Every 1-3 months | Weekly releases, but trait associations accumulate gradually. GWAS data lives in lookup_tables.db, not patch.db. |

### Full CLI reference

| Command | Type | Analogy | What it does |
|---------|------|---------|-------------|
| `genechat init <vcf>` | Porcelain | `terraform init` | Full first-time setup: add + download + annotate + configure |
| `genechat add <vcf> [--label]` | Plumbing | `dvc add`, `helm repo add` | Register a VCF (validate, index, write config) |
| `genechat install [--gwas]` | Plumbing | `cargo fetch`, `vep INSTALL.pl` | Install genome-independent databases (GWAS) |
| `genechat annotate [--source]` | Plumbing | `snpEff ann`, `cargo build` | Build/update patch.db for a registered VCF |
| `genechat update [--apply]` | Plumbing | `brew update` + `brew upgrade` | Check for newer refs; `--apply` downloads + re-annotates |
| `genechat status` | Plumbing | `dvc status`, `git status` | Show genome info, annotation state, reference versions |
| `genechat serve` / bare `genechat` | — | `docker compose up` | Start MCP server |

---

## Multi-VCF Architecture (future expansion)

The architecture is designed so that multi-VCF support is a natural extension, not a rewrite. The anticipated use case: couples wanting to explore genetic compatibility (carrier screening, trait combinations).

### What's multi-VCF-ready today

| Component | Single-genome (v1) | Multi-genome (future) | Change needed |
|-----------|-------------------|----------------------|---------------|
| **VCFEngine** | One instance, takes `(vcf_path, patch_db_path)` | N instances, one per genome | None — already parameterized |
| **patch.db** | One file, lives next to VCF | One per VCF, each next to its VCF | None — already per-VCF |
| **Reference databases** | Shared in `~/.local/share/genechat/references/` | Same — references are genome-build-specific, not sample-specific | None |
| **lookup_tables.db** | Shared (genes, PGx, PRS) | Same — reference data | None |
| **Config** | `[genome]` section with one VCF path | `[[genomes]]` array with labeled entries | Schema extension |
| **Server** | One engine registered with tools | Dict of engines, keyed by label | Moderate refactor |
| **MCP tools** | No `genome` parameter | Optional `genome: str` parameter on each tool | Additive change |
| **`genechat add`** | `add <vcf>` (label auto-derived) | `add <vcf> --label partner` | Already designed for this |

### Config schema evolution

```toml
# v1 (single genome — current, backward compatible)
[genome]
vcf_path = "/data/me.vcf.gz"
genome_build = "GRCh38"

# v2 (multiple genomes — future)
[[genomes]]
label = "me"
vcf_path = "/data/me.vcf.gz"
genome_build = "GRCh38"

[[genomes]]
label = "partner"
vcf_path = "/data/partner.vcf.gz"
genome_build = "GRCh38"
```

The config loader detects which format is present. `[genome]` (singular) is treated as a single-element list with `label` derived from the VCF filename. `[[genomes]]` (plural) is the multi-genome format.

### Tool parameter extension

```python
# v1: tools implicitly use the single engine
def query_variant(rsid: str) -> str: ...

# v2: tools accept optional genome selector
def query_variant(rsid: str, genome: str = "default") -> str: ...
```

When only one genome is configured, the `genome` parameter is ignored. When multiple genomes exist, it selects which engine to query. The LLM can call tools on each genome separately and synthesize results (e.g., "Both of you are carriers for the same CFTR variant").

### What NOT to build now

- No cross-genome comparison tools (the LLM can compare by making two separate tool calls)
- No `genome` parameter on tools (added when multi-VCF ships)
- No `[[genomes]]` config parsing (added when multi-VCF ships)
- No multi-sample VCF support (each person has their own VCF file)

What we do now to keep the door open:
- VCFEngine takes `(vcf_path, patch_db_path)` not a config singleton — easy to instantiate multiple
- patch.db is per-VCF, named `<stem>.patch.db` — no conflicts between genomes
- `--label` flag exists on `add`/`init`/`annotate` — plumbing is ready
- Reference databases in shared cache — no duplication when adding a second genome

---

## Open Questions

1. **Where does patch.db live?** Recommendation: same directory as the raw VCF, named `<vcf_stem>.patch.db` (e.g., `my_genome.vcf.gz` -> `my_genome.patch.db`). This naturally supports multi-VCF (each VCF has its own patch alongside it). `genechat init` auto-determines this.

2. **Should `init` auto-run the full 30-min annotation?** Recommendation: yes, but with clear progress output. If the user ctrl-C's, re-running picks up where it left off (each step is idempotent — pending steps detected and re-run). Alternative: `init` only does validation + config, tells user to run `genechat annotate` separately.

3. **Backward compatibility period?** Recommendation: support both modes indefinitely. The backward compat path is ~20 lines of `if/else` in the engine — negligible maintenance burden. No reason to force migration.

4. **Should this be a separate PR from PRs #17/#18?** Yes. Merge #17 and #18 first (they're independent improvements). Then implement the patch architecture as a new PR series.

5. **Should we store the full raw ANN string?** The current code only parses the first transcript. Storing the full ANN string (~200-500 bytes per variant) would add ~1-2.5 GB to patch.db but preserve the option for multi-transcript analysis later. Recommendation: don't store it for v1. Re-running `genechat annotate --snpeff` is cheap if we later want more transcript data.
