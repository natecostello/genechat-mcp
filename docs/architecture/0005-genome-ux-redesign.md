---
status: accepted
date: 2026-03-11
decision-makers: natecostello
related ADRs:
  - [0002-multi-genome-support](0002-multi-genome-support.md)
  - [0004-cli-guidelines-alignment](0004-cli-guidelines-alignment.md)
---

# Genome UX Redesign

## Context and Problem Statement

The multi-genome CLI and MCP tool UX has several issues that become apparent as
users register more than one genome:

1. **Silent default genome** -- Commands operate on a "primary" genome without
   confirmation. Users with multiple genomes don't know which one they're
   affecting.
2. **State-dependent behavior** -- Commands work one way with one genome and
   differently with two, violating the principle of least astonishment.
3. **`annotate` overlaps with `status`** -- `genechat annotate` (no flags)
   displays annotation status, duplicating `genechat status`.
4. **`update` conflates unrelated concerns** -- Mixes genome-independent
   reference freshness with per-genome annotation state.
5. **MCP tools silently pick defaults** -- The LLM has no tool to discover
   available genomes before querying.

## Decision Drivers

- Explicit is better than implicit -- always tell the user which genome is being
  operated on
- Consistent behavior regardless of state -- same command, same behavior whether
  1 or 5 genomes registered
- Commands are verbs or queries, not both -- `annotate` is an action, `status`
  is a query
- The LLM should discover, not assume -- provide tools to list genomes

## Considered Options

1. **Keep `default_genome` with stricter messaging** -- add confirmation prompts
2. **Remove `default_genome`, require explicit genome selection** -- this ADR
3. **Auto-select most recently used genome** -- implicit but less surprising

## Decision Outcome

Chosen option: **2. Remove `default_genome`, require explicit genome selection**

Key changes:
- Remove `default_genome` field from AppConfig
- Remove `GENECHAT_VCF` and `GENECHAT_GENOME` env vars
- Single genome = auto-select (obvious), multiple = require `--genome`
- Drop `update` command (absorbed into `status`, `annotate --stale`, `install --seeds`)
- Add `list_genomes` MCP tool for LLM genome discovery
- Add rsID probe guard to avoid unnecessary 20 GB dbSNP downloads
- Redesign `status` output: installed databases, per-genome layers, annotation caches

**Implementation plan:** `docs/plans/genome-ux-redesign.md` (see git history after
plan file is removed post-merge).

### CLI Command Model After Redesign

| Command | Role | Genome-scoped? |
|---------|------|---------------|
| `init <vcf>` | First-time setup | Creates one genome |
| `add <vcf>` | Register a VCF | Creates one genome |
| `annotate` | Add/refresh annotation layers | Yes (`--genome` required) |
| `install` | Genome-independent databases (GWAS, seeds) | No |
| `status` | Show everything | No (shows all) |
| `serve` | Start MCP server | No |

Dropped: `update` (absorbed into `status`, `annotate --stale`, `install --seeds`).

### Consequences

- **Good:** Consistent behavior regardless of genome count. No more silent
  defaults. LLM can discover genomes explicitly.
- **Good:** `status` becomes the single "what's my state?" command with freshness
  checking. No more separate `update` that only checks 1 of 4 sources.
- **Good:** rsID probe guard prevents wasted 20 GB downloads for VCFs that
  already have rsIDs.
- **Bad:** Breaking change for users with existing `default_genome` in config
  (mitigated by legacy migration at load time).
- **Bad:** Scripts using `genechat update` will need updating.

## Confirmation

- All 280 tests pass after changes
- `genechat update` returns argparse error (command removed)
- `genechat annotate` without `--genome` shows usage with available genomes
- `genechat status` shows three-section output
- `list_genomes` MCP tool returns genome list

## More Information

- PR that implemented this decision: (to be filled after PR is created)
