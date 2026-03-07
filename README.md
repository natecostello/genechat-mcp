# GeneChat MCP Server

A local-first MCP server that lets you have detailed conversations with AI about your genome. Query your whole-genome sequencing data through Claude (or any MCP-compatible LLM) for pharmacogenomics, disease risk, nutrition, exercise genetics, carrier screening, and more — with your data never leaving your machine.

> **Privacy Notice:** GeneChat reads your VCF locally, but tool responses — containing your genotypes, rsIDs, and clinical interpretations — are sent to your LLM provider (e.g. Anthropic, OpenAI) as part of the conversation. Your raw VCF file is never uploaded, but the LLM does see the specific variants and findings returned by each tool call. Additionally, your MCP client (Claude Desktop, Claude Code, etc.) may log conversation history locally, which will include genomic findings. See [Security Recommendations](#security-recommendations) below for how to protect your data.

## What It Does

You get your genome sequenced ($250–$900 from providers like Nucleus Genomics or Nebula Genomics). You download the raw VCF file. GeneChat annotates it once with open-source tools, then serves it locally via MCP so you can ask questions like:

- "I was just prescribed simvastatin — any genetic concerns?"
- "What does my genome say about cardiovascular risk?"
- "I do heavy lifting and kiteboarding — any genetic injury risk factors?"
- "How should I think about my diet based on my genetics?"
- "I have surgery next month. What should I tell my anesthesiologist?"
- "Am I a carrier for anything concerning?" *(uses ClinVar annotations + LLM knowledge)*

The LLM calls GeneChat's tools behind the scenes, gets your specific genotypes and annotations, and interprets the results in context.

## How It Works

```
You ask a question in Claude
    → Claude picks the right GeneChat tool
    → GeneChat queries your local VCF with pysam
    → Returns your genotype + clinical annotations
    → Claude interprets the results for you
```

Your genome data stays on your machine. GeneChat only reads from local files. No network calls at runtime.

## Tools

| Tool | Purpose |
|------|---------|
| `query_variant` | Look up a single variant by rsID or position |
| `query_variants` | Batch lookup of multiple rsIDs in a single VCF scan |
| `query_gene` | List notable variants in a gene with smart filter |
| `query_genes` | Batch query variants across multiple genes at once |
| `query_pgx` | Pharmacogenomics lookup by drug or gene (CPIC data) |
| `query_clinvar` | Find clinically significant variants |
| `query_gwas` | Search the GWAS Catalog by trait, gene, or variant |
| `calculate_prs` | Polygenic risk scores (PGS Catalog data) |
| `genome_summary` | High-level overview of your genome |
| `rebuild_database` | Rebuild SQLite from existing seed TSVs |

## Prerequisites

- Python 3.11+
- A consumer WGS VCF file (from Nucleus Genomics, Nebula, Sequencing.com, etc.)
- ~15 GB disk for reference databases, ~2 GB for your annotated VCF

**For full annotation** (recommended — adds SnpEff functional annotation):

```bash
# macOS (Homebrew)
brew install bcftools brewsci/bio/snpeff

# Linux (conda)
conda install -c bioconda bcftools snpeff
```

This installs bcftools and SnpEff. Java is required by SnpEff — Homebrew handles this automatically. On Linux, ensure `java` is available.

VCF reading at runtime is handled by [pysam](https://pysam.readthedocs.io/), which is installed automatically via `uv sync`. No external tools are needed at runtime.

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/natecostello/genechat-mcp.git
cd genechat-mcp
uv sync
```

### 2. Install annotation tools

```bash
# macOS
brew install bcftools brewsci/bio/snpeff

# Linux
conda install -c bioconda bcftools snpsift
```

### 3. Download reference databases and annotate your VCF

```bash
# Download ClinVar + SnpEff database + gnomAD exome frequencies (~8 GB, optional)
bash scripts/setup_references.sh ./references

# Annotate your VCF (~20-30 minutes)
# With per-chromosome gnomAD v4 exomes (recommended):
CLINVAR_VCF=./references/clinvar.vcf.gz \
GNOMAD_DIR=./references/gnomad_exomes_v4 \
bash scripts/annotate.sh /path/to/your/raw.vcf.gz ./data

# Or without gnomAD (ClinVar + SnpEff only):
CLINVAR_VCF=./references/clinvar.vcf.gz \
bash scripts/annotate.sh /path/to/your/raw.vcf.gz ./data
```

This runs SnpEff functional annotation + ClinVar + optional gnomAD and produces `data/annotated.vcf.gz`. gnomAD provides population allele frequencies that enable the `smart_filter` in `query_gene` to suppress common benign variants. Without gnomAD, smart_filter falls back to ClinVar-only mode.

### 4. Build lookup tables

```bash
uv run python scripts/build_lookup_db.py
```

### 4b. (Optional) Load GWAS Catalog

Download the GWAS Catalog associations file (~58 MB compressed) and build the GWAS search database:

```bash
mkdir -p data/gwas_catalog
curl -o data/gwas_catalog/gwas-catalog-associations.zip \
  https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/gwas-catalog-associations_ontology-annotated-full.zip
uv run python scripts/build_gwas_db.py
```

This enables the `query_gwas` tool, which searches 1M+ genome-wide association study findings by trait, gene, or variant. Without this step, the tool will prompt users to run the setup.

### 5. Configure

```bash
cp config.toml.example config.toml
# Edit config.toml: set vcf_path to your annotated.vcf.gz
```

Alternatively, skip the config file and just set the `GENECHAT_VCF` environment variable pointing to your annotated VCF. This is enough for basic usage -- all other settings have sensible defaults:

```bash
export GENECHAT_VCF=/path/to/your/annotated.vcf.gz
```

### 6. Connect to Claude

Add to your Claude Desktop or Claude Code MCP config.

**With config file:**

```json
{
  "mcpServers": {
    "genechat": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/genechat-mcp", "genechat"],
      "env": {
        "GENECHAT_CONFIG": "/path/to/genechat-mcp/config.toml"
      }
    }
  }
}
```

**Or with `GENECHAT_VCF` only** (no config file needed):

```json
{
  "mcpServers": {
    "genechat": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/genechat-mcp", "genechat"],
      "env": {
        "GENECHAT_VCF": "/path/to/your/annotated.vcf.gz"
      }
    }
  }
}
```

### 7. Start asking questions

Open Claude and ask about your genetics. GeneChat's tools will appear automatically.

## Architecture & Components

GeneChat has three phases — each with different tools and data sources. No network calls happen at runtime.

```
┌─── YOUR MACHINE (Local Only) ─────────────────────────────────┐
│                                                                │
│  Raw VCF from Sequencing Provider                              │
│      ↓                                                         │
│  ANNOTATION (one-time)                                         │
│      SnpEff → functional impact    (ANN field)                 │
│      ClinVar → clinical significance (CLNSIG, CLNDN)          │
│      dbSNP → rsID identifiers      (ID column)                │
│      gnomAD → population frequency  (AF, AF_popmax/AF_grpmax)  │
│      ↓                                                         │
│  annotated.vcf.gz                                              │
│      ↓                                                         │
│  RUNTIME (no network)                                          │
│      pysam reads VCF  ←→  SQLite lookup tables                 │
│      ↓                                                         │
│  MCP Server ←──── Claude asks questions via MCP protocol       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Annotation Pipeline (one-time setup)

