# Code Quality Reviewer Prompt Template

Use this template when dispatching a code quality reviewer subagent.

**Purpose:** Verify implementation is well-built (clean, tested, maintainable)

**Only dispatch after spec compliance review passes.**

```
Task tool (code-reviewer):
  Use template at .claude/skills/requesting-code-review/code-reviewer.md

  WHAT_WAS_IMPLEMENTED: [from implementer's report]
  PLAN_OR_REQUIREMENTS: Task N from [plan-file]
  BASE_SHA: [commit before task]
  HEAD_SHA: [current commit]
  DESCRIPTION: [task summary]
  PR_NUMBER: [from PR detection, or empty for local-only review]
  IS_AUTHOR: [true/false from PR detection, or empty for local-only]
```

**PR context:** If a PR exists for the current branch, detect it before dispatching (see requesting-code-review SKILL.md for the detection script). If no PR exists, leave PR_NUMBER and IS_AUTHOR empty — review runs locally only.

**Code reviewer returns:** Strengths, Issues (Critical/Important/Minor), Assessment
