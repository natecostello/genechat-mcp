---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write implementation plans assuming the implementing agent has zero context for the codebase. Document everything: files to touch, code, testing, relevant docs. Each task must be self-contained — a subagent receiving only that task's text has everything needed.

DRY. YAGNI. TDD. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

## Task Sizing

**Each task must fit comfortably in a fresh subagent context (~50% of context window).** This is the hard constraint — tasks that exceed this degrade in quality as the subagent runs out of room for reasoning.

This means:
- A task includes ALL context needed — no "see Task 1" references
- Each task is directly pasteable as a subagent prompt
- Task N gets the same quality execution as Task 1 (fresh context)

Size tasks to the work, not to an arbitrary count. A plan may have 2 tasks or 6 — what matters is that each fits the context budget.

## Task Granularity

**Each step within a task is one action:**
- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** Execute this plan using subagent-driven-development (same session) or executing-plans (separate session / teammate).

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

**Acceptance Criteria — what must be TRUE when this plan is done:**
- [ ] [Specific verifiable condition, maps to a test]
- [ ] [Another condition]
- [ ] [Integration/behavioral condition]

**Dependencies:** [Other plans that must complete first, or "None"]

---
```

## Task Structure

Each task must be self-contained — a subagent receiving only this task text has everything needed to implement it.

````markdown
### Task N: [Component Name]

**Context:** [What this task builds, where it fits in the system, any relevant architectural decisions. Include enough that a fresh subagent understands the landscape without reading other tasks.]

**Subsystem spec(s):** [Path to nearest SPEC.md, or "None — new subsystem"]
**Key invariants from spec:** [List with IDs — the subagent must not violate these and must write tests for them]
- INV-N: [description] → test: `test_invN_*`
- FAIL-N: [description] → test: `test_failN_*`
**Adjacent specs:** [If task touches other subsystems, list their SPEC.md paths and only the Public Interface contracts relevant to this task — not their full invariants]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Depends on:** [Task M, or "Independent"]

**Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Dependencies

Mark each task's dependencies explicitly. Independent tasks can be dispatched to subagents in parallel. Dependent tasks run sequentially.

```markdown
### Task 1: Data model          [Independent]
### Task 2: API endpoint        [Independent]
### Task 3: Integration tests   [Depends on: Task 1, Task 2]
```

## Remember
- Exact file paths always
- Complete code in plan (not "add validation")
- Exact commands with expected output
- Each task self-contained with full context
- Size tasks to fit ~50% of subagent context window
- Include nearest SPEC.md path and key invariants in each task
- For cross-cutting tasks: full spec for primary subsystem, Public Interface only for adjacent subsystems. If >2 specs are relevant, the task is too large — split it by subsystem boundary
- Mark dependencies between tasks
- Acceptance criteria = what must be TRUE = the tests
- Anchor tests to SPEC.md item IDs (INV-N, FAIL-N) when a spec exists
- DRY, YAGNI, TDD, frequent commits

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Execution options:**

**1. Subagent-Driven (this session)** — I orchestrate fresh subagents per task, independent tasks run in parallel, review between tasks

**2. Agent Team** — Spawn a teammate to execute the plan autonomously, reports back when done

**3. Separate Session** — Open new session with executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use subagent-driven-development
- Stay in this session
- Fresh subagent per task + two-stage review

**If Agent Team chosen:**
- Spawn teammate using Task tool with `team_name`
- Teammate uses executing-plans to work through the plan
- Reports back on completion

**If Separate Session chosen:**
- Guide them to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses executing-plans
