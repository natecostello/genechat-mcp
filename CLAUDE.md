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

## Project Overview

GeneChat is an open-source MCP (Model Context Protocol) server that enables conversational AI assistants to query a user's whole-genome sequencing (WGS) data stored locally. It wraps bcftools and curated reference databases (ClinVar, gnomAD, PharmGKB/CPIC) behind MCP tools, enabling natural-language questions about pharmacogenomics, disease risk, carrier status, nutrigenomics, exercise genetics, and more — with genomic data never leaving the user's machine.

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
- Not multi-user (single genome, local)
- Not a GUI (MCP server only; UI is the LLM chat)

---

# Architecture

```
LLM Client (Claude Desktop / Claude Code)
    │ MCP Protocol (stdio or SSE)
    ▼
GeneChat MCP Server (Python)
    ├── Tools: query_variant, query_gene, query_clinvar, query_pgx,
    │         query_trait, query_carrier, calculate_prs, genome_summary
    ├── VCF Query Engine (bcftools subprocess)
    ├── Lookup Tables (SQLite)
    └── Config Manager (TOML)
    │ filesystem reads only
    ▼
Local Data (encrypted volume recommended)
    ├── annotated.vcf.gz + .tbi
    ├── reference databases
    └── lookup_tables.db
```

## Technology Stack

- Python 3.11+ with `mcp` official Anthropic Python SDK
- `bcftools` via subprocess for VCF queries (never shell=True)
- SQLite via stdlib sqlite3 for lookup tables
- `uv` with pyproject.toml for packaging
- TOML config (stdlib tomllib)
- pytest for testing
- SnpSift + SnpEff for one-time annotation (not runtime dependency)

## Prerequisites (User's Machine, NOT installed by project)

- bcftools >= 1.17 (conda install -c bioconda bcftools)
- SnpSift/SnpEff >= 5.2 (annotation step only)
- tabix (part of htslib, comes with bcftools)
- Python 3.11+
- ~15 GB for reference databases, ~2 GB for annotated VCF

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
  scripts/
    setup_references.sh            # Downloads ClinVar, gnomAD, SnpEff DB
    annotate.sh                    # One-time VCF annotation pipeline
    build_lookup_db.py             # Builds SQLite from seed TSVs
    generate_test_vcf.py           # Creates synthetic VCF for testing
  data/
    seed/
      genes_grch38.tsv             # Gene coordinates (subset covering all referenced genes)
      pgx_drugs.tsv                # CPIC drug-gene pairs
      pgx_variants.tsv             # PGx key variants with star alleles
      trait_variants.tsv           # Curated trait SNPs
      carrier_genes.tsv            # Carrier screening panel
      prs_weights.tsv              # PGS Catalog scores (start small)
    lookup_tables.db               # Built by build_lookup_db.py (gitignored)
  src/
    genechat/
      __init__.py
      server.py                    # MCP server entry point
      config.py                    # TOML config loader
      vcf_engine.py                # bcftools wrapper
      lookup.py                    # SQLite query layer
      tools/
        __init__.py
        query_variant.py
        query_gene.py
        query_clinvar.py
        query_pgx.py
        query_trait.py
        query_carrier.py
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
[genome]
vcf_path = "/path/to/your/annotated.vcf.gz"
genome_build = "GRCh38"
sample_name = ""

[databases]
lookup_db = "./data/lookup_tables.db"

[server]
transport = "stdio"
host = "localhost"
port = 3001
max_variants_per_response = 100
bcftools_timeout = 30

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
- `get_trait_variants(category=None, trait=None, gene=None) -> list[dict]` — filter by any combo
- `get_carrier_genes(condition=None, acmg_only=False) -> list[dict]`
- `get_prs_weights(trait=None, prs_id=None) -> list[dict]`

All queries case-insensitive. Return lists of dicts.

### src/genechat/models.py

Pydantic models for tool input validation. One model per tool's parameters. Not for output — tools return formatted text strings.

---

## Phase 3: MCP Tools

Each tool is a module in src/genechat/tools/. Each exports `register(app, engine, db, config)` that uses `@app.tool()` to register the tool.

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

