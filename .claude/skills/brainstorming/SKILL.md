---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. A todo list, a single-function utility, a config change — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but you MUST present it and get approval.

## Pre-flight Checks

Before exploring the project, verify the CONTRIBUTING.md workflow prerequisites. Both checks are **soft gates** — the user can always proceed anyway.

### 1a. Issue Check

Ask: "Which GitHub issue does this work address? (Enter issue number, URL, or 'none' to skip)"

- **If number or URL provided:** Run `gh issue view <number> --json title,state` to verify the issue exists. Capture the issue number and title for the design doc header. If the issue is **closed**, warn: "Issue #N is closed. Continue with this issue, pick a different one, or proceed without?" Handle accordingly.
- **If 'none':** Warn: "CONTRIBUTING.md requires filing a GitHub issue before brainstorming. You can create one now or proceed without one." If the user proceeds, record `Issue: None (exploratory)` for the design doc.

### 1b. Branch Check

Run `git branch --show-current` to detect the current branch.

- **If on `main` or `master`:** Warn: "You're on `<branch>`. CONTRIBUTING.md requires a feature branch before brainstorming. Want me to run `/using-git-worktrees` to create one?"
  - If yes: invoke using-git-worktrees, then resume brainstorming from Step 2.
  - If no: allow proceeding with a warning.
- **If on any other branch:** Proceed to Step 2.

## Checklist

You MUST create a task for each of these items and complete them in order:

1. **Pre-flight checks** — verify issue exists and on feature branch (soft gates, see Pre-flight Checks section)
2. **Explore project context** — check files, docs, recent commits
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation
5. **Consider subsystem boundaries** — does this fit in one subsystem or cross boundaries? If it crosses, note which SPEC.md files are relevant and flag that the plan should be split by subsystem. If a new subsystem boundary is identified that lacks a SPEC.md, recommend `/codify-subsystem` after implementation
6. **Present design** — in sections scaled to their complexity, get user approval after each section
7. **Write design doc** — save to `docs/plans/YYYY-MM-DD-<topic>-design.md` (local working directory, not committed)
8. **Evaluate UX design need** — if user-facing or agentic, recommend ux-design-agent
9. **Transition to implementation** — invoke writing-plans skill to create implementation plan

## Process Flow

```dot
digraph brainstorming {
    // Pre-flight: issue check
    "Pre-flight checks" [shape=box];
    "Issue provided?" [shape=diamond];
    "Verify issue exists" [shape=box];
    "Warn: issue recommended" [shape=box];
    "User proceeds?" [shape=diamond];
    "END" [shape=doublecircle];
    "Pre-flight checks" -> "Issue provided?";
    "Issue provided?" -> "Verify issue exists" [label="yes"];
    "Issue provided?" -> "Warn: issue recommended" [label="none"];
    "Verify issue exists" -> "On feature branch?";
    "Warn: issue recommended" -> "User proceeds?";
    "User proceeds?" -> "On feature branch?" [label="yes"];
    "User proceeds?" -> "END" [label="no"];

    // Pre-flight: branch check
    "On feature branch?" [shape=diamond];
    "Warn: on main" [shape=box];
    "Create branch?" [shape=diamond];
    "Invoke using-git-worktrees" [shape=box];
    "On feature branch?" -> "Explore project context" [label="yes"];
    "On feature branch?" -> "Warn: on main" [label="no"];
    "Warn: on main" -> "Create branch?";
    "Create branch?" -> "Invoke using-git-worktrees" [label="yes"];
    "Create branch?" -> "Explore project context" [label="no, proceed anyway"];
    "Invoke using-git-worktrees" -> "Explore project context";

    // Discovery and design
    "Explore project context" [shape=box];
    "Prior ideation exists?" [shape=diamond];
    "Read idea files" [shape=box];
    "Ask clarifying questions" [shape=box];
    "Propose 2-3 approaches" [shape=box];
    "Consider subsystem boundaries" [shape=box];
    "Present design sections" [shape=box];
    "User approves design?" [shape=diamond];
    "Explore project context" -> "Prior ideation exists?";
    "Prior ideation exists?" -> "Read idea files" [label="yes"];
    "Prior ideation exists?" -> "Ask clarifying questions" [label="no"];
    "Read idea files" -> "Ask clarifying questions";
    "Ask clarifying questions" -> "Propose 2-3 approaches";
    "Propose 2-3 approaches" -> "Consider subsystem boundaries";
    "Consider subsystem boundaries" -> "Present design sections";
    "Present design sections" -> "User approves design?";
    "User approves design?" -> "Present design sections" [label="no, revise"];
    "User approves design?" -> "Write design doc" [label="yes"];

    // Finalization
    "Write design doc" [shape=box];
    "UX design needed?" [shape=diamond];
    "Invoke ux-design-agent" [shape=box];
    "Invoke writing-plans skill" [shape=doublecircle];
    "Write design doc" -> "UX design needed?";
    "UX design needed?" -> "Invoke ux-design-agent" [label="yes"];
    "UX design needed?" -> "Invoke writing-plans skill" [label="no"];
    "Invoke ux-design-agent" -> "Invoke writing-plans skill";
}
```

