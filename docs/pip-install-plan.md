# Plan: Make GeneChat Installable via `uv tool install` / `pip install`

## Problem Summary

Currently, `genechat` requires `git clone` + `uv sync` because:

1. **`lookup_tables.db` is not in the wheel.** It is gitignored (`*.db`) and built at install time from seed TSVs.
2. **`src/genechat/data/` has no `__init__.py`**, so hatchling does not treat it as a subpackage.
3. **`_ensure_lookup_db()`** tries to find a source checkout to auto-build the DB. In pip-installed mode, it fails with an error.
4. **GWAS Catalog** is a separate manual `scripts/build_gwas_db.py` step, not integrated into CLI subcommands.
5. **`rebuild_database` MCP tool** shells out to `scripts/build_lookup_db.py` via subprocess, which only exists in a source checkout.
6. **README quickstart and MCP config example** assume clone-based workflow.

## Size Constraints

| Component | Size |
|-----------|------|
| Seed TSVs (genes, pgx, prs) | 1.4 MB |
| lookup_tables.db **without** GWAS | ~1.7 MB |
| lookup_tables.db **with** GWAS | ~306 MB |
| GWAS Catalog zip download | ~58 MB |

The GWAS table (1M+ rows) dominates DB size. Including 306 MB in a wheel is unacceptable. GWAS data must remain a runtime download.

## Design Decisions

### Decision 1: Commit the seed-only DB to git

**Chosen over** build hooks. The seed-only DB is ~1.7 MB, changes infrequently (only when CPIC/HGNC/PGS data is refreshed), and contains no user data. Committing it is simpler and more reliable than hatchling build hooks.

### Decision 2: Split GWAS into a separate DB file

**Current state**: One `lookup_tables.db` containing everything (seed tables + GWAS).

**New state**: Two separate databases:
- `lookup_tables.db` — seed tables only (genes, pgx_drugs, pgx_variants, prs_weights). ~1.7 MB. Shipped in the wheel.
- `gwas.db` — GWAS associations table only. ~306 MB. Built at runtime by `genechat install --gwas`. Stored in `~/.local/share/genechat/gwas.db`.

GWAS data is conceptually a reference database (like ClinVar/gnomAD), not seed data.

---

## Implementation Items

### Item 1: Create `__init__.py` for the data subpackage

**File**: `src/genechat/data/__init__.py`

Create an empty `__init__.py` so hatchling treats `src/genechat/data/` as a subpackage and `importlib.resources` can discover its contents.

**Verification**: `python3 -c "from importlib.resources import files; print(list(files('genechat.data').iterdir()))"` shows directory contents.

---

### Item 2: Build and commit a seed-only `lookup_tables.db`

**Actions**:
1. Run `uv run python scripts/build_lookup_db.py` to produce `src/genechat/data/lookup_tables.db` (~1.7 MB).
2. Update `.gitignore`: remove the blanket `*.db` rule. Replace with targeted ignores that allow `src/genechat/data/lookup_tables.db` to be tracked while excluding `*.patch.db`, `gwas.db`, and other generated DBs.
3. Add `.gitattributes` entry: `src/genechat/data/lookup_tables.db binary` to prevent diff noise.
4. Commit `src/genechat/data/lookup_tables.db` to git.

**Updated `.gitignore` lines**:
```
# Remove:
*.db

# Add:
*.patch.db
gwas.db
data/gwas_catalog/
```

**Verification**: `git status` shows `src/genechat/data/lookup_tables.db` as tracked (~1.7 MB). `sqlite3 src/genechat/data/lookup_tables.db "SELECT name FROM sqlite_master WHERE type='table'"` returns exactly `genes`, `pgx_drugs`, `pgx_variants`, `prs_weights`.

---

### Item 3: Fix `pyproject.toml` packaging

**File**: `pyproject.toml`

