---
status: accepted
date: 2026-03-09
related ADRs:
  - "[0001 Patch architecture](0001-patch-architecture.md) — each genome gets its own patch.db"
---

# Support multiple named genomes via config sections and per-genome engines

## Context and Problem Statement

GeneChat supported a single genome per server instance. This prevented paired analysis (e.g., carrier screening for couples) and made it impossible to run end-to-end tests against a reference genome (GIAB) alongside a personal genome without swapping configs.

## Decision Drivers

* Paired carrier screening requires querying two genomes in a single conversation
* GIAB reference genome must coexist with personal genomes for testing
* Backward compatibility with existing single-genome `[genome]` config sections

## Considered Options

* Multiple server instances
* Config switching via env var
* Named genome sections with a dict of engines

## Decision Outcome

Chosen option: "Named genome sections with a dict of engines", because it enables paired carrier screening, side-by-side comparison, and concurrent test + personal genomes in a single server instance.

Plan: `docs/multi-genome-plan.md` (created at `ddae793`, last version before deletion at `5b22dd7~1`)

### Consequences

* Good, because paired queries (carrier screening, risk comparison) work natively
* Good, because GIAB test genome can coexist with personal genome — no config swapping
* Good, because backward compatible — existing `[genome]` config is treated as `[genomes.default]`
* Bad, because every tool gains an optional `genome` parameter, adding interface complexity
* Bad, because server startup loads all genomes, increasing memory usage proportionally

### Confirmation

Multi-genome support is verified by the `test_config_multi` fixture and paired-query tests in the test suite.

## Pros and Cons of the Options

### Multiple server instances

Run separate GeneChat servers per genome, each configured independently.

* Good, because it is simple — no code changes to support multiple genomes
* Bad, because paired queries across genomes are impossible
* Bad, because MCP client config becomes complex (multiple server entries)

### Config switching via env var

`GENECHAT_GENOME=giab` selects which single genome to load at startup.

* Good, because it is a small change — env var selects config section
* Bad, because no paired analysis is possible — only one genome loaded at a time
* Bad, because switching requires restarting the server

### Named genome sections with a dict of engines

Replace `[genome]` with `[genomes.<label>]` config sections, load all genomes at startup into `engines: dict[str, VCFEngine]`, add optional `genome`/`genome2` parameters to tools.

* Good, because all genomes are available simultaneously
* Good, because paired queries work natively (pass `genome` and `genome2`)
* Good, because backward compatible — legacy `[genome]` auto-migrates to `[genomes.default]`
* Neutral, because env var `GENECHAT_GENOME` can still override the default label
* Bad, because every tool signature gains optional genome parameters
* Bad, because startup memory scales with number of configured genomes

## More Information

Implemented in PR #27 (merged 2026-03-09).
