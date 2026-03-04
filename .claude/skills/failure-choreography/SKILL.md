---
name: failure-choreography
description: Use when designing how agentic systems fail gracefully - when partial failure must surface progress, preserve state, and hand off to humans with dignity
---

# Failure Choreography

## Overview

Turn system failure from betrayal into handoff. The failure surface IS the interface.

**Core principle:** Failures in consequential work are first-class design artifacts, not exceptions.

**Announce at start:** "I'm using the failure-choreography skill to design failure handling."

## When to Use

When designing agentic systems that:
- Execute multi-step tasks
- Have real stakes
- Might fail mid-execution

## The Goal

A well-choreographed failure:
- Makes completed progress visible and usable
- Draws clear lines between saved and lost state
- Explains what happened at calibrated depth
- Presents recovery as choices, not dead ends
- Transfers control with enough context for human dignity

## Five Capability Domains

### 1. Partial Success Surfacing

When step 5 of 7 fails, steps 1-4 happened. Don't let that work vanish.

**Pattern:**
```
✗ "Task failed."

✓ "Completed 4 of 7 steps before failure:
   ✓ Data extraction (23 records)
   ✓ Validation (all passed)
   ✓ Enrichment (geocoding complete)
   ✓ Format conversion (CSV ready)
   ✗ Upload failed at authentication

   Completed work saved to: /output/partial/"
```

**Principle:** Checkpoint on step completion. Persist before proceeding.

### 2. State Preservation

Users need to know: what's saved, what's lost, what's uncertain?

| Category | Description | Action |
|----------|-------------|--------|
| **Preserved** | Can be reused | List with locations |
| **Lost** | Must be redone | List with recreation cost |
| **Uncertain** | Needs verification | List with how to verify |

### 3. Failure Explanation

Calibrate transparency to audience and stakes.

**Level 1 - User-facing:** What happened in task terms.
> "Upload failed: server rejected connection after file preparation."

**Level 2 - Actionable:** What specifically failed and why.
> "Authentication to storage.example.com failed. API key may have expired."

**Level 3 - Technical:** For debugging or escalation.
> "ConnectionError: HTTPSConnectionPool... SSLCertVerificationError..."

**Default:** L1+L2 visible, L3 expandable.

### 4. Recovery Options

Failure without options is a wall. Failure with options is a fork.

**Pattern:**
```
What would you like to do?

[Retry]     Attempt failed step again
            Good if: temporary issue

[Resume]    Skip failed step, continue
            Note: downstream may fail

[Manual]    Download partial results, complete yourself
            Available: processed_data.csv

[Abandon]   Stop, preserve completed work
            Saved to: /output/partial/
```

**Each option needs:** Clear name, what it does, when appropriate, consequences.

### 5. Handoff to Human

**Dignity threshold:** Human can understand, assess, decide, and act without interrogating the system.

**Handoff package:**
```
SITUATION: [1-3 sentences on what happened]

PROGRESS:
✓ [completed items]
✗ [failed item]
⏸ [not attempted]

STATE:
Preserved: [locations]
Lost: [items]
Uncertain: [items + verification steps]

OPTIONS:
1. [choice with consequences]
2. [choice with consequences]

RECOMMENDATION: [agent's suggested path]

IF YOU CONTINUE: [next steps]
```

## Output

Add to requirements document:

```markdown
## Failure Handling

### Partial Success
- [How completed work is surfaced]

### State Categories
- Preserved: [what/where]
- Lost: [what/cost]
- Uncertain: [what/verification]

### Explanation Levels
- L1: [user-facing summary]
- L2: [actionable detail]
- L3: [technical trace]

### Recovery Options
- [Options with consequences]

### Handoff Package
- [What human receives]
```

## Integration

**Called by:** approval-confirmation (on timeout/rejection), delegation-oversight (on handoff failure)

**Coordinates with:** trust-calibration (for state uncertainty framing)

## Anti-Patterns

**Silent failure:** Error logged, user sees nothing.

**Void progress:** Completed work vanishes.

**State ambiguity:** User doesn't know what's saved.

**Dead ends:** Failure with no options.

**Context collapse:** "Task failed. See logs."

## References

- `references/partial-success-patterns.md` - Progress surfacing
- `references/state-preservation.md` - Checkpoint strategies
- `references/failure-explanation.md` - Calibrated explanation
- `references/recovery-patterns.md` - Recovery options
- `references/handoff-patterns.md` - Handoff templates
