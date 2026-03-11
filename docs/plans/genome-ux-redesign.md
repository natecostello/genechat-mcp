# Plan: Genome UX Redesign

## Problem Statement

The current CLI and MCP tool UX around genome selection has several issues:

1. **Silent default genome** — Commands operate on a "primary" genome without confirmation. Users with multiple genomes don't know which one they're affecting.
2. **State-dependent behavior** — A CLI that works one way with one genome and differently with two violates the principle of least astonishment. Adding a second genome silently changes how existing commands work.
3. **`annotate` overlaps with `status`** — `genechat annotate` (no flags) displays annotation status, duplicating `genechat status` but for a single genome.
4. **`status` references section is misleading** — ClinVar, SnpEff, gnomAD, and dbSNP are annotation caches downloaded during `annotate`, not standalone references. Only GWAS is a true installed reference. The current display conflates these.
5. **MCP tools silently pick a default genome** — `genome` parameter defaults to the primary genome. The LLM has no tool to discover available genomes before querying.
6. **`update` command conflates unrelated concerns** — Mixes genome-independent reference freshness checks (ClinVar HTTP HEAD) with per-genome annotation state (gnomAD/dbSNP in patch.db). Shows "not installed" for sources that are per-genome annotations, not installable references. Suggests "Apply updates" when there's nothing to apply. The brew model (`update` = check, `upgrade` = apply) doesn't fit because there's no index to refresh, only 1 of 4 sources has version detection, and `--apply` just calls `annotate` internally.

## Design Principles

- **Explicit is better than implicit** — Always tell the user which genome is being operated on
- **Consistent behavior regardless of state** — The same command should work the same way whether 1 or 5 genomes are registered
- **Commands are verbs or queries, not both** — `annotate` is an action, `status` is a query. Don't mix.
- **The LLM should discover, not assume** — Provide tools for the LLM to list genomes and let the user choose

## Changes

### 1. Remove `default_genome` concept

**Config changes:**
- Remove `default_genome` field from `AppConfig`
- Remove `GENECHAT_VCF` env var support (creates a half-working genome with no patch.db — `init` is the only way to register a genome)
- Remove `GENECHAT_GENOME` env var support
- Remove `genome` legacy field (complete the migration to `genomes` dict)
- Keep backward-compat migration in `model_post_init` for old configs (migrate `[genome]` → `[genomes.default]`), but don't set a default

**CLI changes:**
- `--genome <label>` is required on per-genome commands (`annotate`) when more than one genome is registered; when exactly one genome is registered, that genome is used by default but can still be specified explicitly with `--genome`
- `--genome` accepts one or more labels, plus the keyword `all` as shorthand for all registered genomes (useful for `annotate --stale --genome all`)
- `genechat init` still assigns a label via `--label` or filename, but doesn't mark it as primary
- `genechat status` shows all genomes (no change needed — it already does)

**Behavior:** In a single-genome setup, `genechat annotate --clinvar` without `--genome` runs against the only registered genome. When multiple genomes are registered, omitting `--genome` prints usage help with the available labels so the user can choose explicitly.

### 2. Redesign `genechat annotate` (no flags) + add `--stale`

**Current:** Shows annotation status for the default genome (duplicates `status`).

**New:** Displays usage guidance — available actions and genomes, directs to `status` for details.

```
Usage: genechat annotate --genome <label> [--clinvar | --snpeff | --gnomad | --dbsnp | --stale | --all]

Available genomes:
  personal
  partner

Run 'genechat status' to see current annotation state for each genome.
```

This applies for any missing required info:
- No `--genome` → show available genomes
- `--genome` but no action flags → show available actions for that genome
- Both provided → run the annotation

**New `--stale` flag:** Re-annotate whichever layers have a newer reference available for the specified genome(s). This absorbs the old `update --apply` behavior. Uses the same version detection as `status` (currently ClinVar HTTP HEAD; expandable). Example: `genechat annotate --stale --genome all`.

### 3. Redesign `genechat status` — absorb freshness checking from `update`

**Current:**
```
References: /Users/.../references
  ClinVar:  installed
  SnpEff:   available
  gnomAD:   not installed — genechat annotate --gnomad
  dbSNP:    not installed — genechat annotate --dbsnp
  GWAS:     not installed — genechat install --gwas
```

