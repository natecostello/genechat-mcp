---
status: accepted
date: 2026-03-09
---

# Make GeneChat installable via pip and uv tool install

## Context and Problem Statement

GeneChat required `git clone` + `uv sync` because the lookup database was gitignored and built at install time from seed TSVs. Users couldn't `pip install` or `uv tool install` the package -- the DB wouldn't be in the wheel, and the auto-build fallback required a source checkout.

## Considered Options

1. **Hatchling build hooks** -- Generate `lookup_tables.db` during wheel build. Adds build-time complexity and requires the seed TSVs to be available in the build environment.
2. **Commit the seed-only DB to git** -- The seed-only DB is ~1.7 MB, changes infrequently, and contains no user data. Ship it in the wheel via `force-include`.
3. **Post-install script** -- Run DB generation after `pip install`. Unreliable across package managers and environments.

## Decision Outcome

Chosen option: "Commit the seed-only DB to git", because it is simple, reliable, and the 1.7 MB size is acceptable for a wheel. GWAS data (~306 MB) is kept separate as a runtime download via `genechat install --gwas`, stored in the user's data directory (`~/.local/share/genechat/`).

### Consequences

- Good, because `uv tool install` and `pip install` work without any post-install steps
- Good, because GWAS separation keeps the wheel under 2 MB
- Good, because `importlib.resources` provides a clean path to the bundled DB in both source and installed modes
- Bad, because the DB file is tracked in git -- must be rebuilt and recommitted when seed data changes
- Bad, because two separate databases (lookup_tables.db + gwas.db) adds operational complexity

## More Information

Implemented in PR #28. Original planning doc preserved in git history at `docs/pip-install-plan.md`.
