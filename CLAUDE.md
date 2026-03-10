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
- [ ] Item 1: description -- DONE / DEVIATED / DEFERRED
- [ ] Item 2: description -- DONE / DEVIATED / DEFERRED
...

Each DEVIATED or DEFERRED item must include a one-line rationale.

## Architecture Decision Records

ADRs live in `docs/architecture/` using [MADR 4.0](https://adr.github.io/madr/) format with these project-specific additions:

### When to write an ADR

Write an ADR when a decision:
- Changes how data flows between components (VCF, patch.db, lookup.db, GWAS db)
- Affects the MCP tool interface (new tools, changed parameters, changed output format)
- Changes the annotation pipeline architecture (new sources, different processing)
- Affects module boundaries or adds/removes significant components
- Involves trade-offs between competing concerns that were debated
- Is hard to reverse once implemented
- Affects non-functional requirements (performance, security, privacy)

If in doubt, write the ADR — a short record is better than an undocumented decision.

### Template conventions

- **Frontmatter** must include `status`, `date`, and `related ADRs` (list of links to related ADRs in this directory). Optional fields: `decision-makers`, `consulted`, `informed` (per MADR 4.0 RACI convention)
- **Decision Drivers** should capture the forces that shaped the decision
- **Decision Outcome** must reference the implementation plan with its file path and the git commit hash where the plan can be found (plans are deleted from the tree after implementation, but preserved in git history)
- **Confirmation** section should describe how compliance is verified (tests, code review, etc.)
- **Pros and Cons of the Options** — expand each option with bullet-point pros/cons, not just a one-line description
- **More Information** must list the PRs that implemented the decision (and the PR that removed legacy code, if applicable)

### Numbering and lifecycle

- Sequentially numbered: `0001-short-title.md`, `0002-...`, etc.
- Update `docs/architecture/README.md` index when adding or changing an ADR
- Status values: `proposed`, `accepted`, `rejected`, `deprecated`, `superseded by ADR-NNNN`
- Use `rejected` when an approach was evaluated and deliberately not adopted — this documents "why we didn't do X"

### Amendments and updates

- For **partial updates** to an existing decision, create a new ADR that references the original. Update the original's "More Information" section to note "Amended by ADR-NNNN" but keep its status as `accepted`.
- Reserve `superseded by ADR-NNNN` for complete replacement of a decision.
- ADRs can be written **retroactively**. If a past decision was architecturally significant, write the ADR with the original decision date and add a note in More Information: "Documented retroactively on YYYY-MM-DD."

### Plan documents

Active implementation plans live in `docs/plans/` while work is in progress. When the plan is fully implemented and the PR merges, the plan file is deleted from the tree. The ADR's "Decision Outcome" section preserves a reference to the plan's git commit hash so it remains discoverable via `git show <hash>:docs/plans/<file>`.

## TODO

- [ ] Verify README quickstart instructions work end-to-end with a fresh VCF

---

## Project Overview

GeneChat is an open-source MCP (Model Context Protocol) server that enables conversational AI assistants to query a user's whole-genome sequencing (WGS) data stored locally. It wraps pysam and vendored reference databases (ClinVar, gnomAD, CPIC, PGS Catalog, GWAS Catalog) behind MCP tools, enabling natural-language questions about pharmacogenomics, disease risk, polygenic risk scores, and more -- with genomic data never leaving the user's machine.

## Target User

Technically capable individuals with WGS data from consumer providers (Nucleus Genomics, Nebula Genomics, Sequencing.com). Comfortable with Docker/conda and config files. NOT expected to know bioinformatics.

## Core Use Cases

1. **Pharmacogenomics**: "I was just prescribed simvastatin. Any genetic concerns?"
2. **Disease Risk**: "What does my genome say about cardiovascular risk?"
3. **Carrier Screening**: "Am I a carrier for anything?"
4. **Nutrigenomics**: "How should I think about my diet?"
5. **Exercise/Injury**: "I lift heavy and kiteboard -- genetic factors?"
6. **Anesthesia Prep**: "Surgery coming up, what to tell anesthesiologist?"
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
    | MCP Protocol (stdio or SSE)
    v
GeneChat MCP Server (Python)
    +-- CLI: init, add, annotate, install, update, status, serve
    +-- Tools: query_variant, query_variants, query_gene, query_genes,
    |         query_clinvar, query_gwas, query_pgx, calculate_prs,
    |         genome_summary
    +-- engines: dict[str, VCFEngine] -- one per registered genome
    +-- Patch Database (SQLite) -- per-genome annotation overlay
    +-- Lookup Tables (SQLite)
    +-- Config Manager (TOML) -- [genomes.<label>] sections
    | filesystem reads only
    v
Local Data (encrypted volume recommended)
    +-- raw.vcf.gz + .tbi per genome (never modified)
    +-- patch.db per genome (annotation overlay)
    +-- reference databases (~/.local/share/genechat/references/)
    +-- lookup_tables.db
```

## Technology Stack

- Python 3.11+ with `mcp` official Anthropic Python SDK
- `pysam` (htslib) for VCF queries at runtime
- SQLite via stdlib sqlite3 for lookup tables and patch databases
- `uv` with pyproject.toml for packaging
- TOML config (stdlib tomllib) with `platformdirs` for OS-standard paths
- pytest for testing, ruff for linting
- SnpEff + bcftools for one-time annotation via `genechat init` (not runtime dependencies)

## Prerequisites (User's Machine)

- Python 3.11+
- bcftools >= 1.17 and SnpEff (annotation only, not runtime)
- ~15 GB for reference databases, ~2 GB for raw VCF + patch.db

---

## Repository Structure

```
genechat-mcp/
  pyproject.toml
  config.toml.example
  claude_mcp_config.json.example
  README.md
  CLAUDE.md
  CONTRIBUTING.md
  SECURITY.md
  LICENSE
  docs/
    architecture/                  # Architecture Decision Records (MADR 4.0)
    plans/                         # Active implementation plans
    annotation-updates.md          # Incremental annotation update design
    security.md                    # Platform-specific encryption instructions
  .github/
    copilot-instructions.md        # Copilot PR review instructions
    PULL_REQUEST_TEMPLATE.md
    ISSUE_TEMPLATE/
  scripts/
    build_seed_data.py             # Full pipeline: fetch from APIs -> SQLite
    build_lookup_db.py             # Seed TSVs -> SQLite
    build_gwas_db.py               # GWAS Catalog -> standalone gwas.db
    fetch_gene_coords.py           # HGNC + Ensembl API -> gene coordinates
    fetch_cpic_data.py             # CPIC API -> pgx_drugs + pgx_variants
    fetch_prs_data.py              # PGS Catalog FTP -> prs_weights
    generate_test_vcf.py           # Creates synthetic VCF for testing
  data/
    seed/                          # Generated TSVs (committed to git)
  src/
    genechat/
      __init__.py
      cli.py                       # CLI: init, add, annotate, install, update, status, serve
      server.py                    # MCP server entry point
      config.py                    # TOML config loader + write_config
      vcf_engine.py                # pysam VCF query engine (genotypes from VCF, annotations from patch.db)
      patch.py                     # SQLite patch database (annotation overlay)
      lookup.py                    # SQLite query layer for seed data
      download.py                  # Reference database download functions
      gwas.py                      # GWAS Catalog DB builder + query
      update.py                    # Reference version checker
      models.py                    # Pydantic models for tool I/O
      data/
        __init__.py
        lookup_tables.db           # Seed-only DB shipped in wheel (~1.7 MB)
      tools/
        __init__.py
        common.py                  # resolve_engine() helper
        formatting.py              # Shared output formatting
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
  tests/
    conftest.py
    test_cli.py
    test_vcf_engine.py
    test_patch.py
    test_lookup.py
    test_config.py
    test_download.py
    test_gwas.py
    test_update.py
    test_parsers.py
    test_packaging.py
    test_tools/
    e2e/                           # GIAB NA12878 integration tests
```

---

## Seed Data Pipeline

All seed data is fetched from external APIs at build time. No hand-curated files.

| Source | What it provides | Script |
|--------|-----------------|--------|
| HGNC + Ensembl | All ~19,000 protein-coding gene coordinates | `fetch_gene_coords.py` |
| CPIC (ClinPGx API) | PGx drug-gene guidelines + star-allele variants | `fetch_cpic_data.py` |
| PGS Catalog FTP | Polygenic risk score weights | `fetch_prs_data.py` |

**Rebuild everything:** `uv run python scripts/build_seed_data.py`

The `genes` table includes ALL ~19,000 human protein-coding genes. The LLM can query any protein-coding gene without manual additions.

To add a new PRS trait, add the PGS ID to `PGS_SCORES` in `scripts/fetch_prs_data.py`. The `calculate_prs` tool dynamically lists available traits.
