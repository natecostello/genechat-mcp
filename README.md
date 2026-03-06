# GeneChat MCP Server

A local-first MCP server that lets you have detailed conversations with AI about your genome. Query your whole-genome sequencing data through Claude (or any MCP-compatible LLM) for pharmacogenomics, disease risk, nutrition, exercise genetics, carrier screening, and more — with your data never leaving your machine.

## What It Does

You get your genome sequenced ($250–$900 from providers like Nucleus Genomics or Nebula Genomics). You download the raw VCF file. GeneChat annotates it once with open-source tools, then serves it locally via MCP so you can ask questions like:

- "I was just prescribed simvastatin — any genetic concerns?"
- "What does my genome say about cardiovascular risk?"
- "I do heavy lifting and kiteboarding — any genetic injury risk factors?"
- "How should I think about my diet based on my genetics?"
- "I have surgery next month. What should I tell my anesthesiologist?"
- "Am I a carrier for anything concerning?"

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
| `query_gene` | List notable variants you carry in a gene |
| `query_pgx` | Pharmacogenomics lookup by drug or gene |
| `query_clinvar` | Find clinically significant variants |
| `query_trait` | Nutrigenomics, exercise, metabolism variants |
| `query_carrier` | Carrier screening panel |
| `calculate_prs` | Polygenic risk scores |
| `genome_summary` | High-level overview of your genome |

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
# Download ClinVar + SnpEff database
bash scripts/setup_references.sh ./references

# Annotate your VCF (~20-30 minutes)
CLINVAR_VCF=./references/clinvar_GRCh38.vcf.gz \
GNOMAD_VCF=./references/gnomad.exomes.v4.sites.vcf.bgz \
bash scripts/annotate.sh /path/to/your/raw.vcf.gz ./data
```

This runs SnpEff functional annotation + ClinVar + gnomAD and produces `data/annotated.vcf.gz`. gnomAD must be downloaded separately due to size (see script output).

### 4. Build lookup tables

```bash
python scripts/build_lookup_db.py
```

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
│      gnomAD → population frequency  (AF, AF_popmax)            │
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
| [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) | Clinical significance (Pathogenic, Benign, drug_response, etc.), disease/condition name, review status | ~100 MB | `query_clinvar` filters by significance; `query_variant` shows clinical interpretation; `query_carrier` finds pathogenic variants |
| [dbSNP](https://www.ncbi.nlm.nih.gov/snp/) | rsID identifiers (rs4149056, etc.) for each genomic position | ~20 GB | Enables `query_variant` by rsID — without dbSNP, the VCF ID column is `.` and rsID lookups fail |
| [gnomAD](https://gnomad.broadinstitute.org/) | Population allele frequencies (global + per-population) | ~30 GB | `query_variant` shows how common a variant is; helps distinguish rare vs common findings |
| [SnpEff DB](https://pcingola.github.io/SnpEff/) | Gene/transcript models for functional impact prediction | ~1.6 GB | Used by SnpEff during annotation to determine which gene/transcript a variant affects |

### Seed Data Pipeline (build-time)

These scripts build the SQLite lookup tables that map gene names, drug names, and trait categories to genomic coordinates. Run once, requires internet. The generated database is committed to git.

| Source | What it provides | Script |
|--------|-----------------|--------|
| [HGNC](https://www.genenames.org/) | All ~19,000 human protein-coding gene symbols | `fetch_gene_coords.py` |
| [Ensembl REST API](https://rest.ensembl.org/) | GRCh38 coordinates for genes and variants | `fetch_gene_coords.py`, `fetch_variant_coords.py`, `fetch_prs_coords.py` |
| [CPIC](https://cpicpgx.org/) | Pharmacogenomics drug-gene guidelines, star-allele definitions | Curated in `data/seed/pgx_drugs.tsv`, `pgx_variants.tsv` |
| [PharmVar](https://www.pharmvar.org/) | Pharmacogene star-allele variant coordinates | Curated in `data/seed/pgx_variants.tsv` |
| [PGS Catalog](https://www.pgscatalog.org/) | Polygenic risk score weights | Curated in `data/seed/curated/prs_scores.tsv` |
| Published GWAS | Trait-associated variants (caffeine metabolism, lactose tolerance, etc.) | Curated in `data/seed/curated/trait_metadata.tsv` |
| [ACMG](https://www.acmg.net/) / [GeneReviews](https://www.ncbi.nlm.nih.gov/books/NBK1116/) | Carrier screening gene panels, inheritance patterns | Curated in `data/seed/curated/carrier_metadata.tsv` |

**Pipeline flow:** `uv run python scripts/build_seed_data.py` runs the full pipeline:
1. Downloads all approved gene symbols from HGNC
2. Batch-queries Ensembl for GRCh38 coordinates (genes + variants)
3. Merges curated clinical metadata with Ensembl coordinates
4. Builds SQLite database (`lookup_tables.db`) with 6 tables: `genes`, `pgx_drugs`, `pgx_variants`, `trait_variants`, `carrier_genes`, `prs_weights`

### Runtime Dependencies

At runtime, GeneChat uses **only** local files — no external tools, no network calls.

| Library | What it does |
|---------|-------------|
| [pysam](https://pysam.readthedocs.io/) | Reads your annotated VCF via tabix index — replaces bcftools at runtime |
| [mcp](https://github.com/anthropics/python-sdk) | Implements the MCP server protocol (stdio transport) |
| SQLite (stdlib) | Queries lookup tables for gene coordinates, drug info, trait associations |
| [pydantic](https://docs.pydantic.dev/) | Validates tool inputs and config |

### What Each Tool Question Uses

| Question type | VCF fields read | Lookup tables queried |
|--------------|----------------|----------------------|
| "Tell me about rs4149056" | genotype, ANN, CLNSIG, CLNDN, AF | — |
| "Variants in BRCA1?" | genotype, ANN (impact filter) | `genes` (coordinates) |
| "Prescribed simvastatin — concerns?" | genotype at PGx positions | `pgx_drugs`, `pgx_variants`, `genes` |
| "ClinVar pathogenic variants?" | CLNSIG, CLNDN, CLNREVSTAT | `genes` (if gene filter) |
| "Caffeine metabolism?" | genotype at trait positions | `trait_variants` |
| "Carrier for anything?" | CLNSIG (pathogenic filter) | `carrier_genes`, `genes` |
| "Coronary artery disease risk?" | genotype at PRS positions | `prs_weights` |
| Genome overview | variant counts, CLNSIG summary | `pgx_variants` |

## Privacy

- Your genome data never leaves your machine
- No network calls during normal operation
- No telemetry, no analytics, no data collection
- Encrypted storage recommended (LUKS, FileVault, or VeraCrypt)

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
python scripts/build_lookup_db.py
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