These tools annotate your raw VCF once. They are **not** needed at runtime.

| Tool | What it adds to your VCF | Install |
|------|--------------------------|---------|
| [SnpEff](https://pcingola.github.io/SnpEff/) | **Functional annotation** — gene name, effect type (missense, synonymous, etc.), impact level (HIGH/MODERATE/LOW), protein change (HGVS notation) | `brew install brewsci/bio/snpeff` |
| [bcftools](https://samtools.github.io/bcftools/) | **Database annotation + VCF manipulation** — transfers ClinVar/gnomAD/dbSNP fields onto your VCF, chromosome renaming, compression (bgzip), indexing (tabix) | `brew install bcftools` |

### Reference Databases (downloaded once)

| Database | What it provides | Size | How GeneChat uses it |
|----------|-----------------|------|---------------------|
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Clinical significance (Pathogenic, Benign, drug_response, etc.), disease/condition name, review status | ~100 MB | `query_clinvar` filters by significance; `query_variant` shows clinical interpretation |
| [dbSNP](https://www.ncbi.nlm.nih.gov/snp/) | rsID identifiers (rs4149056, etc.) for each genomic position | ~20 GB | Enables `query_variant` by rsID — without dbSNP, the VCF ID column is `.` and rsID lookups fail |
| [gnomAD](https://gnomad.broadinstitute.org/) | Population allele frequencies (global + per-population) | ~8 GB (exomes) or ~30 GB (genomes) | `query_variant` shows how common a variant is; `query_gene` smart_filter uses AF to suppress common benign variants |
| [SnpEff DB](https://pcingola.github.io/SnpEff/) | Gene/transcript models for functional impact prediction | ~1.6 GB | Used by SnpEff during annotation to determine which gene/transcript a variant affects |
| [GWAS Catalog](https://www.ebi.ac.uk/gwas/) | 1M+ genome-wide association study findings | ~58 MB | `query_gwas` searches by trait, gene, or variant (optional) |

### Seed Data Pipeline (build-time)

These scripts build the SQLite lookup tables that map gene names, drug names, and trait categories to genomic coordinates. Run once, requires internet. The generated database is committed to git.

| Source | What it provides | Script |
|--------|-----------------|--------|
| [HGNC](https://www.genenames.org/) | All ~19,000 human protein-coding gene symbols | `fetch_gene_coords.py` |
| [Ensembl REST API](https://rest.ensembl.org/) | GRCh38 coordinates for genes | `fetch_gene_coords.py` |
| [CPIC](https://cpicpgx.org/) via [ClinPGx API](https://api.cpicpgx.org/v1/) | Pharmacogenomics drug-gene guidelines, star-allele definitions, variant positions | `fetch_cpic_data.py` |
| [PGS Catalog](https://www.pgscatalog.org/) | Polygenic risk score weights (harmonized GRCh38) | `fetch_prs_data.py` |

**Pipeline flow:** `uv run python scripts/build_seed_data.py` runs the full pipeline:
1. Downloads all approved gene symbols from HGNC + Ensembl coordinates
2. Fetches CPIC Level A/B drug-gene pairs, star alleles, and variant positions
3. Downloads PRS scoring files from PGS Catalog FTP
4. Builds SQLite database (`lookup_tables.db`) with 4 tables: `genes`, `pgx_drugs`, `pgx_variants`, `prs_weights`

### Runtime Dependencies

At runtime, GeneChat uses **only** local files — no external tools, no network calls.

| Library | What it does |
|---------|-------------|
| [pysam](https://pysam.readthedocs.io/) | Reads your annotated VCF via tabix index — replaces bcftools at runtime |
| [mcp](https://github.com/anthropics/python-sdk) | Implements the MCP server protocol (stdio transport) |
| SQLite (stdlib) | Queries lookup tables for gene coordinates, drug info, PRS weights |
| [pydantic](https://docs.pydantic.dev/) | Validates tool inputs and config |

### What Each Tool Question Uses

| Question type | VCF fields read | Lookup tables queried |
|--------------|----------------|----------------------|
| "Tell me about rs4149056" | genotype, ANN, CLNSIG, CLNDN, AF | — |
| "Check rs4149056 and rs1801133" | genotype (batch scan) | — |
| "Variants in BRCA1?" | genotype, ANN (impact filter) | `genes`, `pgx_variants` |
| "Check BRCA1, BRCA2, and TP53" | genotype (batch regions) | `genes` |
| "Prescribed simvastatin — concerns?" | genotype at PGx positions | `pgx_drugs`, `pgx_variants`, `genes` |
| "ClinVar pathogenic variants?" | CLNSIG, CLNDN, CLNREVSTAT | `genes` |
| "GWAS findings for FTO?" | — | `gwas_associations` |
| "Coronary artery disease risk?" | genotype at PRS positions | `prs_weights` |
| Genome overview | variant counts, CLNSIG summary | `pgx_variants` |

## TODO: Incremental Annotation Updates

The current annotation pipeline (`annotate.sh`) is a linear chain that must be re-run from scratch. This plan outlines how to support incremental updates of each annotation layer independently, so users can stay current without re-running the full pipeline.

### Background

| Layer | What changes | Release cadence | Re-annotation cost today |
|-------|-------------|-----------------|--------------------------|
| ClinVar | Variant reclassifications (VUS→Pathogenic, etc.) | Monthly | Full pipeline (~30 min) |
| gnomAD | Population allele frequencies | Major releases every 1–2 years | Full pipeline (~30 min) |
| SnpEff | Gene models, transcript definitions | Tied to Ensembl (~2/year) | Full pipeline (~30 min) |
| dbSNP | rsID assignments for new variants | Quarterly | `setup_giab.sh` test data only (~30 min) |
| GWAS Catalog | New association study results | Weekly | `build_gwas_db.py` (~2 min, already incremental) |
| Seed data | PGx (CPIC) + PRS (PGS Catalog) | When APIs update | `build_seed_data.py` (~5 min, already incremental) |

### Design: Layer-Independent Re-annotation

The key insight is that `bcftools annotate` can **strip** specific INFO fields (`-x`) and **re-stamp** them from a fresh reference (`-a`, `-c`). Each annotation layer writes to distinct INFO fields with no cross-dependencies:

| Layer | INFO fields owned | Depends on other layers? |
|-------|-------------------|--------------------------|
| SnpEff | `ANN` | No (reads REF/ALT only) |
| ClinVar | `CLNSIG`, `CLNDN`, `CLNREVSTAT`, `CLNVC` | No (matches on CHROM/POS/REF/ALT) |
| gnomAD | `AF`, `AF_grpmax` (or `AF_popmax`) | No (matches on CHROM/POS/REF/ALT) |
| dbSNP | `ID` column | No (matches on CHROM/POS/REF/ALT) |

Because the fields are independent, any single layer can be updated in isolation.

### Planned Scripts

#### `scripts/update_clinvar.sh` (highest priority)

ClinVar reclassifications are the most clinically impactful updates. Recommended: every 3–6 months.

```
1. Download latest ClinVar VCF (setup_references.sh already does this)
2. Strip old ClinVar fields:
   bcftools annotate -x INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
       annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
3. Re-annotate with fresh ClinVar (with contig rename if needed) to a temp file:
   bcftools annotate -a clinvar_new.vcf.gz \
       -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/CLNVC \
       tmp_stripped.vcf.gz -Oz -o tmp_annotated.vcf.gz
4. Atomically replace the existing annotated VCF:
   mv tmp_annotated.vcf.gz annotated.vcf.gz
5. Re-index: tabix -p vcf annotated.vcf.gz
6. Clean up temp files
```

Estimated time: 2–5 minutes. Preserves all SnpEff, gnomAD, and dbSNP annotations.

#### `scripts/update_gnomad.sh`

Only needed on major gnomAD releases (v4→v5). Recommended: when a new major version ships.

```
1. Strip old frequency fields:
   bcftools annotate -x INFO/AF,INFO/AF_grpmax,INFO/AF_popmax \
       annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
2. Re-annotate per-chromosome (same logic as annotate.sh step 3)
3. Re-index
```

Estimated time: 10–20 minutes (per-chromosome gnomAD annotation dominates).

#### `scripts/update_snpeff.sh`

Only needed when Ensembl releases new gene models. Recommended: annually.

```
1. Download new SnpEff database: snpEff download GRCh38.pXX
2. Strip old ANN field:
   bcftools annotate -x INFO/ANN annotated.vcf.gz -Oz -o tmp_stripped.vcf.gz
3. Re-run SnpEff on stripped VCF (writes new ANN field)
4. Re-index
```

Estimated time: 15–30 minutes (SnpEff is the slowest step). Consider per-chromosome parallelism (already proven in the full pipeline).

#### `scripts/update_dbsnp.sh`

Only needed if the original annotation was done without dbSNP, or on a new dbSNP release.

```
1. Download latest dbSNP VCF + rename contigs to chr prefix
2. bcftools annotate -a dbsnp_new.vcf.gz -c ID \
       annotated.vcf.gz -Oz -o tmp_updated.vcf.gz
3. mv + re-index
```

Note: unlike the others, dbSNP primarily uses the `ID` column (not INFO), so `-x` stripping isn't needed here. The command above will fill in missing (`.`) IDs with rsIDs, but it will not overwrite existing IDs unless you add `--force` or strip the ID column first (so merged/retired rsIDs are not updated by default).

Estimated time: 5–10 minutes.

#### `scripts/update_annotations.sh` (convenience wrapper)

```
Usage: ./scripts/update_annotations.sh [--clinvar] [--gnomad] [--snpeff] [--dbsnp] [--all]

Runs only the requested update layers in the correct order.
Default (no flags): --clinvar only (the most common update).
```

### Implementation Considerations

- **Atomic writes**: All scripts should write to a temp file, then `mv` to the final path — never overwrite in place. A failed update should leave the previous annotation intact.
- **Backup**: Before any update, copy the current `annotated.vcf.gz` to `annotated.vcf.gz.bak` (or timestamped). One bad update shouldn't be catastrophic.
- **Validation**: After re-annotation, spot-check a known variant (e.g., rs4149056 should still have SLCO1B1 in ANN and drug_response in CLNSIG). Could add a `--verify` flag that checks a few sentinel variants.
- **Version tracking**: Write a `##GeneChat_annotations` header line into the VCF recording which database versions were used and when. Example:
  ```
  ##GeneChat_ClinVar=2026-03-01
  ##GeneChat_gnomAD=v4.1
  ##GeneChat_SnpEff=GRCh38.p14
  ##GeneChat_dbSNP=b156
  ```
  The `genome_summary` tool could read these headers and report annotation freshness.
- **GWAS and seed data are already incremental**: `build_gwas_db.py` and `build_seed_data.py` rebuild their SQLite tables from scratch in minutes. No changes needed.

### Recommended Update Cadence

| What | How often | Script | Time |
|------|-----------|--------|------|
| ClinVar | Every 3–6 months | `update_clinvar.sh` | ~3 min |
| Seed data | When CPIC/PGS sources update | `build_seed_data.py` | ~5 min |
| GWAS Catalog | Every 6–12 months | `build_gwas_db.py` | ~2 min |
| gnomAD | On major releases only | `update_gnomad.sh` | ~15 min |
| SnpEff | Annually | `update_snpeff.sh` | ~20 min |
| dbSNP | Annually | `update_dbsnp.sh` | ~7 min |
| Full re-annotation | Only if starting from a new raw VCF | `annotate.sh` | ~30 min |

## TODO: `genechat init` Setup Command

Replace manual config steps (copy config.toml.example, edit VCF path, build lookup DB, copy MCP config JSON) with a single command:

```bash
genechat init /path/to/annotated.vcf.gz
```

This would: validate the VCF + index exist, write `config.toml` with `chmod 600`, build `lookup_tables.db` if missing, and print the MCP config JSON snippet to paste into Claude Desktop/Code.

## Security Recommendations

Genomic data is uniquely sensitive — it is immutable, identifies you and your relatives, and can reveal health predispositions. Take these precautions seriously.

### What stays local vs. what gets transmitted

| Data | Where it lives | Transmitted? |
|------|---------------|-------------|
| Your VCF file | Your machine only | Never |
| Tool responses (genotypes, rsIDs, clinical findings) | Sent to LLM provider per tool call | Yes |
| Conversation history | MCP client logs (local) | Depends on client settings |

GeneChat makes **zero network calls** at runtime. However, every tool response is returned to the LLM, which runs on the provider's servers. This is inherent to how MCP works — the LLM needs your actual genotype data to interpret it.

### Store your VCF on an encrypted volume

Your annotated VCF and `config.toml` (which contains the path to your VCF) should live on an encrypted volume:

**macOS (recommended — APFS encrypted disk image):**

```bash
# Create a 5 GB encrypted sparse image (grows as needed)
hdiutil create -size 5g -fs APFS -encryption AES-256 \
    -volname GenomeData -type SPARSE ~/GenomeData.sparseimage

# Mount it (prompts for password)
hdiutil attach ~/GenomeData.sparseimage

# Your VCF goes in /Volumes/GenomeData/
cp /path/to/annotated.vcf.gz /Volumes/GenomeData/
cp /path/to/annotated.vcf.gz.tbi /Volumes/GenomeData/

# Point config.toml at the mounted volume
# vcf_path = "/Volumes/GenomeData/annotated.vcf.gz"

# Unmount when not in use
hdiutil detach /Volumes/GenomeData
```

**Linux (LUKS encrypted volume):**

```bash
# Create and format an encrypted volume
dd if=/dev/zero of=~/genome_vault.img bs=1M count=5120
sudo cryptsetup luksFormat ~/genome_vault.img
sudo cryptsetup open ~/genome_vault.img genome_vault
sudo mkfs.ext4 /dev/mapper/genome_vault
sudo mkdir -p /mnt/genome_vault
sudo mount /dev/mapper/genome_vault /mnt/genome_vault

# Copy VCF and unmount when done
sudo umount /mnt/genome_vault
sudo cryptsetup close genome_vault
```

**External encrypted drive:** For additional isolation, store your VCF on an external encrypted USB drive. Use the same encrypted volume approach above, but on the external drive. Update `vcf_path` in `config.toml` to point to the mount path.

### File permissions

Restrict access to your VCF and config file:

```bash
chmod 600 /path/to/annotated.vcf.gz /path/to/annotated.vcf.gz.tbi /path/to/annotated.vcf.gz.csi
chmod 600 /path/to/config.toml
```

### MCP client logs

MCP clients like Claude Desktop and Claude Code store conversation history locally. These logs will contain your genomic findings (genotypes, clinical interpretations, risk assessments). Be aware of:

- Where your client stores conversation logs
- Whether cloud sync (iCloud, Dropbox) is enabled on those directories
- Who has access to your machine

### Privacy summary

- Your VCF file never leaves your machine
- No network calls during normal operation
- No telemetry, no analytics, no data collection
- Tool responses are sent to your LLM provider as part of the conversation

## Development / Testing

Install dev dependencies and run the test suite:

```bash
uv sync --extra dev
uv run pytest
```

The test VCF (`tests/data/test_sample.vcf.gz`) is auto-generated by a pytest fixture on first run -- no manual setup needed.

Lint and format checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

### End-to-End Testing with GIAB NA12878

GeneChat includes an optional e2e test suite that runs every tool against the [GIAB NA12878 (HG001)](https://www.nist.gov/programs-projects/genome-bottle) benchmark genome (~3.7M variants). These tests validate real-world behavior and verify known pharmacogenomic genotypes.

There are two setup paths:

| Feature | Python-only (`setup_giab.py`) | Full (`setup_giab.sh`) |
|---------|-------------------------------|------------------------|
| rsID lookup | Yes | Yes |
| ClinVar significance | Yes | Yes |
| SnpEff functional annotation | No* | Yes |
| gnomAD frequencies | No | Optional |
| Prerequisites | Python only | Java + bcftools + SnpEff |
| Setup time | ~20-30 min | ~30 min |

\*Claude already knows functional consequences for well-characterized variants. Missing SnpEff annotation has minimal practical impact on conversation quality.

**Option A: Python-only setup** (no external tools needed):

```bash
uv run python scripts/setup_giab.py ./giab
```

Add `--skip-rsid` to skip the ~15 GB dbSNP download (ClinVar still works, but rsID-based lookups won't).

**Option B: Full setup** (recommended — adds SnpEff functional annotation):

Requires bcftools and SnpEff. Install via Homebrew or conda (see [Prerequisites](#prerequisites)).

```bash
bash scripts/setup_giab.sh ./giab
```

The script auto-detects the correct SnpEff database version. To override, set `SNPEFF_DB`:

```bash
SNPEFF_DB=GRCh38.86 bash scripts/setup_giab.sh ./giab
```

**Run e2e tests:**

```bash
export GENECHAT_GIAB_VCF=./giab/HG001_annotated.vcf.gz
uv run pytest tests/e2e/ -v
```

**Run fast e2e tests only** (skip full-VCF scans):

```bash
uv run pytest tests/e2e/ -v -m "not slow"
```

E2e tests are **automatically skipped** when `GENECHAT_GIAB_VCF` is not set, so they never affect CI or the regular test suite.

## Troubleshooting

**Missing VCF index (.tbi)**
If you see an error about a missing index, regenerate it:
```bash
tabix -p vcf /path/to/your/annotated.vcf.gz
```

**Wrong genome build**
GeneChat expects a GRCh38 VCF with `chr` prefixed chromosomes (e.g. `chr1`, not `1`). If your VCF uses GRCh37/hg19, you need to lift it over to GRCh38 first.

**Missing lookup_tables.db**
If tools return empty results or errors about the lookup database, rebuild it:
```bash
uv run python scripts/build_lookup_db.py
```

**pysam installation issues on macOS**
If pysam fails to install, you may need Xcode command-line tools:
```bash
xcode-select --install
```

## Important Disclaimer

GeneChat is an informational tool, not a medical device. It is not a substitute for professional genetic counseling or medical advice. Always discuss genetic findings with a qualified healthcare provider before making health decisions.

## License

MIT
