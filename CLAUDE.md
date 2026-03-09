# GeneChat MCP Server

## PR Workflow

When submitting a PR, always request a GitHub Copilot review using:
```
gh pr edit <PR_NUMBER> --add-reviewer @copilot
```

## Code Review

GitHub Copilot is configured as a PR code reviewer. Its instructions are in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md). Copilot reviews
deliver inline comments with suggestion blocks. Use `/resolve-pr-comments` to process
review feedback.

## Plan Compliance

When a PR implements a plan, the PR description MUST include a compliance section:

### Plan Compliance
- [ ] Item 1: description — DONE / DEVIATED / DEFERRED
- [ ] Item 2: description — DONE / DEVIATED / DEFERRED
...

Each DEVIATED or DEFERRED item must include a one-line rationale.

## TODO

- [x] Make GeneChat installable via `uv tool install` / `pip install` — [plan](docs/pip-install-plan.md)
- [ ] Verify README quickstart instructions work end-to-end with a fresh VCF
- [ ] Documentation audit: create community files, decide on CLAUDE.md scope and planning docs
- [x] gnomAD incremental download+annotate+delete per chromosome (reduce peak disk from ~150 GB to ~17 GB)

## Project Overview

GeneChat is an open-source MCP (Model Context Protocol) server that enables conversational AI assistants to query a user's whole-genome sequencing (WGS) data stored locally. It wraps pysam and vendored reference databases (ClinVar, gnomAD, CPIC, PGS Catalog, GWAS Catalog) behind MCP tools, enabling natural-language questions about pharmacogenomics, disease risk, polygenic risk scores, and more — with genomic data never leaving the user's machine.

## Target User

Technically capable individuals with WGS data from consumer providers (Nucleus Genomics, Nebula Genomics, Sequencing.com). Comfortable with Docker/conda and config files. NOT expected to know bioinformatics.

## Core Use Cases

1. **Pharmacogenomics**: "I was just prescribed simvastatin. Any genetic concerns?" → Query SLCO1B1, return genotype + CPIC annotation
2. **Disease Risk**: "What does my genome say about cardiovascular risk?" → Query APOB, LDLR, PCSK9, APOE + ClinVar pathogenic variants
3. **Carrier Screening**: "Am I a carrier for anything?" → Query carrier panel genes for pathogenic ClinVar variants
4. **Nutrigenomics**: "How should I think about my diet?" → Query FTO, MCM6/LCT, FADS1/FADS2, MTHFR, APOA2, CYP1A2
5. **Exercise/Injury**: "I lift heavy and kiteboard — genetic factors?" → Query ACTN3, COL1A1, COL5A1, PPARGC1A, IL6/TNF
6. **Anesthesia Prep**: "Surgery coming up, what to tell anesthesiologist?" → Query BCHE, RYR1, CYP2D6, DPYD
7. **Variant Lookup**: "Tell me about rs4149056" or "What variants do I have in BRCA1?"

## Non-Goals (v1)

- Not a diagnostic tool (always includes medical disclaimers)
- Not a variant caller (assumes pre-called provider VCF)
- Not a FASTQ/CRAM processor
- Not a GUI (MCP server only; UI is the LLM chat)

---

# Architecture

```
LLM Client (Claude Desktop / Claude Code)
    │ MCP Protocol (stdio or SSE)
    ▼
GeneChat MCP Server (Python)
    ├── CLI: init, add, download, annotate, update, status, serve
    ├── Tools: query_variant, query_variants, query_gene, query_genes,
    │         query_clinvar, query_gwas, query_pgx, calculate_prs,
    │         genome_summary
    ├── engines: dict[str, VCFEngine] — one per registered genome
    ├── Patch Database (SQLite) — per-genome annotation overlay
    ├── Lookup Tables (SQLite)
    └── Config Manager (TOML) — [genomes.<label>] sections
    │ filesystem reads only
    ▼
Local Data (encrypted volume recommended)
    ├── raw.vcf.gz + .tbi per genome (never modified)
    ├── patch.db per genome (annotation overlay)
    ├── reference databases (~/.local/share/genechat/references/)
    └── lookup_tables.db
```

