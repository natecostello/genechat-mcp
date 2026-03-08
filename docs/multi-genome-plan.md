# Plan: Multi-Genome Support

## Context

GeneChat currently supports a single genome per server instance. The `[genome]` config section holds one `vcf_path` and one `patch_db`. This prevents:

1. **E2e testing alongside a personal genome** — running GIAB e2e tests requires swapping the config or using env var overrides, and both genomes can't be registered simultaneously.
2. **Paired analysis** — couples planning a family need carrier screening across both genomes. A user might want to compare their genome with a family member's.

This plan adds named genome support with the ability to query one or two genomes in a single tool call. It also folds in related work: auto-fixing bare contig names during init, consolidating remaining scripts into CLI subcommands, and removing `setup_giab.py` in favor of the standard user workflow.

## Design

### Config Format

Replace `[genome]` with `[genomes.<label>]` sections. Backward-compatible: a bare `[genome]` section is treated as `[genomes.default]`.

```toml
[genomes.nate]
vcf_path = "/path/to/nate.vcf.gz"
patch_db = "/path/to/nate.patch.db"
sample_name = "Nate"

[genomes.giab]
vcf_path = "./giab/HG001_raw.vcf.gz"
patch_db = "./giab/HG001_raw.patch.db"
sample_name = "GIAB NA12878"

# Legacy format still works (treated as [genomes.default]):
# [genome]
# vcf_path = "/path/to/my.vcf.gz"
```

### Genome Selection

**At server startup:** Load ALL registered genomes. Each gets its own `VCFEngine` instance. The first genome listed (or `[genome]` if using legacy format) is the default.

**At query time:** Every tool gains an optional `genome` parameter (default: first registered genome). For paired queries, tools that support it gain an optional `genome2` parameter.

**CLI:** `genechat init <vcf> --label nate` writes to `[genomes.nate]`. Without `--label`, writes to `[genomes.default]`. `genechat status` lists all registered genomes.

**Env var:** `GENECHAT_GENOME=giab` selects which genome tools query by default (overridable per tool call). `GENECHAT_VCF` continues to work as a single-genome shortcut.

### Paired Queries

Tools that support paired analysis:

| Tool | Paired behavior |
|------|----------------|
| `query_variant` | Show both genotypes side-by-side |
| `query_variants` | Batch lookup across both genomes |
| `query_gene` | List notable variants from both |
| `query_clinvar` | Find pathogenic variants in both |
| `query_pgx` | Compare PGx profiles |
| `calculate_prs` | Compare risk scores |
| `genome_summary` | Side-by-side overview |

Tools where pairing doesn't apply:
- `query_gwas` — trait associations, not genome-specific
- `query_genes` — thin wrapper around `query_gene`

**Output format for paired results:**

```markdown
## Variant: rs4149056
Position: chr22:42127941 (GRCh38)

### Nate
Genotype: T/C (heterozygous)
...

### Partner
Genotype: T/T (homozygous reference)
...
```

For carrier screening, the LLM can identify variants where both partners are carriers and flag autosomal recessive risk.

### Architecture Changes

```
server.py
  - engines: dict[str, VCFEngine]    # label → engine
  - default_genome: str              # label of default genome
  - register_all() passes engines dict instead of single engine

tools/*.py
  - register(mcp, engines, db, config)  # engines is now a dict
  - Each tool resolves genome label → engine at call time
  - Optional genome2 parameter for paired queries

config.py
  - GenomeConfig unchanged
  - AppConfig.genome → AppConfig.genomes: dict[str, GenomeConfig]
  - Backward compat: [genome] → genomes["default"]
  - write_config() accepts label parameter

cli.py
  - genechat init --label writes to [genomes.<label>]
  - genechat add --label writes to [genomes.<label>]
  - genechat status lists all genomes with their annotation state
```

## Files to Modify

### Core changes

| File | Change |
|------|--------|
| `src/genechat/config.py` | `AppConfig.genomes: dict[str, GenomeConfig]`, backward-compat loader, `write_config()` with label |
| `src/genechat/server.py` | Build `engines` dict from `config.genomes`, pass to `register_all()` |
| `src/genechat/tools/__init__.py` | `register_all(mcp, engines, db, config)` — engines is dict |
| `src/genechat/tools/query_variant.py` | Add `genome`, `genome2` params, resolve engine |
| `src/genechat/tools/query_variants.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/query_gene.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/query_genes.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/query_clinvar.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/query_pgx.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/calculate_prs.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/genome_summary.py` | Add `genome`, `genome2` params |
| `src/genechat/tools/query_gwas.py` | Add `genome` param only (no pairing) |
| `src/genechat/cli.py` | `init`/`add` write to `[genomes.<label>]`, `status` lists all, contig auto-fix, `update --seeds`, `download --gwas` |
| `config.toml.example` | Update to show `[genomes.personal]` format |

