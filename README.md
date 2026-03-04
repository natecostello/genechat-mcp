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
    → GeneChat queries your local VCF with bcftools
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

## Quick Start (Docker)

The fastest way to get running. No need to install bcftools, SnpEff, or Python separately.

### 1. Build the image

```bash
git clone https://github.com/youruser/genechat-mcp.git
cd genechat-mcp
docker build -t genechat-mcp .
```

### 2. Annotate your VCF (one-time)

You still need to annotate your raw VCF once. See the [Annotate your VCF](#3-annotate-your-vcf) section below — or use the Docker image itself:

```bash
docker run --rm -v /path/to/references:/refs -v /path/to/data:/data \
  --entrypoint bash genechat-mcp \
  -c "CLINVAR_VCF=/refs/clinvar_GRCh38.vcf.gz GNOMAD_VCF=/refs/gnomad.exomes.v4.sites.vcf.bgz bash scripts/annotate.sh /data/raw.vcf.gz /data"
```

### 3. Connect to Claude

Add to your Claude Desktop or Claude Code MCP config (e.g. `~/.claude.json` or Claude Desktop settings):

```json
{
  "mcpServers": {
    "genechat": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/your/genome.vcf.gz:/data/genome.vcf.gz:ro",
        "-v", "/path/to/your/genome.vcf.gz.tbi:/data/genome.vcf.gz.tbi:ro",
        "-e", "GENECHAT_VCF=/data/genome.vcf.gz",
        "genechat-mcp"
      ]
    }
  }
}
```

Replace `/path/to/your/genome.vcf.gz` (and `.tbi`) with the actual paths to your annotated VCF and its index.

### 4. Start asking questions

Open Claude and ask about your genetics. GeneChat's tools will appear automatically.

---

## Prerequisites

- Python 3.11+
- [bcftools](https://samtools.github.io/bcftools/) >= 1.17
- [SnpEff/SnpSift](https://pcingola.github.io/SnpEff/) >= 5.2 (for one-time annotation only)
- A consumer WGS VCF file (from Nucleus Genomics, Nebula, Sequencing.com, etc.)
- ~15 GB disk for reference databases, ~2 GB for your annotated VCF

Install bcftools via conda:
```bash
conda install -c bioconda bcftools
```

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/youruser/genechat-mcp.git
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

### 6. Connect to Claude

Add to your Claude Desktop or Claude Code MCP config:

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

## Important Disclaimer

GeneChat is an informational tool, not a medical device. It is not a substitute for professional genetic counseling or medical advice. Always discuss genetic findings with a qualified healthcare provider before making health decisions.

## License

MIT