### Tool 5: query_trait

Input: `category: str` (nutrigenomics, exercise, metabolism, sleep, caffeine, alcohol, cardiovascular, inflammation), `trait: str` (optional specific trait), `gene: str` (optional)
Logic: Query trait_variants table, for each matched variant query user VCF, combine. Group by trait, sort by evidence level.
Output: One section per trait with genotype, interpretation, evidence level, PubMed ref.

### Tool 6: query_carrier

Input: `condition: str` (optional), `acmg_only: bool = true`, `max_results: int = 50`
Logic: Get gene list from carrier_genes, for each look up coords and query VCF for ClinVar pathogenic variants.
Output: Which genes have pathogenic variants (carrier positive) vs clear. Note that absence of known pathogenic variants does not guarantee non-carrier status.

### Tool 7: calculate_prs

Input: `trait: str` OR `prs_id: str`
Logic: Get PRS weights, query VCF for each variant, count effect alleles (0/1/2), multiply by weight, sum.
Output: Raw score, variants found/total, percentile if available.
MUST include caveats: PRS captures only common variant risk; performance varies by ancestry; one factor among many.

### Tool 8: genome_summary

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
    from genechat.tools import (query_variant, query_gene, query_clinvar,
                                 query_pgx, query_trait, query_carrier,
                                 calculate_prs, genome_summary)
    for module in [query_variant, query_gene, query_clinvar, query_pgx,
                   query_trait, query_carrier, calculate_prs, genome_summary]:
        module.register(app, engine, db, config)

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

### scripts/annotate.sh

```bash
#!/bin/bash
set -euo pipefail
INPUT_VCF="$1"
OUTPUT_DIR="${2:-.}"
echo "Step 1: SnpEff functional annotation..."
snpEff ann -v GRCh38.p14 "$INPUT_VCF" > "$OUTPUT_DIR/step1_snpeff.vcf"
echo "Step 2: ClinVar annotation..."
SnpSift annotate "$CLINVAR_VCF" "$OUTPUT_DIR/step1_snpeff.vcf" > "$OUTPUT_DIR/step2_clinvar.vcf"
echo "Step 3: gnomAD frequency annotation..."
SnpSift annotate -info AF,AF_popmax "$GNOMAD_VCF" "$OUTPUT_DIR/step2_clinvar.vcf" > "$OUTPUT_DIR/annotated.vcf"
echo "Step 4: Compress and index..."
bgzip "$OUTPUT_DIR/annotated.vcf"
tabix -p vcf "$OUTPUT_DIR/annotated.vcf.gz"
rm -f "$OUTPUT_DIR/step1_snpeff.vcf" "$OUTPUT_DIR/step2_clinvar.vcf"
echo "Done: $OUTPUT_DIR/annotated.vcf.gz"
```

### scripts/setup_references.sh

Download ClinVar VCF from NCBI FTP, download SnpEff DB. Note gnomAD requires manual download due to size.

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
    drug_name TEXT NOT NULL, drug_aliases TEXT, gene TEXT NOT NULL,
    guideline_source TEXT, guideline_url TEXT, clinical_summary TEXT
);
CREATE INDEX idx_pgx_drug ON pgx_drugs(drug_name);

CREATE TABLE pgx_variants (
    gene TEXT NOT NULL, rsid TEXT, chrom TEXT NOT NULL, pos INTEGER NOT NULL,
    ref TEXT NOT NULL, alt TEXT NOT NULL, star_allele TEXT,
    function_impact TEXT, notes TEXT
);
CREATE INDEX idx_pgx_var_gene ON pgx_variants(gene);

CREATE TABLE trait_variants (
    rsid TEXT NOT NULL, chrom TEXT NOT NULL, pos INTEGER NOT NULL,
    ref TEXT NOT NULL, alt TEXT NOT NULL, gene TEXT,
    trait_category TEXT NOT NULL, trait TEXT NOT NULL,
    effect_allele TEXT NOT NULL, effect_description TEXT NOT NULL,
    evidence_level TEXT, pmid TEXT
);
CREATE INDEX idx_trait_category ON trait_variants(trait_category);