## Technology Stack

- Python 3.11+ with `mcp` official Anthropic Python SDK
- `pysam` (htslib) for VCF queries at runtime
- SQLite via stdlib sqlite3 for lookup tables
- `uv` with pyproject.toml for packaging
- TOML config (stdlib tomllib)
- pytest for testing
- SnpEff + bcftools for one-time annotation via `genechat init` (not runtime dependency)

## Prerequisites (User's Machine, NOT installed by project)

- bcftools >= 1.17 (conda install -c bioconda bcftools)
- tabix / htslib (required for ClinVar application; e.g. brew install htslib or conda install -c bioconda htslib)
- SnpEff (annotation step only; brew install brewsci/bio/snpeff)
- Python 3.11+
- ~15 GB for reference databases, ~2 GB for raw VCF + patch.db

---

# Build Instructions

Execute phases in this exact order. Verify each phase before moving on.

## Repository Structure

```
genechat-mcp/
  pyproject.toml
  config.toml.example
  README.md
  CLAUDE.md
  LICENSE                          # MIT
  claude_mcp_config.json.example   # Claude Desktop/Code MCP config
  docs/
    annotation-updates.md          # Incremental annotation update design
    security.md                    # Platform-specific encryption instructions
  scripts/
    build_seed_data.py             # Full pipeline: fetch from APIs → SQLite
    build_lookup_db.py             # Final seed TSVs → SQLite
    fetch_gene_coords.py           # HGNC + Ensembl API → gene coordinates
    fetch_cpic_data.py             # CPIC API → pgx_drugs + pgx_variants
    fetch_prs_data.py              # PGS Catalog FTP → prs_weights
    generate_test_vcf.py           # Creates synthetic VCF for testing
  data/
    seed/
      genes_grch38.tsv             # Generated: gene coordinates from Ensembl
      pgx_drugs.tsv                # Generated: CPIC drug-gene pairs
      pgx_variants.tsv             # Generated: PGx star-allele variants from CPIC
      prs_weights.tsv              # Generated: PRS weights from PGS Catalog
    lookup_tables.db               # Built by build_lookup_db.py (gitignored)
  src/
    genechat/
      __init__.py
      cli.py                       # CLI dispatcher: init, add, download, annotate, update, status, serve
      server.py                    # MCP server entry point
      config.py                    # TOML config loader + write_config
      vcf_engine.py                # pysam VCF query engine
      lookup.py                    # SQLite query layer
      tools/
        __init__.py
        common.py                  # resolve_engine() helper
        query_variant.py
        query_variants.py
        query_gene.py
        query_genes.py
        query_clinvar.py
        query_gwas.py
        query_pgx.py
        calculate_prs.py
        genome_summary.py
      parsers/
        __init__.py
        snpeff.py                  # Parse SnpEff ANN field
        clinvar.py                 # Parse ClinVar INFO fields
        genotype.py                # Parse GT field
      models.py                    # Pydantic models for tool I/O
  tests/
    conftest.py
    test_cli.py
    test_vcf_engine.py
    test_lookup.py
    test_tools/
      test_query_variant.py
      test_query_gene.py
      test_query_pgx.py
      test_query_clinvar.py
```

---

## Phase 1: Project Skeleton

### pyproject.toml

```toml
[project]
name = "genechat-mcp"
version = "0.1.0"
description = "MCP server for conversational personal genomics"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio"]

[project.scripts]
genechat = "genechat.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/genechat"]
```

### config.toml.example

