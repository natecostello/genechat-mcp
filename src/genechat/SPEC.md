# GeneChat MCP Server

## Purpose

GeneChat is a local-first MCP server that enables conversational AI assistants
to query a user's whole-genome sequencing (WGS) data. It wraps pysam and
curated reference databases (ClinVar, gnomAD, CPIC) behind MCP tools so LLMs
can answer natural-language questions about pharmacogenomics, disease risk,
carrier status, nutrigenomics, exercise genetics, and more — with genomic data
never leaving the user's machine.

The key design decision: tool responses are formatted markdown text that an LLM
can interpret directly. No raw data dumps, no JSON blobs for the model to parse.

## Core Mechanism

```
LLM Client (Claude Desktop / Claude Code)
    │ MCP Protocol (stdio or SSE)
    ▼
GeneChat MCP Server (Python, FastMCP)
    ├── Tools: query_variant, query_gene, query_clinvar, query_pgx,
    │         query_trait, query_carrier, calculate_prs, genome_summary
    ├── VCF Query Engine (pysam)
    ├── Lookup Tables (SQLite, read-only)
    └── Config Manager (TOML via tomllib)
    │ filesystem reads only
    ▼
Local Data (encrypted volume recommended)
    ├── annotated.vcf.gz + .tbi/.csi
    ├── reference databases
    └── lookup_tables.db
```

**Key files:**

- `server.py` — MCP entry point. Creates FastMCP, initializes engine + DB,
  registers all tools, runs stdio or SSE transport.
- `vcf_engine.py` — Read-only VCF query engine backed by pysam. All tool
  queries go through this. Validates regions/rsIDs with regex, caps results
  at `max_variants_per_response`.
- `lookup.py` — SQLite query layer (`LookupDB`). Read-only, case-insensitive
  queries. Gene coordinates, PGx drugs/variants, trait variants, carrier genes,
  PRS weights.
- `config.py` — TOML config via tomllib + Pydantic models (`AppConfig`).
  Supports `GENECHAT_CONFIG` and `GENECHAT_VCF` env vars, XDG config dir,
  and CWD fallback.
- `models.py` — Pydantic input validation models, one per tool.
- `parsers/` — SnpEff ANN field, ClinVar INFO fields, VCF GT field parsing.
- `tools/` — One module per tool. Each exports `register(mcp, engine, db, config)`.

**Technology stack:**

- Python 3.11+ with `mcp` (Anthropic Python SDK, FastMCP)
- `pysam` for VCF queries (replaced bcftools subprocess)
- SQLite via stdlib sqlite3 for lookup tables
- `uv` with pyproject.toml for packaging
- TOML config via stdlib tomllib
- pytest for testing
- SnpEff + ClinVar + gnomAD for one-time VCF annotation (not runtime)

**Data flow per tool call:**

1. Tool validates input (Pydantic model)
2. Looks up metadata from SQLite (gene coords, drug-gene pairs, etc.)
3. Queries VCF via pysam (region-based or full scan for rsID)
4. Parses annotations (SnpEff ANN, ClinVar, genotype)
5. Formats results as structured markdown
6. Appends medical disclaimer on clinical results

## Public Interface

| Export | Used By | Contract |
|---|---|---|
| 8 MCP tools | LLM clients via MCP protocol | Tool names, parameters, and output format stable across versions |
| `VCFEngine` class | All tool modules | `query_region`, `query_rsid`, `query_clinvar`, `stats` methods |
| `LookupDB` class | All tool modules | `get_gene`, `get_gene_region`, `search_pgx_*`, `get_trait_variants`, `get_carrier_genes`, `get_prs_weights` methods |
| `AppConfig` model | server.py, engine, DB | Pydantic model with genome, databases, server, display sections |
| `register(mcp, engine, db, config)` | `tools/__init__.py` | Every tool module exports this function |

### MCP Tools

| Tool | Input | Purpose |
|---|---|---|
| `query_variant` | rsid OR position | Single variant lookup with full annotation |
| `query_gene` | gene, impact_filter, max_results | List notable variants in a gene |
| `query_clinvar` | significance, gene?, condition? | Find clinically significant variants |
| `query_pgx` | drug OR gene | Pharmacogenomics: genotypes + CPIC guidance |
| `query_trait` | category?, trait?, gene? | Nutrigenomics, exercise, metabolism variants |
| `query_carrier` | condition?, acmg_only | Carrier screening panel |
| `calculate_prs` | trait OR prs_id | Polygenic risk scores with caveats |
| `genome_summary` | (none) | High-level variant counts and annotation summary |

## Invariants

