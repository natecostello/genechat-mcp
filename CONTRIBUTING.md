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

## Seed Data

Don't hand-edit TSVs in `data/seed/`. Run `uv run python scripts/build_seed_data.py` to fetch from upstream APIs and rebuild.
