---
name: subagent-driven-development
description: Use when executing implementation plans with independent tasks in the current session
---

# Subagent-Driven Development

Execute plan by dispatching fresh subagents per task, with two-stage review after each: spec compliance first, then code quality. Independent tasks can run in parallel.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality at scale. Independent tasks parallelize; dependent tasks wait.

## When to Use

```dot
digraph when_to_use {
    "Have implementation plan?" [shape=diamond];
    "Tasks mostly independent?" [shape=diamond];
    "Stay in this session?" [shape=diamond];
    "subagent-driven-development" [shape=box];
    "executing-plans or agent team" [shape=box];
    "Write a plan first (writing-plans)" [shape=box];
    "Reconsider plan structure" [shape=box];

    "Have implementation plan?" -> "Tasks mostly independent?" [label="yes"];
    "Have implementation plan?" -> "Write a plan first (writing-plans)" [label="no"];
    "Tasks mostly independent?" -> "Stay in this session?" [label="yes"];
    "Tasks mostly independent?" -> "Reconsider plan structure" [label="no - tightly coupled"];
    "Stay in this session?" -> "subagent-driven-development" [label="yes"];
    "Stay in this session?" -> "executing-plans or agent team" [label="no"];
}
```

**If tasks are tightly coupled** (shared files, shared state, ordering dependencies beyond explicit `Depends on:`), break them into smaller independent units or execute them serially within a single subagent.

## The Process

```dot
digraph process {
    rankdir=TB;

    subgraph cluster_per_task {
        label="Per Task (or per parallel group)";
        "Dispatch implementer subagent" [shape=box];
        "Implementer asks questions?" [shape=diamond];
        "Answer questions, provide context" [shape=box];
        "Implementer implements, tests, commits, self-reviews" [shape=box];
        "Dispatch spec reviewer subagent" [shape=box];
        "Spec compliant?" [shape=diamond];
        "Fix subagent fixes spec gaps" [shape=box];
        "Dispatch code quality reviewer subagent" [shape=box];
        "Quality approved?" [shape=diamond];
        "Fix subagent fixes quality issues" [shape=box];
        "Mark task complete" [shape=box];
    }

    "Read plan, extract tasks, note dependencies, create TodoWrite" [shape=box];
    "More tasks remain?" [shape=diamond];
    "Verify acceptance criteria" [shape=box];
    "Dispatch final code reviewer for entire implementation" [shape=box];
    "Use finishing-a-development-branch" [shape=box style=filled fillcolor=lightgreen];

    "Read plan, extract tasks, note dependencies, create TodoWrite" -> "Dispatch implementer subagent";
    "Dispatch implementer subagent" -> "Implementer asks questions?";
    "Implementer asks questions?" -> "Answer questions, provide context" [label="yes"];
    "Answer questions, provide context" -> "Dispatch implementer subagent";
    "Implementer asks questions?" -> "Implementer implements, tests, commits, self-reviews" [label="no"];
    "Implementer implements, tests, commits, self-reviews" -> "Dispatch spec reviewer subagent";
    "Dispatch spec reviewer subagent" -> "Spec compliant?";
    "Spec compliant?" -> "Fix subagent fixes spec gaps" [label="no"];
    "Fix subagent fixes spec gaps" -> "Dispatch spec reviewer subagent" [label="re-review"];
    "Spec compliant?" -> "Dispatch code quality reviewer subagent" [label="yes"];
    "Dispatch code quality reviewer subagent" -> "Quality approved?";
    "Quality approved?" -> "Fix subagent fixes quality issues" [label="no"];
    "Fix subagent fixes quality issues" -> "Dispatch code quality reviewer subagent" [label="re-review"];
    "Quality approved?" -> "Mark task complete" [label="yes"];
    "Mark task complete" -> "More tasks remain?";
    "More tasks remain?" -> "Dispatch implementer subagent" [label="yes"];
    "More tasks remain?" -> "Verify acceptance criteria" [label="no"];
    "Verify acceptance criteria" -> "Dispatch final code reviewer for entire implementation";
    "Dispatch final code reviewer for entire implementation" -> "Use finishing-a-development-branch";
}
```

### Step by step

1. **Read plan.** Extract all tasks with full text. Note dependencies.
2. **Check task sizing.** Each task should fit ~50% of a subagent's context window. If a task looks too large, break it up before dispatching.
3. **Load subsystem context.** For each task, find the nearest SPEC.md to the task's target files. If one exists, prepend its key sections (Purpose, Invariants, Failure Modes) to the task context when dispatching. For cross-cutting tasks: include the full spec for the primary subsystem and only the Public Interface section from adjacent subsystems. If a task needs >2 specs, it crosses too many boundaries — split it before dispatching.
4. **Dispatch task.** Fresh subagent (via Task tool) with full task text and context. For independent tasks, dispatch in parallel. For dependent tasks, wait.
5. **Handle questions.** If the subagent asks questions, answer clearly before letting them proceed.
6. **Spec review.** Dispatch spec compliance reviewer (./spec-reviewer-prompt.md). If issues found, dispatch fix subagent, then re-review.
7. **Quality review.** Dispatch code quality reviewer (./code-quality-reviewer-prompt.md). If issues found, dispatch fix subagent, then re-review.
8. **Next task.** Repeat until all tasks complete.
9. **Verify acceptance criteria.** Check the plan's acceptance criteria. Run the tests.
10. **Final review.** Dispatch code reviewer for the entire implementation — catches cross-task integration issues.
11. **Finish.** Use finishing-a-development-branch.

