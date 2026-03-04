# Skills Subsystem

## Purpose

The skills directory provides reusable agent instructions as Markdown documents.
Each skill is a self-contained directory with a SKILL.md frontmatter file that
Claude Code loads automatically based on keyword matching in the `description`
field. Skills encode proven techniques, processes, and domain expertise that
agents apply during specific task types (brainstorming, planning, testing, etc.).

The key design decision: skills are documentation-as-code, version-controlled
alongside the project, and tested via the same TDD methodology they prescribe
(see `writing-skills/SKILL.md`).

## Core Mechanism

Claude Code discovers skills by scanning `.claude/skills/*/SKILL.md` for YAML
frontmatter. The `name` field maps to `/skill-name` invocation, and the
`description` field drives automatic keyword-based triggering.

**Skill loading flow:**
1. User invokes `/skill-name` or triggers via keyword match in conversation
2. Claude Code reads the skill's `SKILL.md` and any referenced support files
3. Agent follows the skill's checklist/process, using referenced prompts and
   templates as needed

**Key files:**
- `UPSTREAM-superpowers.md` — Tracks provenance and sync status for skills
  originating from [obra/superpowers](https://github.com/obra/superpowers)
- `*/SKILL.md` — Entry point for each skill (YAML frontmatter + Markdown body)

## Public Interface

| Export | Used By | Contract |
|---|---|---|
| YAML frontmatter `name` | Claude Code skill router | Must be unique, lowercase, hyphenated |
| YAML frontmatter `description` | Claude Code keyword matcher | Must contain trigger keywords |
| `/skill-name` invocation | Users and other skills | Must be stable across sessions |
| Cross-skill references | Skills referencing each other | Use skill name, not file path |

## Invariants

| ID | Invariant | Why It Matters |
|---|---|---|
| INV-1 | Every skill directory contains exactly one `SKILL.md` with valid YAML frontmatter (`name` + `description`) | Claude Code cannot discover or load skills without frontmatter |
| INV-2 | Skill names are unique across all `SKILL.md` files | Duplicate names cause routing ambiguity |
| INV-3 | Every tracked skill directory has a negated gitignore entry (`!.claude/skills/<name>/`) | Without the negation, git ignores the skill due to the `.claude/skills/*` blanket rule |
| INV-4 | Skills originating from upstream have an entry in `UPSTREAM-superpowers.md` with correct sync status | Agents modifying upstream-derived skills must know divergence status to avoid clobbering upstream changes |
| INV-5 | Skills that reference other skills use the skill name (not file path) in their Integration section | Skill directories may move; names are the stable identifier |
| INV-6 | Support files (prompts, templates, examples) live inside the skill's own directory | Skills must be self-contained — an agent loads one directory |

## Failure Modes

| ID | Symptom | Cause | Fix |
|---|---|---|---|
| FAIL-1 | Skill not discovered by Claude Code | Missing or malformed YAML frontmatter in SKILL.md | Add `---` fenced frontmatter with `name` and `description` fields |
| FAIL-2 | Wrong skill triggered for a task | Overly broad keywords in `description` field | Narrow the description; use specific trigger phrases |
| FAIL-3 | Skill changes lost after git operations | Missing negated gitignore entry for new skill directory | Add `!.claude/skills/<name>/` to `.gitignore` |
| FAIL-4 | Upstream sync clobbers local customizations | Skill marked "identical" in UPSTREAM-superpowers.md but has local changes | Update status to "diverged" with notes on what differs |
| FAIL-5 | Skill references broken after rename | Cross-references use file paths instead of skill names | Update references to use `/skill-name` form |

## Testing

Skills are tested via the TDD methodology defined in `writing-skills/SKILL.md`:
pressure scenarios run against subagents with and without the skill loaded.

```bash
# No automated test suite — skills are validated via subagent pressure testing
# See writing-skills/testing-skills-with-subagents.md for the process
```

### Coverage

| Spec Item | Test | Description |
|---|---|---|
| INV-1 | Manual: verify frontmatter parses | Each new skill is checked during `/writing-skills` process |
| INV-2 | Manual: grep for duplicate names | Check `grep -r '^name:' .claude/skills/*/SKILL.md` for duplicates |
| INV-3 | Manual: verify gitignore entry | Part of `/codify-subsystem` and PR review checklist |
| INV-4 | Manual: check UPSTREAM-superpowers.md | Review during upstream sync |
| FAIL-1 | Subagent test: skill discovery | Pressure test from `writing-skills/testing-skills-with-subagents.md` |
| FAIL-2 | Subagent test: keyword specificity | Pressure test with ambiguous task description |

## Dependencies

| Dependency | Type | SPEC.md Path |
|---|---|---|
| Claude Code skill router | external | N/A — built into Claude Code runtime |
| obra/superpowers | external | N/A — upstream repo, tracked in UPSTREAM-superpowers.md |
| docs/spec-template.md | internal | N/A — template reference, not a subsystem |
