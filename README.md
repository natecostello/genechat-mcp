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
- [SnpEff/SnpSift](https://pcingola.github.io/SnpEff/) >= 5.2 (for one-time annotation only)
- [bcftools](https://samtools.github.io/bcftools/) >= 1.17 (for one-time annotation only)
- A consumer WGS VCF file (from Nucleus Genomics, Nebula, Sequencing.com, etc.)
- ~15 GB disk for reference databases, ~2 GB for your annotated VCF

VCF reading at runtime is handled by [pysam](https://pysam.readthedocs.io/), which is installed automatically via `uv sync`.

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/natecostello/genechat-mcp.git
cd genechat-mcp
uv sync
```

### 2. Download reference databases

```bash
bash scripts/setup_references.sh ./references
```

This downloads ClinVar and SnpEff databases. gnomAD must be downloaded separately due to size (see script output for instructions).

### 3. Annotate your VCF

```bash
CLINVAR_VCF=./references/clinvar_GRCh38.vcf.gz \
GNOMAD_VCF=./references/gnomad.exomes.v4.sites.vcf.bgz \
bash scripts/annotate.sh /path/to/your/raw.vcf.gz ./data
```

This runs SnpEff + ClinVar + gnomAD annotation (~20–30 minutes) and produces `data/annotated.vcf.gz`.

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

## Data Sources

All open-source, publicly available:

- [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) — clinical variant significance
- [gnomAD](https://gnomad.broadinstitute.org/) — population allele frequencies
- [SnpEff](https://pcingola.github.io/SnpEff/) — functional variant annotation
- [CPIC](https://cpicpgx.org/) — pharmacogenomics guidelines
- [PharmVar](https://www.pharmvar.org/) — pharmacogene variation
- [PGS Catalog](https://www.pgscatalog.org/) — polygenic risk scores

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

**Setup** (one-time, ~30 min, ~5 GB downloads):

```bash
bash scripts/setup_giab.sh ./giab
```

This downloads the GIAB VCF, fixes chromosome prefixes, and annotates with SnpEff + dbSNP + ClinVar. Prerequisites: bcftools, Java, SnpEff/SnpSift.

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