```toml
[genomes.personal]
vcf_path = "/path/to/your/raw.vcf.gz"
genome_build = "GRCh38"
# patch_db = ""  # Auto-derived from VCF path

# [genomes.partner]  # Uncomment for paired analysis
# vcf_path = "/path/to/partner.vcf.gz"

[databases]
lookup_db = ""  # Leave empty to use built-in package data

[server]
transport = "stdio"
host = "localhost"
port = 3001
max_variants_per_response = 100

[display]
include_population_freq = true
include_raw_annotation = false
```

### claude_mcp_config.json.example

```json
{
  "mcpServers": {
    "genechat": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/genechat-mcp", "genechat"],
      "env": {
        "GENECHAT_CONFIG": "/path/to/config.toml"
      }
    }
  }
}
```

---

## Phase 2: Core Modules

### src/genechat/config.py

Load TOML config using tomllib (stdlib 3.11+). Support GENECHAT_CONFIG env var to override default path. Use Pydantic models or dataclasses for typed config sections: genome (vcf_path, genome_build, sample_name), databases (lookup_db), server (transport, host, port, max_variants_per_response, bcftools_timeout), display (include_population_freq, include_raw_annotation).

### src/genechat/parsers/snpeff.py

Parse SnpEff ANN field. ANN is comma-separated (multiple transcripts), each transcript is pipe-delimited. Format per transcript: Allele|Annotation|Impact|Gene_Name|Gene_ID|Feature_Type|Feature_ID|Transcript_BioType|Rank|HGVS.c|HGVS.p|cDNA_pos|CDS_pos|AA_pos|Distance|Errors

```python
def parse_ann_field(ann_raw: str) -> dict:
    """Parse first (most severe) SnpEff ANN entry. Return dict with keys:
    gene, effect, impact (HIGH/MODERATE/LOW/MODIFIER), transcript, hgvs_c, hgvs_p.
    Return empty dict if ann_raw is '.' or empty."""
    if not ann_raw or ann_raw == '.':
        return {}
    first = ann_raw.split(',')[0]
    parts = first.split('|')
    if len(parts) < 11:
        return {"raw": ann_raw}
    return {
        "gene": parts[3],
        "effect": parts[1],
        "impact": parts[2],
        "transcript": parts[6],
        "hgvs_c": parts[9],
        "hgvs_p": parts[10],
    }
```

### src/genechat/parsers/clinvar.py

```python
def parse_clinvar_fields(clnsig: str, clndn: str, clnrevstat: str) -> dict:
    """Parse ClinVar INFO fields. Return empty dict if no ClinVar data."""
    if not clnsig or clnsig == '.':
        return {}
    return {
        "significance": clnsig.replace('_', ' '),
        "condition": clndn.replace('_', ' ') if clndn and clndn != '.' else None,
        "review_status": clnrevstat.replace('_', ' ') if clnrevstat and clnrevstat != '.' else None,
    }
```

### src/genechat/parsers/genotype.py

```python
def parse_genotype(gt: str, ref: str, alt: str) -> dict:
    """Parse VCF GT field into human-readable form. Return dict with display (e.g. 'T/C')
    and zygosity (homozygous_ref, heterozygous, homozygous_alt, no_call).
    Handle both / (unphased) and | (phased) separators. Handle multi-allelic alts."""
    if gt in ('.', './.', '.|.'):
        return {"display": "no call", "zygosity": "no_call"}
    separator = '/' if '/' in gt else '|'
    alleles_idx = gt.split(separator)
    allele_map = {'0': ref}
    for i, a in enumerate(alt.split(','), 1):
        allele_map[str(i)] = a
    alleles = [allele_map.get(idx, '?') for idx in alleles_idx]
    display = '/'.join(alleles)
    if alleles[0] == alleles[1]:
        zygosity = "homozygous_ref" if alleles[0] == ref else "homozygous_alt"
    else:
        zygosity = "heterozygous"
    return {"display": display, "zygosity": zygosity}
```

### src/genechat/vcf_engine.py

This is the foundation. All tool queries go through it.

