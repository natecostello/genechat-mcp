---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

**Tests:**
```
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"
```

**Regression tests (TDD Red-Green):**
```
✅ Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
❌ "I've written a regression test" (without red-green verification)
```

**Build:**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"
```

**Agent delegation:**
```
✅ Agent reports success → Check VCS diff → Verify changes → Report actual state
❌ Trust agent report
```

## Why This Matters

From 24 failure memories:
- your human partner said "I don't believe you" - trust broken
- Undefined functions shipped - would crash
- Missing requirements shipped - incomplete features
- Time wasted on false completion → redirect → rework
- Violates: "Honesty is a core value. If you lie, you'll be replaced."

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.

## Integration with Code Simplification

After verification passes, the code-simplification skill runs automatically:

```
verify (this skill) → simplify → re-verify → complete
```

The simplification skill will:
- Apply low-risk changes automatically
- Flag structural changes for approval
- Analyze failures for deeper issues
- Re-run verification after changes

Only after simplification completes and final verification passes can completion be claimed.

## SPEC.md Invariant Check

After standard verification passes, check for subsystem specifications:

1. **Find SPEC.md** — Walk up from modified files to find the nearest SPEC.md
2. **If found, check invariants** — Review each invariant in the spec's table.
   For each one, verify it still holds after your changes. How to verify
   depends on the invariant type:
   - **Testable invariants** (data constraints, API contracts): run the
     corresponding `test_invN_*` test. A passing test is sufficient evidence.
   - **Architectural invariants** (coupling rules, file organization, naming):
     review the diff against the constraint. Confirm the change doesn't
     introduce a violation.
   - **Unclear or untestable invariants**: note them in the report rather
     than skipping — flag for human review.
3. **Check coverage** — If the SPEC.md has a Coverage table in its Testing
   section, verify that every INV-N and FAIL-N has a corresponding test and
   that the test passes. Flag uncovered spec items.
4. **Report** — Include invariant and coverage check results in verification output

This is a lightweight consistency check, not a replacement for the full test
suite. If an invariant is unclear or untestable, note it rather than skipping it.

### Staleness Check

After checking invariants, assess whether the SPEC.md is still current:

1. **Compare modification dates** — If source files in the subsystem have been
   modified more recently than SPEC.md (check via `git log -1 --format=%ci`),
   the spec may be stale.
2. **Check for drift** — Do your changes introduce new invariants, failure modes,
   or public interfaces not captured in the spec? If yes, flag for update.
3. **Report staleness** — Include in verification output. Recommend
   `/codify-subsystem` to refresh the spec if significant drift is detected.

A stale spec is better than no spec — don't block completion on staleness alone.
Flag it and move on.

```
SPEC.md invariant check:
- [path/to/SPEC.md]
- INV-1: [description] → ✅ Still holds / ❌ Violated
- FAIL-1: [description] → ✅ Handled / ❌ Unhandled

Coverage check:
- INV-1 → test_inv1_* ✅ Covered / ❌ Missing test
- FAIL-1 → test_fail1_* ✅ Covered / ❌ Missing test

Staleness:
- SPEC.md last modified: [date]
- Source files modified after spec: [yes/no — list files if yes]
- New invariants/interfaces not in spec: [yes/no — describe if yes]
- Recommendation: [Current / Recommend re-codification]
```