**Problems:**
- ClinVar/SnpEff/dbSNP are annotation caches, not standalone references. gnomAD is never persistently installed. The current display conflates these.
- Freshness checking (is ClinVar newer upstream?) lives in `update` but belongs here since `status` is the "what's my state?" command.

**New:** Three sections — installed databases, per-genome annotation state with freshness, and annotation caches:

```
Installed databases:
  GWAS:           installed (2026-03-01, 1.2M associations)
  Lookup tables:  installed (2026-03-08, CPIC 2026-02, PGS v2024-09)

Genomes:
  personal:
    VCF:      /path/to/personal.vcf.gz
    Patch DB: /path/to/personal/patch.db (42 MB)
    Layers:   snpeff (GRCh38.86), clinvar (2026-03-02 — update available: 2026-04-01),
              gnomad (v4.1), dbsnp (b156)

  partner:
    VCF:      /path/to/partner.vcf.gz
    Patch DB: /path/to/partner/patch.db (38 MB)
    Layers:   snpeff (GRCh38.86), clinvar (2026-03-02 — update available: 2026-04-01)

Annotation caches: /Users/.../references
  ClinVar:  cached (2026-03-02)
  SnpEff:   cached (GRCh38.86)
  dbSNP:    cached
  gnomAD:   not cached (downloaded per-chromosome during annotation, not retained)
```

Key changes:
- Per-genome annotation layers shown with version and freshness indicators
- "update available" inline where we can detect newer upstream versions (currently ClinVar; expandable)
- Installed databases section shows genome-independent databases from `genechat install`
- Annotation caches section explains intermediate reference files
- Freshness checking (HTTP HEAD for ClinVar, etc.) absorbed from the old `update` command

### 4. Add `list_genomes` MCP tool

**Purpose:** Let the LLM discover available genomes so it can ask the user which one to query, rather than silently picking a default.

**Tool signature:**
```python
def list_genomes() -> str:
    """List all registered genomes with their labels and basic info."""
```

**Returns:** A formatted list of genome labels with VCF path, annotation state (has patch.db? which layers?), and whether the genome has been annotated.

**MCP server instructions update:** Change from "Always start with genome_summary" to "Always start with list_genomes to see available genomes, then use genome_summary for a detailed view of a specific genome."

**Tool behavior for `genome` parameter across all tools:**
- When only one genome is registered: `genome` parameter is optional (defaults to the only one). This is NOT state-dependent behavior — it's "there's only one option, so the answer is obvious." The key difference from today: the tool response always names the genome it used.
- When multiple genomes are registered: `genome` parameter is required. Omitting it returns an error listing available genomes.

### 5. Drop `update` command

**Current:** `update` checks for newer references, `update --apply` re-annotates stale layers, `update --seeds` rebuilds lookup_tables.db.

**Problem:** The brew model (`update` = refresh index, `upgrade` = apply) doesn't fit. There's no index to refresh — just an HTTP HEAD on one URL. `--apply` is just `annotate` for stale layers. `--seeds` is unrelated to reference updates.

**New:** Absorb each piece into the right command:

| Old command | New home | Rationale |
|-------------|----------|-----------|
| `update` (naked) | `status` | Freshness checking is a read-only query — belongs in the "what's my state?" command |
| `update --apply` | `annotate --stale` | Re-annotating is what `annotate` does; `--stale` auto-detects which layers need it |
| `update --seeds` | `install --seeds` | Seed data is a genome-independent database, same as GWAS |

The `update` subcommand is removed from the CLI. The `update.py` module stays (version checking logic) but is called by `status` and `annotate --stale` instead.

**Naked command behavior after this change:**

| Command | Without `--genome` | With `--genome` |
|---------|-------------------|-----------------|
| `status` | Shows all genomes + all databases + freshness | N/A (always shows all) |
| `annotate` | Lists available genomes + usage | Runs specified layers on specified genome(s) |
| `install` | Lists available databases + what's installed | N/A (genome-independent) |

### 6. `install --seeds` — make seed refresh user-facing

**Current:** Seed data (PGx guidelines, gene coords, PRS weights) is baked into `lookup_tables.db` in the wheel. Refreshing requires a source checkout and running `scripts/build_seed_data.py`.