**Changes**:
1. Remove the `[tool.hatch.build.targets.wheel.shared-data]` section (installs files outside the package, wrong for `importlib.resources`).
2. Add `force-include` to ensure the DB file ships in the wheel:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/genechat"]

[tool.hatch.build.targets.wheel.force-include]
"src/genechat/data/lookup_tables.db" = "genechat/data/lookup_tables.db"
```

**Verification**: `uv build --wheel && python3 -m zipfile -l dist/genechat_mcp-*.whl | grep lookup_tables` shows `genechat/data/lookup_tables.db` in the wheel. Wheel size is ~1.8 MB, not 300+ MB.

---

### Item 4: Simplify `_ensure_lookup_db()` in `cli.py`

**File**: `src/genechat/cli.py` (lines ~111-160)

The success path (`if db_path.exists(): return True`) already handles installed mode. Keep the source-checkout fallback for developers. Update the error message for installed mode:

```
"The built-in lookup database should have been installed with the package.
Try reinstalling: uv tool install genechat-mcp"
```

**Verification**: After `uv tool install .`, `genechat init /path/to/vcf` does not fail at the lookup DB check.

---

### Item 5: Create `src/genechat/gwas.py` module

**New file**: `src/genechat/gwas.py`

Extract the GWAS build logic from `scripts/build_gwas_db.py` into a proper package module:

- `download_gwas_catalog(dest_dir: Path) -> Path` — downloads the zip from EBI FTP
- `build_gwas_db(zip_path: Path, db_path: Path) -> int` — processes zip into SQLite, returns row count

`scripts/build_gwas_db.py` becomes a thin wrapper that imports from `genechat.gwas`.

**Verification**: `from genechat.gwas import download_gwas_catalog, build_gwas_db` works. Script still works: `uv run python scripts/build_gwas_db.py`.

---

### Item 6: Add `genechat install --gwas` to CLI

**File**: `src/genechat/cli.py`

**Changes**:
1. Add `--gwas` flag to the `download` subcommand parser.
2. Add to `_run_download()`:
   ```python
   if args.gwas or download_all:
       _download_and_build_gwas()
   ```
3. Implement `_download_and_build_gwas()` using the `genechat.gwas` module. Target path: `~/.local/share/genechat/gwas.db`.

**Verification**: `genechat install --gwas` downloads the GWAS catalog and builds `~/.local/share/genechat/gwas.db`. `genechat install --all` includes GWAS.

---

### Item 7: Add `gwas_db` config field and separate GWAS DB support

**Files**: `src/genechat/config.py`, `src/genechat/lookup.py`

**config.py changes**:
1. Add `gwas_db: str = ""` to `DatabasesConfig`.
2. Add a method to resolve the GWAS DB path (default: `~/.local/share/genechat/gwas.db`).

**lookup.py changes**:
1. After opening the main connection, check if the GWAS DB exists. If so, `ATTACH DATABASE` it:
   ```python
   self._conn.execute("ATTACH DATABASE ? AS gwas", (gwas_path,))
   ```
2. Update `has_gwas_table()` to check the attached DB.
3. Update `search_gwas()` and `gwas_traits_for_gene()` to prefix table references with `gwas.` when attached.

**Verification**:
- Without GWAS: `query_gwas` returns "GWAS Catalog not loaded" as before.
- With GWAS: `query_gwas` returns results from the attached `gwas.db`.

---

### Item 8: Update `rebuild_database` MCP tool

**File**: `src/genechat/tools/rebuild_database.py`

**Changes**:
- **Source checkout** (build script exists): Import and call `build_db()` directly instead of subprocess.
- **Installed mode**: Return a clear message: "Rebuild not available in installed mode. The built-in lookup database is pre-populated. For a full refresh, reinstall the package."

**Verification**: In installed mode, `rebuild_database` returns a helpful message, not a stack trace. In source checkout, it rebuilds successfully.

---

### Item 9: Update README quickstart

**File**: `README.md`

Show `uv tool install` as the primary install path. Keep clone-based instructions under "Development Setup":

```markdown
## Quickstart

