# Escalation Taxonomy

## Category Definitions

### Uncertainty
Agent's confidence in correctness is below threshold.

**Subtypes**:
- **Source uncertainty**: Information may be wrong or stale
- **Inference uncertainty**: Reasoning beyond explicit data
- **Interpretation uncertainty**: Ambiguous instructions or data

**UX treatment**: Present evidence, acknowledge gaps, offer verification path.

**Example**: "The deadline appears to be Friday based on the email thread, but the thread is 3 weeks old. Verify this hasn't changed?"

### Stakes
Consequences of the action exceed what user has delegated.

**Subtypes**:
- **Financial**: Cost above threshold
- **Reputational**: External visibility, public-facing
- **Irreversible**: Cannot be undone
- **Scope**: Affects more people/systems than typical

**UX treatment**: Explicitly state what's at stake. Show consequence preview.

**Example**: "This email goes to the press list (847 recipients). Sending to external list—want to review?"

### Policy Ambiguity
User's rules don't clearly cover this case.

**Subtypes**:
- **Edge case**: Situation falls between defined categories
- **Conflict**: Multiple rules apply with different implications
- **Gap**: No relevant rule exists

**UX treatment**: Surface the ambiguity explicitly. Present the rules that almost apply.

**Example**: "This meeting is half in your 'deep work' block and half outside it. I normally protect deep work time—should I accept anyway?"

### Preference-Sensitivity
Multiple valid approaches; choice depends on user values.

**Subtypes**:
- **Tone/voice**: How to say something
- **Prioritization**: What to do first when everything is urgent
- **Tradeoffs**: Explicit choice between competing goods

**UX treatment**: Present options with tradeoffs, not just yes/no. Let user express preference.

**Example**: "Two valid approaches: (1) Apologize for delay, reschedule ASAP. (2) Reschedule without apology, project confidence. Your call?"

### Novelty
First encounter with this task type or situation.

**Subtypes**:
- **New task type**: Never done this before
- **New context**: Familiar task in unfamiliar setting
- **Parameter outlier**: Familiar task with unusual parameters

**UX treatment**: Explicitly flag novelty. Seek feedback to calibrate future handling.

**Example**: "First time handling a travel reimbursement. Here's my approach—does this look right?"

### Conflict
Agent's reasoning contradicts user's stated intent or prior behavior.

**Subtypes**:
- **Intent contradiction**: Request seems to conflict with goals
- **Behavioral inconsistency**: Different from past preferences
- **Logical conflict**: Internal inconsistency in instructions

**UX treatment**: Surface the conflict non-judgmentally. Seek clarification.

**Example**: "You asked to decline all meetings this week, but this invite is from your skip-level. Should I still decline?"

## Threshold Approaches

### Static Thresholds
Fixed boundaries per category. Simple but inflexible.

```python
THRESHOLDS = {
    'uncertainty': 0.7,      # confidence below this triggers
    'financial': 100,        # dollars above this triggers
    'external': True,        # any external communication triggers
}
```

**Use for**: Initial deployment, regulatory requirements, non-negotiable stakes.

### Adaptive Thresholds
Boundaries that adjust based on user behavior.

```python
def adapt_threshold(category, user_history):
    base = THRESHOLDS[category]
    # Relax if user consistently approves without modification
    if approval_rate(user_history, category) > 0.95:
        return base * 1.2  # raise threshold (fewer escalations)
    # Tighten if user frequently modifies
    if modification_rate(user_history, category) > 0.3:
        return base * 0.8  # lower threshold (more escalations)
    return base
```

**Use for**: Mature relationships, learned preferences, personalization.

### User-Configured Thresholds
Explicit user settings per category or domain.

```
Calendar: "Act autonomously for internal meetings, ask for external"
Email: "Draft all, let me review before sending external"
Purchases: "Under $50 autonomous, $50-$200 notify, over $200 ask"
```

**Use for**: Power users, high-stakes domains, explicit control preferences.

## Signal Design

### Category-Specific Visual Treatment

| Category | Visual Signal | Rationale |
|----------|--------------|-----------|
| Uncertainty | Dashed border, muted color | Uncertainty is soft, not alarming |
| Stakes | Bold border, warm color | Stakes demand attention |
| Policy | Neutral, informational | Policy is clarification, not warning |
| Preference | Choice-oriented layout | Multiple options, not yes/no |
| Novelty | "New" badge, learning frame | Frame as calibration opportunity |
| Conflict | Alert icon, contrast color | Conflict needs explicit attention |

### Anti-Pattern: Uniform Escalation
All categories look identical:
```
✗ [Modal] "Requires your approval" [Approve] [Reject]
```

This trains users to ignore category distinctions. They should feel different because they *are* different.

### Urgency Layering
Within each category, urgency varies:

| Urgency | Treatment |
|---------|-----------|
| Low | Batched with other escalations, async review |
| Medium | Individual notification, reasonable wait time |
| High | Immediate notification, short timeout |
| Critical | Block workflow until resolved |

Urgency is orthogonal to category. A stakes escalation can be low-urgency (budget review) or critical (unauthorized wire transfer in progress).