```python
"""VCF query engine wrapping bcftools."""
import subprocess
import re
import shutil
from pathlib import Path
from typing import Optional

REGION_PATTERN = re.compile(r'^chr[\dXYMT]{1,2}:\d+-\d+$')
RSID_PATTERN = re.compile(r'^rs\d+$')

# bcftools query format string — extracts all fields we need per variant
QUERY_FORMAT = (
    '%CHROM\\t%POS\\t%ID\\t%REF\\t%ALT\\t'
    '%INFO/ANN\\t%INFO/CLNSIG\\t%INFO/CLNDN\\t'
    '%INFO/CLNREVSTAT\\t%INFO/AF\\t%INFO/AF_popmax'
    '[\\t%GT]\\n'
)
```

Implement class `VCFEngine` with:
- `__init__(self, config)` — validate VCF exists, .tbi exists, bcftools in PATH
- `query_region(self, region, include_filter=None) -> list[dict]` — validate region format, call bcftools with -r
- `query_regions(self, regions, include_filter=None) -> list[dict]` — multiple regions comma-joined
- `query_rsid(self, rsid) -> list[dict]` — validate rsID format, use -i 'ID="rsid"'
- `query_clinvar(self, significance, region=None) -> list[dict]` — filter on CLNSIG
- `_execute_and_parse(self, cmd) -> list[dict]` — subprocess.run with list args (NEVER shell=True), timeout, parse output, cap at max_variants
- `_parse_line(self, line) -> dict` — split tab output, call parsers, return structured dict

Parsed variant dict structure:
```python
{
    "chrom": "chr22", "pos": 42127941, "rsid": "rs4149056",
    "ref": "T", "alt": "C",
    "genotype": {"display": "T/C", "zygosity": "heterozygous"},
    "annotation": {"gene": "SLCO1B1", "effect": "missense_variant",
                   "impact": "MODERATE", "hgvs_c": "c.521T>C", "hgvs_p": "p.Val174Ala"},
    "clinvar": {"significance": "drug response", "condition": "Simvastatin response",
                "review_status": "criteria provided, multiple submitters"},
    "population_freq": {"global": 0.14, "popmax": 0.21}
}
```

Safety: 30s timeout, read-only, regex-validated inputs, max variant cap with truncation notice.

### src/genechat/lookup.py

SQLite query layer. Initialize with config, open connection with row_factory=sqlite3.Row.

Methods:
- `get_gene(symbol) -> dict|None` — case-insensitive lookup
- `get_gene_region(symbol, padding=2000) -> str|None` — return "chrom:start-end" with padding
- `search_pgx_by_drug(drug_name) -> list[dict]` — search drug_name and aliases
- `search_pgx_by_gene(gene) -> list[dict]` — PGx drug entries for a gene
- `get_pgx_variants(gene) -> list[dict]` — known PGx variants for a gene
- `get_prs_weights(trait=None, prs_id=None) -> list[dict]`
- `list_prs_traits() -> list[dict]` — distinct PRS traits for dynamic availability listing

All queries case-insensitive. Return lists of dicts.

### src/genechat/models.py

Pydantic models for tool input validation. One model per tool's parameters. Not for output — tools return formatted text strings.

---

## Phase 3: MCP Tools

Each tool is a module in src/genechat/tools/. Each exports `register(mcp, engines, db, config)` where `engines` is a `dict[str, VCFEngine]`. Tools use `resolve_engine()` from `tools/common.py` to map the optional `genome` parameter to a specific engine.

Every tool:
1. Validates input
2. Looks up metadata from SQLite
3. Queries VCF engine
4. Formats results as structured markdown text for LLM consumption
5. Appends medical disclaimer on clinical results
6. Handles errors gracefully with helpful messages (not stack traces)

Medical disclaimer text (use on every clinical result):
"NOTE: This is informational only and not a medical diagnosis. Discuss findings with a healthcare provider before making health decisions."

### Tool 1: query_variant