### 1. Install GeneChat
uv tool install genechat-mcp

### 2. Install annotation tools
brew install bcftools brewsci/bio/snpeff

### 3. Initialize
genechat init /path/to/your/raw.vcf.gz

### 4. Start asking questions
Open Claude and ask about your genetics.

## Development Setup
git clone ... && cd genechat-mcp && uv sync
```

**Verification**: README shows `uv tool install genechat-mcp` as primary method.

---

### Item 10: Update `claude_mcp_config.json.example`

**File**: `claude_mcp_config.json.example`

Show the simple installed-mode config:
```json
{
  "mcpServers": {
    "genechat": {
      "command": "genechat"
    }
  }
}
```

Keep a comment or note about the development-mode config with `--directory`.

**Verification**: After `uv tool install .`, `{"command": "genechat"}` starts the server.

---

### Item 11: Add GWAS hint to `genechat init` output

**File**: `src/genechat/cli.py`

After init completes, print:
```
Optional: Enable GWAS trait search:
  genechat install --gwas
```

**Verification**: `genechat init` output includes GWAS download hint.

---

### Item 12: Add `gwas_installed()` and update `genechat status`

**File**: `src/genechat/download.py`, `src/genechat/cli.py`

Add `gwas_installed()` helper. Update `_run_status()` to show GWAS status.

**Verification**: `genechat status` shows "GWAS: installed" or "GWAS: not installed".

---

### Item 13: Add packaging tests

**File**: `tests/test_packaging.py`

```python
def test_lookup_db_accessible_via_importlib():
    from importlib import resources
    ref = resources.files("genechat") / "data" / "lookup_tables.db"
    with resources.as_file(ref) as p:
        assert p.exists()
        assert p.stat().st_size > 0

def test_default_db_path_resolves():
    from genechat.config import _default_db_path
    path = _default_db_path()
    assert path.exists()
    assert path.name == "lookup_tables.db"
```

**Verification**: `uv run pytest tests/test_packaging.py -v` passes.

---

### Item 14: End-to-end verification

Manual test steps:

```bash
# Build the wheel
uv build --wheel

# Install into isolated environment
uv tool install dist/genechat_mcp-*.whl

# Verify command exists
which genechat

# Verify lookup DB is accessible
genechat status

# Full init cycle (requires VCF + annotation tools)
genechat init /path/to/test.vcf.gz

# Verify MCP server starts
genechat serve  # Ctrl+C to stop

# Clean up
uv tool uninstall genechat-mcp
```

---

## Implementation Order

```
Phase A: Package data (Items 1-3)
  Item 1: data/__init__.py
  Item 2: commit seed-only lookup_tables.db + .gitignore
  Item 3: pyproject.toml fix

Phase B: GWAS separation (Items 5-7)
  Item 5: genechat/gwas.py module
  Item 6: CLI --gwas flag
  Item 7: config + lookup.py ATTACH support

Phase C: Cleanup (Items 4, 8)
  Item 4: simplify _ensure_lookup_db()
  Item 8: rebuild_database tool update

Phase D: Docs and polish (Items 9-12)
  Item 9:  README rewrite
  Item 10: MCP config example
  Item 11: init output GWAS hint
  Item 12: gwas_installed() + status

Phase E: Testing (Items 13-14)
  Item 13: packaging tests
  Item 14: end-to-end verification
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Committing binary DB to git | At 1.7 MB it's negligible. Use `.gitattributes binary`. Only regenerate when seed data changes. |
| `importlib.resources` breaks for zip packages | Use `importlib.resources.files(...).joinpath(...).as_file()` to obtain a real filesystem `Path` even when the package is loaded from a zip importer. |
| GWAS `ATTACH DATABASE` needs write access | Open GWAS DB in read-only mode via URI: `file:path?mode=ro`. |
| `uv tool install` isolated environments | pysam ships binary wheels on supported platforms. Same as today. |