**The terminal state is invoking writing-plans.** The only intermediate skills you may invoke are using-git-worktrees (during pre-flight, if on main) and ux-design-agent (when UX design is needed). Do NOT invoke any other implementation skill.

## The Process

**Prior ideation:**
- If user references an idea file (`docs/*-idea-*.md`) or mentions prior ideation, read it
- Follow any `Related: [[...]]` links to gather context from connected ideas
- Use this context to skip or shorten discovery — the problem/opportunity is already captured

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- If prior ideation exists, start from that context
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## Evaluating UX Design Need

After validating the design direction, evaluate whether detailed UX design is needed:

**Recommend ux-design-agent when:**
- User-facing interface (GUI, CLI, voice)
- Agentic system (AI takes actions on user's behalf)
- User model isn't obvious ("who uses this and how?")
- Complex interaction flows (onboarding, wizards, multi-step)

**Skip to writing-plans when:**
- Internal tooling (user model is "us")
- Simple feature with obvious interaction
- Backend/infrastructure work

**Ask explicitly:**
> "This involves [user-facing interface / agentic behavior / complex interaction].
> Would you like detailed UX design (requirements, user model, modality selection)?
> Or proceed directly to implementation planning?"

**If yes:**
- **REQUIRED SUB-SKILL:** Use ux-design-agent
- ux-design-agent will produce structured requirements
- Then continue to writing-plans

**If no:**
- Proceed to writing-plans with current design document

## After the Design

**Documentation:**
- Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md` (local working directory, not committed)
- Include this header at the top of the design doc:
  ```markdown
  # Design: <topic>

  **Issue:** #<number> — <title>
  **Date:** YYYY-MM-DD
  **Branch:** <branch-name>
  ```
  If the issue check was skipped, use `**Issue:** None (exploratory)`.
  Get the branch name from `git branch --show-current`.
- Use writing-clearly-and-concisely skill if available
- Paste the design into the PR body when you open it

**Implementation (if continuing):**
- Ask: "Ready to set up for implementation?"
- If no worktree was created during pre-flight, use using-git-worktrees to create one
- Use writing-plans to create detailed implementation plan

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design in sections, validate each
- **Be flexible** - Go back and clarify when something doesn't make sense

## Integration

**Invokes:**
- **using-git-worktrees** — During pre-flight checks, if user is on `main`/`master` and wants a branch

**Called by:**
- Directly via `/brainstorming`
- Any task creating features, building components, adding functionality, or modifying behavior (per skill trigger)

**Pairs with:**
- **writing-plans** — Terminal state; brainstorming always transitions to planning
- **ux-design-agent** — Optional intermediate step for user-facing or agentic designs
