# Checkpoint Patterns

## Trigger Types

### Uncertainty-Based Triggers
Pause when agent confidence drops below threshold.

```
IF confidence(decision) < threshold[domain]
   AND cost(asking) < cost(error) * P(error)
THEN checkpoint
```

**Threshold calibration**:
- Start conservative (lower thresholds = more checkpoints)
- Raise threshold as track record builds
- Per-domain thresholds: scheduling might be 0.7, financial decisions 0.95

**Anti-pattern**: Global threshold. Uncertainty in "which meeting room" differs from uncertainty in "which investment."

### Stakes-Based Triggers
Pause when consequences exceed user's configured autonomy envelope.

Stakes dimensions:
- **Reversibility**: Can this be undone? At what cost?
- **Scope**: Who/what is affected?
- **Magnitude**: How much is at stake (time, money, reputation)?
- **External visibility**: Will others see this action?

**Pattern**: Map stakes dimensions to autonomy gradient. User configures by dimension, system triggers when any dimension exceeds threshold.

### Novelty-Based Triggers
Pause on first encounter with new task types or edge cases.

Detection signals:
- Task type not in training distribution
- Parameters outside historical range
- Context significantly different from prior instances

**Conservative default**: New situations should checkpoint until user explicitly grants autonomy.

## Checkpoint Content Design

### The 30-Second Rule
A checkpoint should be evaluable in 30 seconds or less. If it requires more:
- Action is too complex for single approval (break it up)
- Context is insufficient (add more)
- User needs to take over, not approve

### Content Structure

```
CHECKPOINT: [One-line action description]

Context: [Why this is happening now, 1-2 sentences]
Proposed: [Specific action, rendered if possible]
Confidence: [High/Medium/Low with brief reason]

[Approve] [Modify] [Take Over]
```

**Lead with decision**: "Send this email?" not "I've drafted an email response..."

### Rendered vs. Described
Prefer rendered previews over descriptions:

```
✗ "I'll send an email declining the meeting"
✓ [Rendered email preview] → [Send] [Edit] [Cancel]
```

Rendered previews:
- Enable evaluation without mental simulation
- Make scope explicit (who receives, exact wording)
- Reduce ambiguity about what "approve" means

## Checkpoint Frequency Adaptation

### Signal: Response Latency
- <2 seconds: Either excellent calibration OR rubber-stamping
- 2-10 seconds: Normal evaluation
- >30 seconds: Checkpoint may be too complex

**Distinguish rubber-stamping from calibration**: Inject occasional probe trials—checkpoints for actions user has explicitly not configured to approve. If probes get fast approval, user is rubber-stamping.

### Signal: Override Rate
- High override rate: Agent is miscalibrated on this domain
- Zero override rate: Either perfect calibration OR user is disengaged

Track override rate per domain. High rates indicate need for more frequent checkpoints; near-zero warrants periodic verification.

### Adaptation Protocol
1. Start with baseline frequency (conservative)
2. Track user engagement signals (latency, modifications, overrides)
3. Adjust per-domain based on track record
4. Surface proposed adjustments periodically: "You've approved all 23 calendar checkpoints. Act autonomously for calendar?"
5. Allow manual override of learned preferences

## Anti-Patterns

### Approval Theater
Checkpoints that can't be meaningfully evaluated:
```
✗ "Proceed with data processing?" [Yes] [No]
   (User has no idea what "data processing" entails)
```

Fix: Show specific action, provide enough context to evaluate.

### Checkpoint Fatigue Design
Equally-weighted checkpoints for all actions:
```
✗ Same modal for "save draft" and "publish to 10,000 subscribers"
```

Fix: Stakes-based visual differentiation. Routine actions inline, high-stakes actions prominent.

### Context Stripping
Checkpoints without trigger explanation:
```
✗ "Send this email?" (User: "...why are you asking me?")
```

Fix: Include trigger context. "Sending external email [to press list]—checking because this goes outside company."
