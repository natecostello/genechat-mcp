# Upstream Skills: obra/superpowers

Several skills in this repo originate from [obra/superpowers](https://github.com/obra/superpowers), an open-source Claude Code plugin (MIT license). We track them as plain files in `.claude/skills/` rather than loading the plugin.

**Last synced to:** `e4a2375cb705ca5800f0833528ce36a3faf9017a` (2026-02-21)

## Status

| Skill | Status | Notes |
|-------|--------|-------|
| brainstorming | diverged | Upstream hard gates + our prior ideation check, UX evaluation, local working dir convention |
| dispatching-parallel-agents | identical | |
| executing-plans | diverged | Upstream batch model + our acceptance criteria step and agent team delegation |
| finishing-a-development-branch | identical | |
| receiving-code-review | identical | |
| requesting-code-review | diverged | PR-aware review flow: detects PR, posts findings, applies GitHub review actions by authorship |
| subagent-driven-development | diverged | Upstream per-task review flow + our parallel dispatch for independent tasks, context budget check, hidden coupling guard |
| systematic-debugging | identical | Minor: `superpowers:` prefix stripped in two cross-references |
| test-driven-development | identical | |
| using-git-worktrees | identical | Minor: reworded cross-refs in Integration section |
| using-superpowers | not tracked | Meta-skill for plugin discovery; redundant with native Claude Code skill loading |
| verification-before-completion | identical+ | Appended section: code-simplification pipeline integration |
| writing-plans | diverged | Task context budget (~50% of subagent window), self-contained tasks, dependency markers, acceptance criteria |
| writing-skills | identical | Minor: `superpowers:` prefix stripped |

**identical** — matches upstream (may have trivial prefix changes).
**identical+** — our additions appended at end; upstream content unchanged above.
**diverged** — structural differences throughout; requires manual merge on sync.

## Original UX design skills

These skills are original (not from obra/superpowers). They form a dependency chain rooted at `ux-design-agent`:

| Skill | Purpose |
|-------|---------|
| ux-design-agent | Entry point: requirements, user modeling, modality selection |
| design-principles | GUI modality: visual design patterns and polish |
| delegation-oversight | Agentic modality: human-AI handoff design |
| approval-confirmation | Sub-skill of delegation-oversight: informed consent UI |
| failure-choreography | Graceful failure: state preservation and human handoff |
| trust-calibration | Confidence framing and uncertainty acknowledgment |
| ux-writing | Interface copy: buttons, labels, errors, forms |

**Dependency graph:**
```
ux-design-agent
├── design-principles        [GUI modality]
├── delegation-oversight      [Agentic modality]
│   ├── approval-confirmation
│   │   ├── failure-choreography → trust-calibration
│   │   └── ux-writing
│   └── writing-plans         [already tracked above]
└── writing-plans             [already tracked above]
```

## Where and why we differ

Five skills diverge from upstream. Three share a theme:

**Context budget and parallelism** (executing-plans, writing-plans, subagent-driven-development) — Upstream's execution model is serial: one task at a time, fixed batches. We constrain task size to ~50% of a subagent's context window (so quality doesn't degrade as the agent works) and allow independent tasks to run in parallel. These changes are additive to upstream's structure — we preserve upstream's process flows and layer our constraints on top.

**PR integration** (requesting-code-review) — Upstream reviews locally only. We detect whether a PR exists, post review findings to it, and choose the appropriate GitHub review action (approve / request changes) based on whether the reviewer authored the PR.

**Process additions** (brainstorming) — Upstream's hard-gate structure (design before implementation) merged with our prior ideation check, UX design evaluation step, and local working directory convention.

## Namespace prefix

Upstream is packaged as a Claude Code plugin with a `superpowers:` namespace. Skills cross-reference each other as `superpowers:writing-plans`, etc. We load skills directly from `.claude/skills/`, so the prefix is stripped everywhere. Expect mechanical conflicts on cross-reference lines when syncing.

## How to sync

Be cautious — it is easy to introduce process bugs this way.

1. Clone upstream at the target commit

```sh
git clone --depth 1 https://github.com/obra/superpowers.git /tmp/superpowers
```

2. Diff a specific skill

```sh
diff -r /tmp/superpowers/skills/<name>/ .claude/skills/<name>/
```

3. For identical skills, copy directly

```sh
cp /tmp/superpowers/skills/<name>/SKILL.md .claude/skills/<name>/SKILL.md
```

4. For diverged skills, review diff and merge manually

5. Strip `superpowers:` prefix from any new cross-references

6. Update this file: change the commit SHA and update the status table
