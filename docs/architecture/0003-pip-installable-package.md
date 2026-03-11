---
status: accepted
date: 2026-03-09
related ADRs:
  - "[0001 Patch architecture](0001-patch-architecture.md) — patch.db is per-user, not shipped in the wheel"
---

# Make GeneChat installable via pip and uv tool install

## Context and Problem Statement

GeneChat required `git clone` + `uv sync` because the lookup database was gitignored and built at install time from seed TSVs. Users couldn't `pip install` or `uv tool install` the package — the DB wouldn't be in the wheel, and the auto-build fallback required a source checkout.

## Decision Drivers

* `uv tool install` and `pip install` must work without post-install steps
* The wheel must remain small (under 5 MB)
* GWAS data (~306 MB) must not be bundled in the wheel
* The solution must work in both source checkout and installed package modes

## Considered Options

* Hatchling build hooks
* Commit the seed-only DB to git
* Post-install script

## Decision Outcome

Chosen option: "Commit the seed-only DB to git", because it is simple, reliable, and the 1.7 MB size is acceptable for a wheel. GWAS data (~306 MB) is kept separate as a runtime download via `genechat install --gwas`, stored in the user's data directory (`~/.local/share/genechat/`).

Plan: `docs/pip-install-plan.md` (created at `8fc9894`, last version before deletion at `5b22dd7~1`)

### Consequences

* Good, because `uv tool install` and `pip install` work without any post-install steps
* Good, because GWAS separation keeps the wheel under 2 MB
* Good, because `importlib.resources` provides a clean path to the bundled DB in both source and installed modes
* Bad, because the DB file is tracked in git — must be rebuilt and recommitted when seed data changes
* Bad, because two separate databases (lookup_tables.db + gwas.db) adds operational complexity

### Confirmation

Package installability is verified by `tests/test_packaging.py` which checks that `importlib.resources` can locate the bundled lookup_tables.db.

## Pros and Cons of the Options

### Hatchling build hooks

Generate `lookup_tables.db` during wheel build using a custom Hatchling build hook.

* Good, because the DB is always up-to-date with the latest seed TSVs
* Bad, because it adds build-time complexity (custom hook code)
* Bad, because the seed TSVs and build scripts must be available in the build environment
* Bad, because it makes builds non-reproducible if API responses change

### Commit the seed-only DB to git

The seed-only DB is ~1.7 MB, changes infrequently, and contains no user data. Ship it in the wheel via `force-include` in pyproject.toml.

* Good, because installation is zero-config — the DB is already in the wheel
* Good, because builds are reproducible — the DB is version-controlled
* Neutral, because 1.7 MB added to git history is acceptable
* Bad, because seed data updates require rebuilding and recommitting the DB file

### Post-install script

Run DB generation after `pip install` completes.

* Good, because the wheel stays tiny (no DB bundled)
* Bad, because post-install scripts are unreliable across package managers (pip, pipx, uv)
* Bad, because the user needs network access during installation
* Bad, because it requires the seed TSVs or API access at install time

## More Information

Implemented in PR #28 (merged 2026-03-09).