CREATE TABLE carrier_genes (
    gene TEXT PRIMARY KEY, condition_name TEXT NOT NULL,
    inheritance TEXT NOT NULL, carrier_frequency TEXT, acmg_recommended BOOLEAN
);

CREATE TABLE prs_weights (
    prs_id TEXT NOT NULL, trait TEXT NOT NULL, rsid TEXT NOT NULL,
    chrom TEXT NOT NULL, pos INTEGER NOT NULL, effect_allele TEXT NOT NULL,
    weight REAL NOT NULL, reference TEXT
);
CREATE INDEX idx_prs_id ON prs_weights(prs_id);
```

### Seed Data Specifications

**genes_grch38.tsv** — Start with ~500 genes covering all genes referenced by other seed files plus common clinically relevant genes. GRCh38 coordinates, chr prefix. Source: Ensembl/NCBI Gene.

**pgx_drugs.tsv** — CPIC Level A and B pairs. Required entries:
warfarin/CYP2C9, warfarin/VKORC1, clopidogrel/CYP2C19, codeine/CYP2D6, simvastatin/SLCO1B1, tamoxifen/CYP2D6, ondansetron/CYP2D6, fluorouracil/DPYD, azathioprine/TPMT, sertraline/CYP2C19, omeprazole/CYP2C19, metoprolol/CYP2D6, tramadol/CYP2D6, ibuprofen/CYP2C9, phenytoin/CYP2C9, succinylcholine/BCHE, volatile_anesthetics/RYR1, allopurinol/HLA-B, carbamazepine/HLA-B, abacavir/HLA-B.

**pgx_variants.tsv** — Star-allele defining variants. Required genes with key alleles:
CYP2D6 (*3,*4,*5,*6,*10,*17,*41), CYP2C19 (*2,*3,*17), CYP2C9 (*2,*3), SLCO1B1 (*5,*15), DPYD (*2A), VKORC1 (-1639G>A), TPMT (*2,*3A,*3B,*3C), NUDT15 (*3), UGT1A1 (*6,*28).

**trait_variants.tsv** — Well-validated trait SNPs. Required entries:
- Nutrigenomics: FTO rs9939609 (obesity), MCM6 rs4988235 (lactose), FADS1 rs174547 (omega), MTHFR rs1801133 C677T, MTHFR rs1801131 A1298C, APOA2 rs5082 (sat fat), TAS2R38 rs713598 (bitter taste)
- Exercise: ACTN3 rs1815739 (sprint/power), COL1A1 rs1800012 (tendon), COL5A1 rs12722 (ligament), PPARGC1A rs8192678 (endurance), IL6 rs1800795 (inflammation), TNF rs1800629
- Metabolism: CYP1A2 rs762551 (caffeine), ADH1B rs1229984 (alcohol), ALDH2 rs671 (alcohol flush)
- Cardiovascular: F5 rs6025 (Factor V Leiden), F2 rs1799963 (prothrombin), APOE rs429358+rs7412
- Other: HFE rs1800562 C282Y, HFE rs1799945 H63D, UGT1A1 rs8175347 (Gilbert's)

Include effect_allele, effect_description, evidence_level (strong/moderate/preliminary), PubMed IDs.

**carrier_genes.tsv** — ACMG recommended + expanded: CFTR (CF), HBB (sickle cell), SMN1 (SMA), HEXA (Tay-Sachs), GBA (Gaucher), FMR1 (Fragile X), PAH (PKU), ASPA (Canavan), GAA (Pompe), GJB2 (hearing loss), SLC26A4 (Pendred), BCKDHA (MSUD), HEXA (Tay-Sachs), FANCC (Fanconi), BLM (Bloom), MCOLN1 (Mucolipidosis IV).

**prs_weights.tsv** — Start with ONE validated CAD PRS (50-500 variants, not genome-wide). Source: PGS Catalog.

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

**test_lookup.py**: get_gene returns correct coords, get_gene_region includes padding, search_pgx_by_drug finds name and alias, trait_variants filter by category, carrier_genes filter by acmg.

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