### Helper: genome resolution

Add a shared utility (e.g. in `tools/__init__.py` or a new `tools/common.py`):

```python
def resolve_engine(engines: dict[str, VCFEngine], genome: str | None, config) -> tuple[str, VCFEngine]:
    """Resolve a genome label to its VCFEngine.

    Returns (label, engine). Raises ValueError with available genome names if not found.
    """
    if genome is None:
        genome = config.default_genome
    if genome not in engines:
        available = ", ".join(engines.keys())
        raise ValueError(f"Unknown genome '{genome}'. Available: {available}")
    return genome, engines[genome]
```

### Files to delete

| File | Reason |
|------|--------|
| `scripts/setup_giab.py` | Replaced by `genechat init` with contig auto-fix |
| `scripts/setup_giab.sh` | Dead code (old shell version) |
| `tests/test_setup_giab.py` | Tests for deleted script |

### Tests

| File | Change |
|------|--------|
| `tests/conftest.py` | Multi-genome fixtures (two test VCFs with different genotypes) |
| `tests/test_config.py` | Test `[genomes.*]` parsing, backward compat with `[genome]` |
| `tests/test_cli.py` | Test `--label` flag for init/add, multi-genome status output |
| `tests/test_tools/test_query_variant.py` | Test genome selection, paired output |
| `tests/test_tools/test_query_gene.py` | Test paired gene query |
| `tests/test_tools/test_query_pgx.py` | Test paired PGx comparison |

### Documentation to revise

| File | What to update |
|------|----------------|
| `README.md` | Add "Don't have your genome sequenced?" section, quickstart (show `--label`), architecture diagram (multiple genomes), config format, simplify e2e instructions, remove `setup_giab.py` references |
| `CLAUDE.md` | Update config format in Phase 1, update Architecture diagram, update Core Use Cases to include paired analysis, update config.py description in Phase 2, update repo structure (remove `setup_giab.py`, `rebuild_database.py`) |
| `config.toml.example` | Replace `[genome]` with `[genomes.personal]` example, add commented-out second genome |
| `claude_mcp_config.json.example` | Show `GENECHAT_GENOME` env var option |
| `docs/annotation-updates.md` | Note that annotate/update operates on all registered genomes (or add `--genome` flag) |
| `.github/copilot-instructions.md` | Update project layout (config format change), add multi-genome as architectural context |
| `docs/security.md` | Note that multiple VCFs may be registered; same encryption recommendations apply to all |

## Contig Name Auto-Fix

Consumer WGS providers use `chr1`, `chr2`, etc. but some public datasets (GIAB, 1000 Genomes) use bare contig names (`1`, `2`). Currently `setup_giab.py` exists solely to handle this.

**Fix:** `genechat init` detects bare contig names in the input VCF and rewrites them with `chr` prefix before annotation. This uses `bcftools annotate --rename-chrs` (same mechanism as the dbSNP contig rename in `download.py`).

Detection: read the first few lines of the VCF header, check `##contig=<ID=...>` lines. If any use bare names (no `chr` prefix), apply the rename.

This eliminates `setup_giab.py` entirely. GIAB becomes just another VCF:

```bash
# Download GIAB VCF from NCBI FTP (~120 MB)
curl -O https://ftp-trace.ncbi.nlm.nih.gov/.../HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

# Standard init — auto-detects bare contigs, fixes them, annotates
genechat init HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz --label giab
```

## CLI Consolidation

All user/developer actions should be accessible via CLI. Remaining scripts that need CLI equivalents:

| Script | Proposed CLI | Who needs it |
|--------|-------------|-------------|
| `build_seed_data.py` | `genechat update --seeds` | Developer updating vendored data from upstream APIs |
| `build_gwas_db.py` | `genechat download --gwas` (download) + auto-build in `genechat init` | User wanting GWAS trait search |
| `setup_giab.py` | **Remove** — replaced by standard `genechat init` with contig auto-fix | Nobody |
| `setup_giab.sh` | **Remove** — dead code | Nobody |