Input: `rsid: str` OR `position: str` (one required)
Logic: If rsid, call engine.query_rsid(). If position, parse as region (pos to pos+1) and call engine.query_region().
Output format:
```
## Variant: rs4149056
Position: chr22:42127941 (GRCh38)
Your genotype: T/C (heterozygous)

### Functional Annotation
Gene: SLCO1B1
Effect: missense_variant (MODERATE impact)
Protein change: p.Val174Ala (c.521T>C)

### Clinical Significance
ClinVar: drug_response — Simvastatin response
Review: criteria provided, multiple submitters

### Population Frequency
Global: 14.0% | Popmax: 21.0%
```

### Tool 2: query_gene

Input: `gene: str`, `impact_filter: str = "HIGH,MODERATE"` (optional), `max_results: int = 50`
Logic: Look up gene coords from SQLite, query VCF region, filter by impact if specified.
Output: List of variants with annotation. If zero found, state clearly.

### Tool 3: query_clinvar

Input: `significance: str` (Pathogenic, Likely_pathogenic, risk_factor, drug_response, etc.), `gene: str` (optional), `condition: str` (optional), `max_results: int = 50`
Logic: Build bcftools CLNSIG filter. If gene specified, add region. If condition specified, post-filter on CLNDN. Whole-genome queries enforce hard limit of 100.
Output: Variants grouped by gene with clinical annotation.

### Tool 4: query_pgx

Input: `drug: str` OR `gene: str` (one required), `include_all_variants: bool = false`
Logic:
1. If drug: search pgx_drugs table (case-insensitive, check aliases) → get gene(s) and clinical_summary
2. Look up gene coordinates from genes table
3. Get known PGx variants from pgx_variants table
4. For each known PGx variant, query user VCF for genotype at that position
5. Compile results

Output format:
```
## Pharmacogenomics: Simvastatin
Related gene: SLCO1B1 (Solute carrier organic anion transporter)
Guideline: CPIC

### Your SLCO1B1 Variants
| Variant | Your Genotype | Function Impact |
|---------|--------------|-----------------|
| rs4149056 (*5) | T/C (het) | Decreased function |
| rs2306283 (*1B) | A/A (ref) | Normal function |

### Clinical Summary
[clinical_summary from pgx_drugs table]
[Add context about user's specific genotype combination]
```

### Tool 5: calculate_prs

Input: `trait: str` OR `prs_id: str`
Logic: Get PRS weights, query VCF for each variant, count effect alleles (0/1/2), multiply by weight, sum.
Output: Raw score, variants found/total, percentile if available.
MUST include caveats: PRS captures only common variant risk; performance varies by ancestry; one factor among many.

### Tool 6: genome_summary

Input: none
Logic: bcftools stats (cache after first call), count by type, count ClinVar by significance, count non-ref PGx variants.
Output: Overview with variant counts, clinical annotation summary, PGx summary.

---

## Phase 4: Server Entry Point

### src/genechat/server.py

```python
"""GeneChat MCP Server entry point."""
import asyncio
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
from genechat.config import load_config
from genechat.vcf_engine import VCFEngine
from genechat.lookup import LookupDB

def main():
    config = load_config(os.environ.get("GENECHAT_CONFIG", "config.toml"))
    app = Server("genechat")
    engine = VCFEngine(config)
    db = LookupDB(config)

    # Register all tools
    from genechat.tools import register_all
    register_all(app, engine, db, config)

    asyncio.run(_run(app))

async def _run(app):
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    main()
```

Must support both stdio (default) and SSE transport based on config.

---

## Phase 5: Scripts

### scripts/build_lookup_db.py

Read all TSV files from data/seed/, create SQLite database at data/lookup_tables.db. Use csv.DictReader with tab delimiter. CREATE TABLE statements match schemas below. CREATE INDEX as specified. Idempotent: drop and recreate tables if DB exists. Print row counts after loading.

### scripts/generate_test_vcf.py

