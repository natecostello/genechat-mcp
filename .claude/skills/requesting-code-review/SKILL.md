---
name: requesting-code-review
description: Use when completing tasks, implementing major features, or before merging to verify work meets requirements
---

# Requesting Code Review

Dispatch code-reviewer subagent to catch issues before they cascade.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

**1. Detect context:**

Determine if a PR exists for the current branch and whether you are the author:

```bash
# Get PR number and author in a single API call.
# NOTE: If this fails, check gh auth status before assuming no PR exists.
# See "Error handling" below — silent fallback masks auth/network failures.
PR_JSON=$(gh pr view --json number,author 2>/dev/null) || PR_JSON=""

if [ -n "$PR_JSON" ]; then
  PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')
  PR_AUTHOR=$(echo "$PR_JSON" | jq -r '.author.login')
  CURRENT_USER=$(gh api user --jq '.login')
  IS_AUTHOR=$( [ "$PR_AUTHOR" = "$CURRENT_USER" ] && echo "true" || echo "false" )
else
  PR_NUMBER=""
  IS_AUTHOR=""
fi
```

If no PR exists, the review runs locally only (existing behavior).

**Error handling:** If `gh pr view` fails for reasons other than "no PR" (auth failure, network error, rate limit), the agent must surface the error rather than silently falling back to local-only review. Check `gh auth status` and retry before assuming no PR exists. A silent fallback means the agent skips posting to the PR — the user won't know the review happened.

**2. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**3. Dispatch code-reviewer subagent:**

Use Task tool with code-reviewer type, fill template at `code-reviewer.md`

**Placeholders:**
- `{WHAT_WAS_IMPLEMENTED}` - What you just built
- `{PLAN_REFERENCE}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit
- `{DESCRIPTION}` - Brief summary
- `{PR_NUMBER}` - PR number (empty for local-only review)
- `{IS_AUTHOR}` - `true` if current user authored the PR, `false` otherwise

**4. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

## Example: Local Review (no PR)

```
[Just completed Task 2: Add PR-aware review flow]

You: Let me request code review before proceeding.

PR_NUMBER=""  # No PR exists yet
BASE_SHA=447c459
HEAD_SHA=9a0d42a

[Dispatch code-reviewer subagent]:
  WHAT_WAS_IMPLEMENTED: PR-aware review flow with authorship detection
  PLAN_REFERENCE: Task 2 from docs/plans/optimize-pr-review.md
  BASE_SHA: 447c459
  HEAD_SHA: 9a0d42a
  DESCRIPTION: Added context detection, PR commenting, and authorship-based action branching
  PR_NUMBER: ""
  IS_AUTHOR: ""

[Subagent returns]:
  Strengths: Clean decision matrix, backwards-compatible design
  Issues:
    Important: Redundant API calls in detection script
    Minor: Examples lack concrete placeholder values
  Assessment: Ready to proceed with fixes

You: [Fix redundant API calls, continue to Task 3]
```

## Example: PR Review (self-authored)

```
[PR #5 is open, you are the author]

PR_NUMBER=5, IS_AUTHOR=true

[Dispatch code-reviewer subagent]
[Subagent posts structured comment on PR #5]
[Clean review: comment signals LGTM — no --approve attempted]
[Issues found: comment lists them — no --request-changes attempted]
```

## Example: PR Review (external)

```
[PR #12 from a contributor, you are not the author]

PR_NUMBER=12, IS_AUTHOR=false

[Dispatch code-reviewer subagent]
[Subagent posts structured comment on PR #12]
[Clean review: gh pr review 12 --approve]
[Issues found: gh pr review 12 --request-changes]
```

## Integration with Workflows

**Subagent-Driven Development:**
- Review after EACH task
- Catch issues before they compound
- Fix before moving to next task

**Executing Plans:**
- Review after each batch (3 tasks)
- Get feedback, apply, continue

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: requesting-code-review/code-reviewer.md
