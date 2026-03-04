---
name: executing-plans
description: Use when you have a written implementation plan to execute in a separate session with review checkpoints
---

# Executing Plans

## Overview

Load plan, review critically, execute tasks in batches, report for review between batches.

**Core principle:** Batch execution with checkpoints for review. Verify acceptance criteria at the end.

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

## The Process

### Step 1: Load and Review Plan
1. Read plan file
2. Review critically — identify questions or concerns
3. Note acceptance criteria from plan header
4. If concerns: Raise them before starting
5. If clear: Create TodoWrite and proceed

### Step 2: Execute Batch
**Default: First 3 tasks**

For each task:
1. Mark as in_progress
2. Load nearest SPEC.md for the task's target files (if one exists). Review its Invariants before starting — these are constraints you must not violate. If the task crosses subsystems, load the primary spec in full and only the Public Interface section from adjacent specs.
3. Follow each step exactly (plan has bite-sized steps)
4. Run verifications as specified
5. Mark as completed

### Step 3: Report
When batch complete:
- Show what was implemented
- Show verification output
- Say: "Ready for feedback."

### Step 4: Continue
Based on feedback:
- Apply changes if needed
- Execute next batch
- Repeat until complete

### Step 5: Verify Acceptance Criteria
After all tasks complete:
- Check each acceptance criterion from the plan header
- Run the tests that verify each condition
- Report: which criteria pass, which fail

### Step 6: Complete Development
After acceptance criteria verified:
- **REQUIRED SUB-SKILL:** Use finishing-a-development-branch
- Follow that skill to verify tests, present options, execute choice

## Agent Teams

For larger efforts or autonomous execution, this skill can be run by a **teammate** rather than in a manual session:

1. Controller spawns teammate using Task tool with `team_name`
2. Teammate loads and executes the plan
3. Teammate reports progress via messages
4. Controller reviews and unblocks as needed

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker mid-batch (missing dependency, test fails, instruction unclear)
- Plan has critical gaps
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Step 1 (Review) when:**
- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking after seeing implementation results

**Don't force through blockers** — stop and ask.

## Remember
- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Verify acceptance criteria after all tasks complete
- Between batches: just report and wait
- Stop when blocked, don't guess
- Never start implementation on main/master branch without explicit user consent

## Integration

**Required workflow skills:**
- **using-git-worktrees** - REQUIRED: Set up isolated workspace before starting execution
- **writing-plans** - Creates the plan this skill executes
- **finishing-a-development-branch** - Complete development after all tasks

**Alternative workflows:**
- **subagent-driven-development** - Same-session execution with fresh subagents, parallel dispatch, two-stage review
