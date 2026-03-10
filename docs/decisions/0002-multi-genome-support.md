---
status: accepted
date: 2026-03-09
---

# Support multiple named genomes via config sections and per-genome engines

## Context and Problem Statement

GeneChat supported a single genome per server instance. This prevented paired analysis (e.g., carrier screening for couples) and made it impossible to run end-to-end tests against a reference genome (GIAB) alongside a personal genome without swapping configs.

## Considered Options

1. **Multiple server instances** -- Run separate GeneChat servers per genome. Simple but prevents paired queries and complicates MCP client config.
2. **Config switching via env var** -- `GENECHAT_GENOME=giab` selects which single genome to load. No paired analysis possible.
3. **Named genome sections with a dict of engines** -- Replace `[genome]` with `[genomes.<label>]` config sections, load all genomes at startup into `engines: dict[str, VCFEngine]`, add optional `genome`/`genome2` parameters to tools.

## Decision Outcome

Chosen option: "Named genome sections with a dict of engines", because it enables paired carrier screening, side-by-side comparison, and concurrent test + personal genomes in a single server instance.

### Consequences

- Good, because paired queries (carrier screening, risk comparison) work natively
- Good, because GIAB test genome can coexist with personal genome -- no config swapping
- Good, because backward compatible -- existing `[genome]` config is treated as `[genomes.default]`
- Bad, because every tool gains an optional `genome` parameter, adding interface complexity
- Bad, because server startup loads all genomes, increasing memory usage proportionally

## More Information

Implemented in PR #27. Original planning doc preserved in git history at `docs/multi-genome-plan.md`.
