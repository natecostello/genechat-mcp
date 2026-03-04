# Subsystem Specifications

> This manifest indexes all SPEC.md files in the project. Updated by the
> `/codify-subsystem` skill. Agents use this to discover specs for subsystems
> outside their immediate working directory.

## Cold-Tier Retrieval

This manifest serves as the cold-tier baseline for the three-tier context
architecture. Agents consult it when they need specs outside their immediate
working directory (warm tier) or the always-loaded CLAUDE.md (hot tier).

For projects with many subsystems, pair this manifest with
[local-rag](https://github.com/aihaysteve/local-rag) to enable semantic
retrieval over SPEC.md files. local-rag indexes Markdown documents and
provides an MCP retrieval service that agents can query by task description
rather than navigating the manifest manually.

## Index

| Subsystem | Spec Path | Summary |
|---|---|---|
| Skills | `.claude/skills/SPEC.md` | Reusable agent instructions as Markdown with YAML frontmatter |

## Cross-Cutting Concerns

| Concern | Spec Path | Subsystems Affected |
|---|---|---|
| *(none yet)* | | |
