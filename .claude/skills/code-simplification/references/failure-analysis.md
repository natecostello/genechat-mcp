# Failure Analysis

When a simplification breaks tests, analyze before reverting. Failures are signals.

## Decision Tree

```
Test fails after simplification
│
├─ Is the test testing implementation details?
│  └─ YES → Brittle test. Flag for test improvement.
│
├─ Does the test rely on something the simplification removed?
│  ├─ Was that reliance intentional/documented?
│  │  └─ YES → Skip simplification. It's not dead code.
│  └─ NO → Hidden coupling. Flag for refactor opportunity.
│
├─ Does the failure reveal inconsistency elsewhere?
│  └─ YES → Expand scope. Attempt to fix inconsistency.
│
└─ None of the above
   └─ Revert and skip. Log the reason.
```

## Brittle Test Indicators

The test is likely brittle if it:

- Asserts on internal function calls (mock call counts)
- Snapshots internal structure rather than output
- Relies on specific execution order when order doesn't matter
- Tests private methods directly
- Breaks when refactoring without behavior change

**Action:** Flag test for improvement. Don't let brittle tests block valid simplifications.

**Report format:**
```
### Blocked
- **[Simplification]** (file.ts)
  - Attempted: [What was tried]
  - Failure: Test `test_name` relies on [internal detail]
  - Analysis: Test is brittle—tests [structure/implementation] not behavior
  - Action taken: Reverted, flagged test for improvement
  - Recommendation: Refactor test to assert [output/behavior], then retry
```

## Hidden Coupling Indicators

Hidden coupling exists if:

- Removing "unused" code breaks distant tests
- Function is called via string lookup / reflection
- Code is used by external consumers not in test suite
- Implicit contract exists (naming convention, file location)

**Action:** Flag as refactor opportunity. The coupling should be made explicit.

**Report format:**
```
### Escalations
- **Hidden coupling in `file.ts`**: `functionName` appears unused but is
  called via [mechanism] in [location]. Recommend: [make explicit / audit].
```

## Inconsistency Indicators

Inconsistency exists if:

- Simplification reveals two code paths doing same thing differently
- Removing duplication shows one path handles edge case the other doesn't
- Test failure exposes assumption that should be documented

**Action:** Expand scope. Attempt to fix the inconsistency (make both paths consistent).

**Report format (if fixed):**
```
### Applied
- Fixed inconsistent handling of [case] in [file.ts] (discovered during simplification)
```

**Report format (if unfixable):**
```
### Blocked
- **[Simplification]** (file.ts)
  - Attempted: [What was tried]
  - Failure: Revealed inconsistent handling of [case]
  - Analysis: [Path A] handles [X], [Path B] doesn't
  - Action taken: Reverted, inconsistency exceeds simplification scope
  - Recommendation: Unify handling of [case] before retrying
```

## Scope Expansion Limits

When attempting to fix a deeper issue, stay within scope if:

- Fix is in same file or directly related files
- Fix doesn't require interface changes
- Fix doesn't affect external API
- Fix can be verified by same test suite

Escalate (don't fix) if:

- Fix requires changes across multiple modules
- Fix requires architectural decisions
- Fix would change external behavior
- Fix requires test infrastructure changes

## Analysis Checklist

Before reverting any simplification failure:

1. [ ] Read the failing test—what is it actually asserting?
2. [ ] Is the assertion about behavior or implementation?
3. [ ] Is the "dead" code actually dead, or is there hidden usage?
4. [ ] Does the failure reveal something that should be fixed?
5. [ ] Is fixing it within simplification scope?

If you can't answer these questions, default to SKIP (not escalate).