| ID | Invariant | Why It Matters |
|---|---|---|
| INV-1 | Tool responses are formatted markdown, not raw data | LLMs interpret markdown directly; raw JSON/TSV degrades response quality |
| INV-2 | Medical disclaimer appended to every clinical result | Legal and ethical requirement — users must not treat output as diagnosis |
| INV-3 | VCF engine is read-only — no writes, no shell=True | Security: user genomic data must not be modified or exposed to injection |
| INV-4 | All VCF queries cap results at `max_variants_per_response` with truncation notice | Prevents unbounded responses that exceed LLM context windows |
| INV-5 | Region and rsID inputs are regex-validated before query | Prevents malformed queries from reaching pysam |
| INV-6 | Zero results are explained clearly ("no variants found" vs "gene not analyzed") | Users must distinguish "clean" from "not checked" |
| INV-7 | No network calls at runtime — all data local | Privacy guarantee: genomic data never leaves the machine |
| INV-8 | All genomic positions are GRCh38 with chr prefix | Coordinate system consistency across VCF, SQLite, and tool output |
| INV-9 | SQLite connection is read-only (`PRAGMA query_only = ON`) | Defense in depth: lookup DB must not be modified at runtime |
| INV-10 | Seed data accuracy > completeness | Better to ship 200 verified variants than 2000 unverified ones |

## Failure Modes

| ID | Symptom | Cause | Fix |
|---|---|---|---|
| FAIL-1 | "VCF file not found" on startup | `genome.vcf_path` config incorrect | Set correct path in config.toml or GENECHAT_VCF env var |
| FAIL-2 | "VCF index not found" on startup | Missing .tbi/.csi index | Run `tabix -p vcf <file>` or `pysam.tabix_index(...)` |
| FAIL-3 | "Lookup database not found" | SQLite DB not built or path wrong | Run `python scripts/build_lookup_db.py` |
| FAIL-4 | Empty results for known gene | Gene coordinates missing from genes table | Verify gene in `data/seed/genes_grch38.tsv`, rebuild DB |
| FAIL-5 | rsID query slow (full file scan) | pysam has no rsID index — must iterate all records | Expected behavior; suggest region-based query if gene known |
| FAIL-6 | Truncated results | Variant count exceeds `max_variants_per_response` | Narrow query (add gene filter, restrict region) |
| FAIL-7 | Missing annotation fields in output | VCF not annotated with SnpEff/ClinVar/gnomAD | Re-run `scripts/annotate.sh` |
| FAIL-8 | "Sample not found" error | Multi-sample VCF with wrong `sample_name` config | Set `genome.sample_name` in config.toml |

## Seed Data

**Two-layer data model:** Curated clinical metadata in `data/seed/curated/`
(hand-maintained). Genomic coordinates fetched from Ensembl by pipeline scripts.
The pipeline merges both into final TSVs in `data/seed/`, then rebuilds SQLite.

```
data/seed/curated/          ← Edit these (clinical knowledge)
  gene_lists.tsv            ← Gene symbols + category
  carrier_metadata.tsv      ← Conditions, inheritance, frequencies
  trait_metadata.tsv        ← Trait rsIDs, descriptions, evidence, PMIDs
  prs_scores.tsv            ← PRS weights + effect alleles

scripts/
  build_seed_data.py        ← Full pipeline: fetch coords → merge → SQLite
  build_lookup_db.py        ← Final TSVs → SQLite
  fetch_gene_coords.py      ← Ensembl → gene coordinates
  fetch_variant_coords.py   ← Ensembl → variant coordinates
  fetch_prs_coords.py       ← Ensembl → PRS variant coordinates
```

**Rebuild:** `uv run python scripts/build_seed_data.py`

The `genes` table includes all ~19,000 human protein-coding genes from HGNC.
You do not need to add genes manually for the LLM to query them.

## Testing

```bash
uv run pytest -x                            # Run all tests
uv run pytest tests/test_vcf_engine.py      # VCF engine tests
uv run pytest tests/test_lookup.py          # SQLite query tests
uv run pytest tests/test_tools/             # Tool output tests
uv run ruff check . && uv run ruff format . # Lint
```

### Coverage

| Spec Item | Test | Description |
|---|---|---|
| INV-1 | `test_tools/` | Verifies tool output is formatted markdown |
| INV-3 | `test_vcf_engine.py` | Verifies read-only operation, no shell execution |
| INV-4 | `test_vcf_engine.py::test_max_variants_cap` | Verifies truncation at cap |
| INV-5 | `test_vcf_engine.py::test_invalid_region` | Verifies regex validation rejects bad input |
| INV-9 | `test_lookup.py` | Verifies read-only SQLite access |
| FAIL-1 | `test_vcf_engine.py::test_missing_vcf` | Verifies FileNotFoundError on bad path |
| FAIL-3 | `test_lookup.py` | Verifies FileNotFoundError on missing DB |

## Dependencies

| Dependency | Type | SPEC.md Path |
|---|---|---|
| pysam | external | N/A — PyPI package |
| mcp (FastMCP) | external | N/A — Anthropic MCP SDK |
| SQLite (stdlib) | external | N/A — Python stdlib |
| SnpEff / ClinVar / gnomAD | external (build-time) | N/A — annotation pipeline only |
| Skills | internal | `.claude/skills/SPEC.md` |
