# Autonomy Gradients

## Configuration UX Patterns

### Preset-Based Configuration
Start with coarse presets, allow refinement.

**Presets**:
```
[Conservative]    Check everything before acting
[Balanced]        Check important decisions, act on routine tasks
[Autonomous]      Act and notify; ask only for major decisions
[Full Trust]      Act autonomously in this domain
```

**Refinement path**: After user selects preset, system proposes domain-specific adjustments based on observed behavior.

### Domain-Specific Configuration
Different autonomy levels per task domain.

```yaml
calendar:
  internal_meetings: autonomous
  external_meetings: recommend_and_approve
  recurring_series: autonomous_with_notify

email:
  drafting: autonomous
  internal_send: autonomous_with_notify
  external_send: recommend_and_approve
  external_to_list: always_ask

purchases:
  under_50: autonomous
  50_to_200: autonomous_with_notify
  over_200: recommend_and_approve
```

### Condition-Based Configuration
Rules that trigger different autonomy levels.

```
IF recipient is external AND email mentions [pricing/contract/legal]
THEN require_approval
ELSE IF recipient is external
THEN recommend_and_approve
ELSE autonomous_with_notify
```

## Adaptation Mechanisms

### Learning from Overrides
When user modifies agent's proposed action, treat as preference signal.

```python
def learn_from_override(proposed, actual, context):
    """Extract preference signal from user modification."""
    
    # What did user change?
    delta = diff(proposed, actual)
    
    # In what context?
    features = extract_context(context)
    
    # Update preference model
    preferences.update(features, delta)
    
    # Consider surfacing learned pattern
    if confidence_in_pattern(features, delta) > threshold:
        queue_confirmation(
            f"I've noticed you prefer {delta} when {features}. "
            f"Should I do this automatically?"
        )
```

### Surfacing Learned Preferences
Periodically ask user to confirm inferred preferences.

```
Pattern detected: You've modified all external email sign-offs 
from "Best, Claude" to "Regards, [name]"

Should I:
○ Always use "Regards, [name]" for external emails
○ Ask each time for external emails  
○ Keep my current approach (you'll continue to edit)
```

**Timing**: Surface after N consistent overrides (not after first occurrence).

### Calibration Drift Detection
Monitor for changes in user behavior that suggest preferences have shifted.

Signals:
- Sudden increase in override rate for a domain
- Approval latency increasing (suggests growing discomfort)
- Explicit feedback ("Why are you still asking me about this?")

Response: Prompt preference review for affected domains.

## The Autonomy Spectrum

### Detailed Level Definitions

**Level 1: Gather Info & Await Instruction**
Agent collects information, presents it, waits for user to decide and direct.
```
"Here's what I found about the vendor. What would you like me to do?"
```

**Level 2: Present Options for Decision**
Agent identifies options, analyzes tradeoffs, presents for user choice.
```
"I found three vendors. Here are their pros/cons. Which should I pursue?"
```

**Level 3: Recommend & Get Approval**
Agent recommends one option with reasoning, waits for approval.
```
"I recommend Vendor A because [reasons]. Proceed?"
```

**Level 4: Act & Notify at Checkpoints**
Agent executes with periodic updates at meaningful milestones.
```
"Scheduled the meeting. Sent the agenda. Waiting for responses."
```

**Level 5: Act & Summarize After**
Agent completes task, summarizes what happened.
```
"Done. Scheduled meeting for 3pm, sent agenda to 5 attendees, 3 have confirmed."
```

**Level 6: Act & Notify Only if Asked**
Agent acts, records what happened, surfaces only on inquiry.
```
[No notification] → User: "What happened with that meeting?"
"Scheduled for 3pm. All attendees confirmed."
```

**Level 7: Full Autonomy**
Agent acts without notification. User discovers through outcomes.

### Mapping Domains to Levels

| Domain | Typical Level | Rationale |
|--------|---------------|-----------|
| Information lookup | 1-2 | User defines what's relevant |
| Scheduling (internal) | 4-5 | Low stakes, easily reversible |
| Scheduling (external) | 3 | Reputation at stake |
| Email drafting | 3-4 | User voice matters |
| Email sending (internal) | 4-5 | Low stakes |
| Email sending (external) | 3 | Reputation, irreversible |
| Financial (<$50) | 5-6 | De minimis |
| Financial (>$500) | 2-3 | Meaningful stakes |
| Document creation | 4 | Easy to revise |
| Document publishing | 3 | Irreversible, external |

## Anti-Patterns

### The Autonomy Cliff
```
✗ Settings: [Full Manual] ←—switch—→ [Full Autonomous]
```
No middle ground. Users want nuance, not binary.

### The Configuration Maze
```
✗ 47 individual settings across 12 screens
```
Users can't configure what they haven't experienced. Start simple, add complexity as needed.

### Configuration Amnesia
```
✗ System forgets preferences between sessions
✗ No way to see/export current configuration
```
Preferences are user property. Make them visible, portable.