Create synthetic VCF for testing. Include:
- Well-known PGx variants: rs4149056 (SLCO1B1, het T/C), rs1799853 (CYP2C9*2, hom ref), rs1801265 (DPYD, het)
- ClinVar variant: one pathogenic CFTR variant (het)
- Trait variants: rs1815739 (ACTN3, hom alt CC), rs762551 (CYP1A2, het)
- APOE: rs429358 + rs7412 (set up as E3/E4)
- Mix of genotypes. Proper VCF header with INFO field definitions for ANN, CLNSIG, CLNDN, CLNREVSTAT, AF, AF_popmax.
- bgzip and tabix the output (if available, otherwise note they're needed)

### Annotation (CLI subcommands, replacing former shell scripts)

Annotation is now handled entirely by Python CLI subcommands:

- `genechat init <vcf>` — Full first-time setup: downloads references, runs SnpEff + ClinVar annotation into patch.db, writes config
- `genechat download [--gnomad] [--all]` — Downloads reference databases (ClinVar, SnpEff DB, optionally gnomAD)
- `genechat annotate [--clinvar] [--gnomad] [--snpeff] [--all]` — Rebuild or update individual annotation layers in patch.db
- `genechat update [--apply]` — Check for newer reference versions and optionally re-annotate

The raw VCF is never modified. Annotations are stored in a SQLite patch database (`patch.db`).

---

## Phase 6: Seed Data

Create accurate TSV files. Header row matches SQL column names. Tab-delimited. UTF-8. Use `.` for missing values.

### SQLite Schemas

```sql
CREATE TABLE genes (
    symbol TEXT PRIMARY KEY, name TEXT, chrom TEXT NOT NULL,
    start INTEGER NOT NULL, end INTEGER NOT NULL, strand TEXT
);
CREATE INDEX idx_genes_chrom ON genes(chrom, start, end);

CREATE TABLE pgx_drugs (
    drug_name TEXT NOT NULL, gene TEXT NOT NULL,
    guideline_source TEXT, guideline_url TEXT, clinical_summary TEXT
);
CREATE INDEX idx_pgx_drug ON pgx_drugs(drug_name);

CREATE TABLE pgx_variants (
    gene TEXT NOT NULL, rsid TEXT, chrom TEXT NOT NULL, pos INTEGER NOT NULL,
    ref TEXT NOT NULL, alt TEXT NOT NULL, star_allele TEXT,
    function_impact TEXT, notes TEXT
);
CREATE INDEX idx_pgx_var_gene ON pgx_variants(gene);

CREATE TABLE prs_weights (
    prs_id TEXT NOT NULL, trait TEXT NOT NULL, rsid TEXT NOT NULL,
    chrom TEXT NOT NULL, pos INTEGER NOT NULL, effect_allele TEXT NOT NULL,
    weight REAL NOT NULL
);
CREATE INDEX idx_prs_id ON prs_weights(prs_id);
```

### Seed Data Specifications

**genes_grch38.tsv** — All ~19,000 human protein-coding genes. GRCh38 coordinates, chr prefix. Source: HGNC + Ensembl REST API. Generated by `fetch_gene_coords.py`.

**pgx_drugs.tsv** — CPIC Level A and B drug-gene pairs. Fetched from ClinPGx API by `fetch_cpic_data.py`. Includes cpic_level and pgx_testing columns.

**pgx_variants.tsv** — Star-allele defining variants with positions. Fetched from ClinPGx API by `fetch_cpic_data.py`. One row per (gene, rsid, star_allele) triple.

**prs_weights.tsv** — Polygenic risk score weights. Downloaded from PGS Catalog FTP by `fetch_prs_data.py`. Multiple PGS IDs supported.

### IMPORTANT

All genomic positions MUST be GRCh38. Use chr prefix. Double-check rsID-to-position mappings. For positions that cannot be verified at build time, add a comment header in the TSV noting the source and that positions should be verified against dbSNP before clinical use.

Seed data accuracy matters more than completeness. Better to ship 200 verified variants than 2000 unverified ones.

---

## Phase 7: Tests

### tests/conftest.py

Fixtures:
- `test_config`: Config pointing to test VCF and test DB
- `test_vcf`: Path to synthetic VCF (from generate_test_vcf.py)
- `test_db`: SQLite with known test data subset
- `test_engine`: VCFEngine using test fixtures
- `test_lookup`: LookupDB using test fixtures

### Test Cases

**test_vcf_engine.py**: query_region returns expected variants, query_rsid correct, query_clinvar returns pathogenic, max_variants cap works, invalid region raises ValueError, missing VCF raises FileNotFoundError.

**test_lookup.py**: get_gene returns correct coords, get_gene_region includes padding, search_pgx_by_drug finds by name, PRS weights filter by trait.

**test_tools/**: Each tool produces valid formatted output. Drug lookup returns variants with genotypes. rsID lookup returns full annotation.

---

## Design Principles

1. Tool responses = useful markdown text an LLM can directly interpret. No raw data dumps.
2. Medical disclaimers on every clinical result.
3. Zero results explained clearly. "No pathogenic variants found" ≠ "gene not analyzed."
4. Tool descriptions (docstrings LLM sees) must clearly explain purpose and when to use.
5. Graceful failures with helpful messages, not stack traces.
6. No network calls at runtime. Everything local.
7. Seed data accuracy > completeness. Include PubMed IDs. Honest evidence levels.

---

## Seed Data Pipeline

All seed data is fetched from external APIs at build time. No hand-curated files.

```
scripts/
  fetch_gene_coords.py      ← HGNC + Ensembl → gene coordinates
  fetch_cpic_data.py         ← CPIC API → pgx_drugs + pgx_variants
  fetch_prs_data.py          ← PGS Catalog FTP → prs_weights
  build_seed_data.py         ← Runs full pipeline: fetch → SQLite
  build_lookup_db.py         ← Final TSVs → SQLite (called by build_seed_data.py)

data/seed/                   ← Generated output (committed to git)
  genes_grch38.tsv, pgx_drugs.tsv, pgx_variants.tsv, prs_weights.tsv
```

**Rebuild everything:** `uv run python scripts/build_seed_data.py`

This fetches latest data from HGNC, CPIC, and PGS Catalog, then rebuilds all TSVs + SQLite. Idempotent, safe to re-run. Requires internet access (build-time only, never at runtime).

### Gene Coverage

The `genes` table includes ALL ~19,000 human protein-coding genes, fetched automatically from HGNC. **You do not need to add genes manually for the LLM to query them.** If the LLM asks about any protein-coding gene, it will already have coordinates.

### Data Sources

| Data | Source API | Script | License |
|------|-----------|--------|---------|
| Gene coordinates | HGNC + Ensembl REST | `fetch_gene_coords.py` | Open |
| PGx drugs + variants | [ClinPGx API](https://api.cpicpgx.org/v1/) (CPIC) | `fetch_cpic_data.py` | CC0 |
| PRS weights | [PGS Catalog FTP](https://www.pgscatalog.org/) | `fetch_prs_data.py` | CC BY 4.0 |

### Adding a New PRS Trait

Edit `scripts/fetch_prs_data.py` — add the PGS ID to the `PGS_SCORES` list:

```python
PGS_SCORES = [
    ("PGS000010", "Coronary artery disease", None),
    ("PGS000011", "Coronary artery disease", None),
    ("PGS000074", "Colorectal cancer", None),
    ("PGS000034", "Adult body mass index (BMI)", None),
    # Add new entries here
]
```

The `calculate_prs` tool dynamically lists available traits, so no tool code changes are needed.

### After Any Edit

```bash
uv run python scripts/build_seed_data.py    # Fetch from APIs + rebuild SQLite
uv run pytest -x                             # Verify nothing broke
uv run ruff check . && uv run ruff format .  # Lint
```