**Problem:** Package releases are infrequent. CPIC updates PGx guidelines, PGS Catalog adds scores. Users should be able to refresh without upgrading the package. This is the same pattern as `install --gwas` — fetch external data, build a genome-independent database.

**New:** `genechat install --seeds` fetches from CPIC/HGNC/PGS Catalog APIs and rebuilds lookup_tables.db.

**Implementation:** Move the seed fetch/build logic from `scripts/` into the package (`src/genechat/seeds/` or similar) so it's available to pip-installed users. The scripts in `scripts/` become thin wrappers or are removed.

**`install` command after this change:**
```
genechat install [--gwas] [--seeds] [--all] [--force]
```

**`status` shows freshness for all installed databases:**
```
Installed databases:
  GWAS:           installed (2026-03-01, 1.2M associations)
  Lookup tables:  installed (2026-03-08, CPIC 2026-02, PGS v2024-09)
```

### 7. rsID probe guard on dbSNP download

**Problem:** `annotate --dbsnp` triggers a ~20 GB download + contig rename. If the VCF already has rsIDs (most consumer VCFs do), the download is completely wasted — `update_dbsnp_from_stream` only updates `WHERE rsid IS NULL`.

**New behavior:** Before downloading dbSNP, probe the existing patch.db for rsID coverage:

```python
# PatchDB method
def rsid_coverage(self, sample_size: int = 1000) -> tuple[int, int]:
    """Return (total, has_rsid) from a sample of annotations."""
```

- If >90% of sampled rows already have rsIDs: skip the download, print a message explaining why, suggest `--force` to override.
- Applies to `annotate --dbsnp`, `annotate --all`, and `init --dbsnp`.
- The probe runs after SnpEff (step 1), which is when VCF-native rsIDs are already in patch.db.
- `--force` flag overrides the guard for users who want dbSNP anyway (e.g., backfilling the remaining <10%).

**Where the logic lives:**
- `PatchDB.rsid_coverage()` — the probe query (patch.py)
- `cli.py` `_cmd_annotate()` — the decision to skip, between SnpEff completion and dbSNP download

### 8. Update `genechat init` completion message

**Current:** Shows MCP config + optional GWAS hint.

**New:** After the MCP config, show a "next steps" section:

```
=== Next Steps ===

Your genome 'personal' is ready. Here's what you can enhance:

  GWAS trait search (58 MB):     genechat install --gwas
  gnomAD smart filter (150 GB):  genechat annotate --genome personal --gnomad
  dbSNP rsID backfill:           [Not needed — your VCF already has rsIDs]
                                 OR [Recommended — your VCF lacks rsIDs]
                                     genechat annotate --genome personal --dbsnp

Run 'genechat status' to see your full setup.
```

The dbSNP recommendation requires a quick rsID probe: sample a few variants from the VCF and check if they have rsIDs. If most do, mark as not needed; if none do, recommend it.

## Files to Modify

| File | Changes |
|------|---------|
| `src/genechat/config.py` | Remove `default_genome`, remove `GENECHAT_VCF`/`GENECHAT_GENOME` env vars, remove legacy `genome` field, update `model_post_init` |
| `src/genechat/cli.py` | Drop `update` subcommand; require `--genome` on `annotate`; `--genome` accepts multiple labels + `all`; add `--stale` flag to `annotate`; redesign `annotate` no-flags output; redesign `status` to show per-genome layers + freshness + installed databases; add `--seeds` to `install`; update init completion message; dbSNP download guard |
| `src/genechat/patch.py` | Add `rsid_coverage()` method |
| `src/genechat/update.py` | Keep version-checking logic; remove `format_status_table` (absorbed by `status`); called by `status` and `annotate --stale` |
| `src/genechat/server.py` | Update instructions to reference `list_genomes`; update engine resolution |
| `src/genechat/tools/common.py` | Update `resolve_engine` — require `genome` when multiple registered; always name genome in response |
| `src/genechat/tools/list_genomes.py` | New file — `list_genomes` tool |
| `src/genechat/tools/__init__.py` | Register `list_genomes` |
| `src/genechat/seeds/` | New package — move seed fetch/build logic from `scripts/` into the installed package |
| `scripts/` | Thin wrappers or remove (logic moved to `src/genechat/seeds/`) |
| `tests/test_cli.py` | Update tests for new annotate behavior, status output, dropped update command |
| `tests/test_config.py` | Update tests — no default_genome |
| `tests/test_update.py` | Update — version checking still tested, but called from status/annotate |
| `tests/test_tools/` | Add `list_genomes` tests; update genome resolution tests |
| `README.md` | Update CLI commands table, multi-genome section, drop `update` references |
| `CLAUDE.md` | Update CLI docs, tool inventory, repo structure |

