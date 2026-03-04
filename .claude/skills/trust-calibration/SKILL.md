---
name: trust-calibration
description: Use when communicating agent confidence to users - when outputs need calibrated certainty markers, uncertainty acknowledgment, or evidence surfacing
---

# Trust Calibration

## Overview

Calibrate how agents communicate confidence. The goal is not maximum trust—it's accurate trust.

**Core principle:** Users should trust exactly as much as the agent deserves, no more, no less.

## When to Use

When designing agent communications that involve:
- Stating conclusions or recommendations
- Acknowledging limitations or uncertainty
- Showing evidence or reasoning
- Recovering from errors

**Invoked by:** delegation-oversight, approval-confirmation, failure-choreography

## The Core Problem

**Overtrust:** User accepts wrong output. Burns them once, they never delegate again.

**Undertrust:** User second-guesses correct output. Micromanagement negates delegation value.

Both stem from miscalibrated confidence communication.

## Five Calibration Levels

### Level 1: Claim-Level Confidence

Match linguistic confidence to actual confidence.

| Confidence | Verbs | Source | Recommendation |
|------------|-------|--------|----------------|
| High | "is", "will" | "[authoritative source]" | "Proceed with..." |
| Medium | "should", "likely" | "[partial evidence]" | "Consider..." |
| Low | "might", "appears" | "couldn't confirm" | "Verify before..." |

**When declarative:** Source authoritative, track record high, error cost low.

**When hedged:** Source ambiguous, extrapolating, error cost high.

### Level 2: Uncertainty Acknowledgment

"I don't know" is valuable—but must be specific.

**The uncertainty stack:**
1. **What** you're uncertain about (specific claim)
2. **Why** you're uncertain (source of doubt)
3. **How** to proceed (verification path)

**Types:**
- Source uncertainty: "Pricing from last month—may have changed"
- Inference uncertainty: "Based on tone, he seems opposed—I can't know his position"
- Scope uncertainty: "Found 3 vendors—there may be others I missed"
- Capability uncertainty: "Can draft outline—have lawyer review before signing"

### Level 3: Evidence Surfacing

Show enough work to trust, not so much they drown.

**Progressive disclosure:**
```
[Summary]      → What user needs to decide
[Key evidence] → 2-3 supporting points
[Full trail]   → Expandable complete reasoning
```

**Calibrate to stakes:**

| Stakes | Evidence Pattern |
|--------|------------------|
| Low | Conclusion only. Source on request. |
| Medium | Conclusion + key evidence. Trail available. |
| High | Conclusion + evidence + uncertainty + verification recommendation. |

### Level 4: Track Record

Trust accumulates across interactions.

**Domain-specific:** Build trust per capability, not globally.
```
✓ Email scheduling: 47 successful, 0 errors
⚠ Contract review: 3 successful, 1 significant error
```

**Error memory:** Surface past errors when relevant to current task.

**Improvement signaling:** When agent has improved, say so.

### Level 5: Calibration Failure Recovery

When user trusted and got burned.

**Recovery sequence:**
1. Acknowledge fully (don't minimize)
2. Recognize impact
3. Explain cause
4. State correction
5. Reset expectations

**Post-failure pattern:**
```
Pre-failure:  "Here's the analysis."
Post-failure: "Here's the analysis. Given the error last time,
              verify [specific vulnerability] before acting."
```

## Quick Reference

| Situation | Pattern |
|-----------|---------|
| High confidence, low stakes | Declarative. Source on demand. |
| High confidence, high stakes | Declarative + key evidence + verification available. |
| Medium confidence | Hedged + specific uncertainty + evidence. |
| Low confidence | Explicit uncertainty + why + verification recommendation. |
| Past errors in domain | Surface history + increased verification. |
| Post-failure | Full acknowledgment + cause + correction + reset. |

## Anti-Patterns

**Confidence theater:** Sounding confident regardless of actual confidence.

**Uncertainty flooding:** Hedging everything equally. Users ignore all signals.

**Evidence dumping:** Overwhelming users with proof. Learned helplessness.

**Trust amnesia:** Not tracking past performance.

**Minimized recovery:** Glossing over failures. Destroys trust faster than original error.

## References

- `references/confidence-patterns.md` - Linguistic inventory
- `references/uncertainty-patterns.md` - Uncertainty types
- `references/evidence-surfacing.md` - Progressive disclosure
- `references/track-record.md` - Building trust
- `references/failure-recovery.md` - Recovery patterns
