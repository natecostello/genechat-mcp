# Contributing to GeneChat

## Development Setup

```bash
git clone https://github.com/natecostello/genechat-mcp.git
cd genechat-mcp
uv sync --extra dev
```

## Running Tests

```bash
uv run pytest -x
uv run ruff check . && uv run ruff format --check .
```

## PR Process

1. Branch from main
2. Make changes, add tests
3. Ensure `uv run pytest -x` and `uv run ruff check .` pass
4. Submit PR -- Copilot review is requested automatically
5. Address review comments before merge

## Code Style

- Ruff for linting and formatting (config in pyproject.toml)
- Type hints on public APIs
- Medical disclaimers on clinical tool output

## Architecture Decisions

Significant design decisions are recorded as [Architecture Decision Records (ADRs)](docs/architecture/) using the [MADR 4.0](https://adr.github.io/madr/) format.

**When to write an ADR:** If your change affects data flow between components, the MCP tool interface, the annotation pipeline architecture, or module boundaries — write an ADR. See the full criteria in `CLAUDE.md`.

**Process:** Create a new ADR in `docs/architecture/` using the next sequential number. Set status to `proposed` until the implementing PR merges, then update to `accepted`. Reference the implementing PR in the "More Information" section.

## Seed Data

Don't hand-edit TSVs in `data/seed/`. They are auto-generated from upstream APIs (HGNC, Ensembl, CPIC, PGS Catalog). To refresh:

```bash
genechat install --seeds        # pip-installed
uv run python scripts/build_seed_data.py  # source checkout
```