## Implementation Order

1. **Config changes** — Remove `default_genome`, remove env vars, update `model_post_init`, fix tests
2. **CLI: Drop `update` command** — Remove subcommand, keep `update.py` version-checking logic
3. **CLI: `annotate` redesign** — New no-flags behavior, require `--genome` (multi-label + `all`), add `--stale` flag
4. **CLI: `status` redesign** — Per-genome annotation layers + freshness, installed databases, annotation caches
5. **CLI: `install --seeds`** — Move seed fetch/build logic into package, add `--seeds` flag
6. **rsID probe guard** — `PatchDB.rsid_coverage()` + dbSNP download guard in `_cmd_annotate`
7. **MCP: `list_genomes` tool** — New tool + update server instructions
8. **MCP: `resolve_engine` update** — Require genome when multiple, always name genome used
9. **CLI: init completion message** — Next steps section with rsID probe result
10. **Documentation** — README, CLAUDE.md
11. **ADR-0005** — Document the UX redesign decisions (multi-genome contract, `update` removal, command roles)

## Resolved Questions

1. **`GENECHAT_VCF` env var** — Drop it. It creates a half-working genome (no patch.db) that can't do anything useful. `genechat init` is the only way to register a genome.
2. **`genechat update --apply` requires `--genome`** — Moot. `update` is being dropped. The behavior moves to `annotate --stale --genome <label>`, which accepts one or more labels plus `all`.
3. **ADR needed** — Yes, ADR-0005. This changes the multi-genome UX contract, drops a command, and redefines command roles.
4. **`update` command** — Drop it. The brew model doesn't fit (no index, 1/4 sources checkable, `--apply` duplicates `annotate`). Absorbed: freshness → `status`, `--apply` → `annotate --stale`, `--seeds` → `install --seeds`.
5. **Seed refresh** — User-facing via `install --seeds`. Seed data goes stale (CPIC updates PGx guidelines, PGS adds scores) and package releases are infrequent. Same pattern as `install --gwas`. Requires moving seed fetch/build logic from `scripts/` into the package.

## CLI Command Model After Redesign

| Command | Role | Genome-scoped? |
|---------|------|---------------|
| `init <vcf>` | First-time setup (register + annotate + install) | Creates one genome |
| `add <vcf>` | Register a VCF without annotation | Creates one genome |
| `annotate` | Add/refresh annotation layers in a genome's patch.db | Yes (`--genome` required) |
| `install` | Add/refresh genome-independent databases (GWAS, seeds) | No |
| `status` | Show everything: genomes, layers + freshness, installed databases | No (shows all) |
| `serve` | Start the MCP server | No |

Dropped: `update` (absorbed into `status`, `annotate --stale`, `install --seeds`).

## Verification

- `uv run pytest -x` passes
- `uv run ruff check . && uv run ruff format .` clean
- `GENECHAT_VCF` env var has no effect (no implicit genome creation)
- `genechat update` prints an error or unrecognized command (command removed)
- `genechat annotate` (no flags) prints usage with genome list
- `genechat annotate --clinvar` (no `--genome`) prints usage with genome list
- `genechat annotate --genome personal --clinvar` runs annotation
- `genechat annotate --genome personal --genome partner --clinvar` annotates both
- `genechat annotate --stale --genome all` re-annotates stale layers across all genomes
- `genechat annotate --genome personal --dbsnp` on a VCF with rsIDs prints "rsIDs already present, skipping" (and `--force` overrides)
- `genechat install --seeds` fetches from CPIC/HGNC/PGS APIs and rebuilds lookup_tables.db
- `genechat install --gwas` still works as before
- `genechat status` shows per-genome annotation layers with freshness indicators, installed databases, annotation caches
- `genechat init <vcf> --label test` shows next steps with rsID probe result
- MCP `list_genomes` tool returns genome list
- MCP tools with `genome=None` and multiple genomes return error listing available genomes