### Parallel dispatch

Independent tasks can be dispatched simultaneously. The per-task review cycle (steps 5-6) runs after each implementer finishes, so reviews can also run in parallel across tasks.

**Guard:** Never parallelize tasks that write to the same files — this is hidden coupling even if tasks aren't marked as dependent.

## Orchestration: Task Tool vs. Agent Teams

**Task tool (default):** Dispatch subagents with Task tool. Controller manages coordination.

**Agent teams (for larger efforts):** Spawn a team with Teammate tool. Create tasks in the shared task list. Teammates claim and execute tasks, coordinating via messages. Controller acts as team lead.

Use agent teams when:
- Multiple plans to execute in sequence
- Want teammates to self-coordinate
- Controller context is getting heavy

## Prompt Templates

- `./implementer-prompt.md` — Dispatch implementer subagent
- `./spec-reviewer-prompt.md` — Dispatch spec compliance reviewer subagent
- `./code-quality-reviewer-prompt.md` — Dispatch code quality reviewer subagent

## Example Workflow

```
You: I'm using Subagent-Driven Development to execute this plan.

[Read plan: docs/plans/feature-plan.md]
[3 tasks: Task 1 (independent), Task 2 (independent), Task 3 (depends on 1+2)]
[Create TodoWrite with all tasks]

Tasks 1 and 2 are independent — dispatch in parallel:

[Dispatch Task 1 implementer with full task text + context]
[Dispatch Task 2 implementer with full task text + context]

Task 1 implementer: Done. Implemented X, 5/5 tests passing, committed.
Task 2 implementer: "Before I begin — should Y use Z pattern?"
You: "Yes, follow existing pattern in src/z.py"
Task 2 implementer: Done. Implemented Y, 3/3 tests passing, committed.

[Dispatch spec reviewers for both in parallel]
Task 1 spec review: ✅ Spec compliant
Task 2 spec review: ❌ Missing: error handling for edge case

[Dispatch fix subagent for Task 2]
Fix subagent: Added error handling, committed.
[Re-review Task 2]
Task 2 spec review: ✅ Spec compliant

[Dispatch code quality reviewers for both in parallel]
Both: ✅ Approved

[Mark Tasks 1 and 2 complete]

Task 3 depends on 1+2, now unblocked:

[Dispatch Task 3 implementer]
Task 3 implementer: Done. Integration tests passing, committed.

[Spec review → ✅, Quality review → ✅]
[Mark Task 3 complete]

[Verify acceptance criteria from plan header — all pass]
[Dispatch final code reviewer for entire implementation]
Final reviewer: All requirements met, no cross-task issues. Approved.

[Use finishing-a-development-branch]
```

## Trade-offs

**vs. Manual execution:**
- Fresh context per task (no confusion from accumulated state)
- Subagent can ask questions before and during work
- Two-stage review catches issues early

**vs. executing-plans:**
- Same session (no handoff)
- Continuous progress (no waiting for human between batches)
- Review checkpoints automatic
- But: controller context grows as tasks accumulate

**Cost:** Each task costs at minimum 3 subagent invocations (implementer + spec reviewer + quality reviewer), plus fix subagents for review failures and a final whole-implementation reviewer. Catching issues per-task is cheaper than debugging integration problems later.

## Red Flags

**Never:**
- Start implementation on main/master branch without explicit user consent
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed issues
- Make subagent read plan file (provide full text instead)
- Skip scene-setting context (subagent needs to understand where task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance
- Skip review loops (reviewer found issues = fix = review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is ✅** (wrong order)
- Dispatch dependent tasks before their dependencies complete
- Parallelize tasks that write to the same files (hidden coupling)

**If subagent asks questions:**
- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

**If reviewer finds issues:**
- Dispatch fix subagent with specific instructions
- Reviewer reviews again
- Repeat until approved

**If subagent fails task:**
- Dispatch fresh fix subagent with specific instructions
- Don't try to fix manually (context pollution)

## Integration

**Required workflow skills:**
- **using-git-worktrees** — REQUIRED: Set up isolated workspace before starting execution
- **writing-plans** — Creates the plan this skill executes
- **requesting-code-review** — Code review template for reviewer subagents
- **finishing-a-development-branch** — Complete development after all tasks

**Subagents should use:**
- **test-driven-development** — Subagents follow TDD for each task

**Alternative workflows:**
- **executing-plans** — Batch execution in a separate session with human checkpoints