Scripts that remain as internal implementation (called by other scripts, never directly by users):
- `build_lookup_db.py` — called by `build_seed_data.py` and `genechat init`
- `fetch_gene_coords.py`, `fetch_cpic_data.py`, `fetch_prs_data.py` — called by `build_seed_data.py`
- `generate_test_vcf.py` — called by pytest fixtures
- `overnight_parity_test.py` — developer testing tool

### `genechat update --seeds`

Fetches latest data from HGNC, CPIC, and PGS Catalog APIs, regenerates seed TSVs, and rebuilds lookup_tables.db. This is the CLI equivalent of `uv run python scripts/build_seed_data.py`. Requires network access (build-time only).

### `genechat download --gwas`

Downloads the GWAS Catalog and builds the gwas_associations table in lookup_tables.db. Currently a standalone script (`build_gwas_db.py`). Should integrate into the download subcommand alongside `--gnomad` and `--dbsnp`.

## GIAB / Demo Genome Documentation

The README quickstart currently has a separate "End-to-End Testing with GIAB NA12878" section aimed at developers. Replace with a user-friendly section earlier in the README:

```markdown
### Don't have your genome sequenced?

You can explore GeneChat using the [GIAB NA12878](https://www.nist.gov/programs-projects/genome-bottle)
benchmark genome — a well-characterized reference sample with ~3.7M variants:

\`\`\`bash
# Download the benchmark VCF (~120 MB)
curl -L -O https://ftp-trace.ncbi.nlm.nih.gov/giab/ftp/release/NA12878_HG001/NISTv4.2.1/GRCh38/HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz

# Initialize (auto-fixes contig names, downloads references, annotates)
uv run genechat init HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz --label giab
\`\`\`

Then ask Claude questions just like you would with your own genome.
```

The existing e2e test section in "Development / Testing" simplifies to:

```markdown
### End-to-End Testing with GIAB NA12878

Optional e2e tests against the GIAB benchmark genome:

\`\`\`bash
# Download and init GIAB (see "Don't have your genome sequenced?" above)
export GENECHAT_GIAB_VCF=./HG001_GRCh38_1_22_v4.2.1_benchmark.vcf.gz
uv run pytest tests/e2e/ -v
\`\`\`

E2e tests are automatically skipped when `GENECHAT_GIAB_VCF` is not set.
```

## Implementation Order

1. **Contig auto-fix** — detect bare contig names in `genechat init`, apply `bcftools annotate --rename-chrs`
2. **Config layer** — `AppConfig.genomes` dict, backward compat, `write_config()` with label
3. **Server + engine dict** — build `engines: dict[str, VCFEngine]` from config
4. **Tool interface change** — `register_all(mcp, engines, db, config)`, add `resolve_engine()` helper
5. **Single-genome tools** — add optional `genome` param to all tools (no paired logic yet)
6. **Paired queries** — add `genome2` param to supported tools, side-by-side formatting
7. **CLI consolidation** — `--label` for init/add, `update --seeds`, `download --gwas`, multi-genome status
8. **Remove setup_giab.py** — delete script and tests, update e2e conftest
9. **Annotate/update** — decide whether to operate on all genomes or require `--genome` flag
10. **Tests** — multi-genome fixtures, config parsing, contig auto-fix, paired tool output
11. **Documentation** — README (demo genome section, quickstart, architecture), CLAUDE.md, config examples, copilot instructions

## Verification

- `uv run pytest -x` passes with multi-genome fixtures
- `uv run ruff check . && uv run ruff format --check .` clean
- Single-genome backward compat: existing `[genome]` config works unchanged
- `GENECHAT_VCF` env var still works as single-genome shortcut
- Contig auto-fix: a VCF with bare contig names (like GIAB) is correctly initialized
- Paired query: two test VCFs with different genotypes at known variants produce side-by-side output
- `genechat init <vcf> --label giab` creates `[genomes.giab]` section
- `genechat status` lists all registered genomes
- `genechat update --seeds` fetches from APIs and rebuilds lookup_tables.db
- `genechat download --gwas` downloads GWAS Catalog and builds the table
- `setup_giab.py` is deleted; e2e tests use standard `genechat init` workflow
- Tool descriptions (visible to LLM) clearly explain the `genome` and `genome2` parameters
- README has a "Don't have your genome sequenced?" section with GIAB download + init instructions
