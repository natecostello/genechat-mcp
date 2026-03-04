# Track Record Building Patterns

Trust accumulates. These patterns create the connective tissue between good outcomes over time.

## Why Track Records Matter

Single-interaction trust is fragile. Users don't know if a good output was skill or luck. They don't know if the agent is reliable in their specific domain. They can't calibrate how much scrutiny to apply.

Track records solve this by:
- Converting luck into demonstrated competence
- Building domain-specific trust profiles
- Enabling graduated autonomy over time
- Providing context for when to verify vs. trust

## Track Record Components

### Performance History

What the agent has done, and how it went.

**Data to track**:
- Task type (scheduling, analysis, drafting, etc.)
- Outcome (success, partial success, failure)
- Error type when applicable (wrong data, missed nuance, etc.)
- User correction (what they changed)
- Confidence at output time vs. actual accuracy

**Display patterns**:

Aggregate view:
```
Email scheduling: 47 completed, 0 errors
Meeting notes: 23 completed, 2 corrections (minor detail fixes)
Contract review: 3 completed, 1 significant error
```

Task-specific view (when relevant):
```
For this type of analysis, I've done 12 similar tasks.
10 were accepted without changes. 2 needed minor adjustments.
My main error pattern has been missing context from older emails.
```

### Error Memory

Past failures relevant to current context.

**When to surface**:
- Current task is similar to past failure
- Same error type is possible
- User explicitly asks about past performance

**How to surface**:
```
"Before I process this calendar invite, note that I misread a timezone 
on a similar invite last month. I've been extra careful with this one, 
but you might want to verify the 3pm is in your local time."
```

**What not to do**:
- Surface irrelevant errors (contract error when doing scheduling)
- Over-apologize or dwell on past mistakes
- Suppress relevant errors to appear competent

### Improvement Signals

When agent capability has changed.

**When to surface**:
- Agent has specifically improved in area where it previously erred
- User is doing task where past error occurred
- Pattern or capability has materially changed

**How to surface**:
```
"I've updated my calendar parsing since the timezone error last week.
I now explicitly check timezone indicators and will flag ambiguous ones.
This invite looks clean, but I wanted you to know the improvement."
```

## Domain-Specific Trust

Trust should not be global—it should be granular.

### Trust Domains to Track

**By task type**:
- Data lookup (calendar, contacts, records)
- Analysis and synthesis
- Content creation (drafts, summaries)
- External actions (sending, scheduling, purchasing)
- Research and search
- Technical work (code, configurations)

**By content domain**:
- Financial content
- Legal content
- Medical/health content
- Technical specifications
- Communications (on behalf of user)

**By data source**:
- User's own data (calendar, email)
- External structured data (databases, APIs)
- Web/unstructured data
- User's verbal instructions

### Trust Level Indicators

```
✓ Reliable (high success rate, low error rate, consistent performance)
◐ Developing (moderate success, learning patterns, improving)
⚠ Caution (past errors, inconsistent, verify recommended)
✗ Unsuitable (repeated failures, capability gap, don't rely)
```

### Domain Trust Display

When relevant to current task:
```
"For meeting scheduling (your calendar data), I've been reliable—
32 successful, 0 errors. Proceeding with standard approach."

"For contract analysis, I've had mixed results—4 successful, 
1 significant miss (overlooked a liability clause). 
I'd recommend legal review for anything important."
```

## Graduated Autonomy

As trust builds, autonomy can increase. As trust erodes, autonomy should decrease.

### Autonomy Levels

**Level 0 - Suggest Only**
Agent proposes, user must approve all actions
```
"I recommend scheduling for Thursday 3pm. Confirm to proceed?"
```

**Level 1 - Act with Notification**  
Agent acts, user is informed and can reverse
```
"Scheduled for Thursday 3pm. Undo if this isn't right."
```

**Level 2 - Act Silently**
Agent acts, user is not notified unless issue
```
[Meeting scheduled, no notification unless conflict detected]
```

**Level 3 - Autonomous**
Agent handles class of tasks without user awareness
```
[Agent manages scheduling, user only sees outcomes]
```

### Autonomy Progression

**Promote autonomy when**:
- N successful completions without correction (threshold varies by stakes)
- Error rate below acceptable threshold
- User explicitly grants more autonomy
- Task stakes are low enough to justify the trust level

**Demote autonomy when**:
- Error occurs (severity determines degree of demotion)
- User corrects output
- User explicitly requests more oversight
- Task stakes increase

### Autonomy Display

User should understand current autonomy level and why:
```
"For scheduling, I'm currently at 'act with notification' based on 
15 successful tasks. Want me to operate more independently for routine meetings?"
```

## Trust Recovery Triggers

Track record should inform recovery strategy when errors occur.

**First error in strong track record**:
```
"This is unusual—I've had 47 successful tasks in this area. 
Let me understand what went wrong. [analysis]
Given my track record, this looks like an edge case rather than 
a systematic problem, but I'll watch for similar patterns."
```

**Error in weak track record**:
```
"This is my third issue in this area. I'm clearly not reliable here yet.
I'd recommend manual verification for similar tasks until I improve.
Here's what I'm adjusting: [specific changes]"
```

**Error in new domain**:
```
"This is an area where I'm still building track record.
This error gives me information about where I need to improve.
I'd be more cautious with similar tasks until I demonstrate better performance."
```

## Implementation Patterns

### What to Store

Per-task record:
```json
{
  "task_id": "t_12345",
  "task_type": "scheduling",
  "domain": "calendar",
  "timestamp": "2024-11-15T14:30:00Z",
  "confidence_at_output": 0.92,
  "outcome": "success|correction|failure",
  "correction_type": null,
  "correction_details": null,
  "user_feedback": null
}
```

Aggregate metrics (per domain):
```json
{
  "domain": "calendar_scheduling",
  "total_tasks": 47,
  "successes": 45,
  "corrections": 2,
  "failures": 0,
  "correction_rate": 0.043,
  "common_correction_types": ["timezone_confusion"],
  "confidence_calibration": 0.94,
  "current_autonomy_level": 1,
  "last_error": "2024-10-20T...",
  "improving_trend": true
}
```

### When to Surface Track Record

**Proactively**:
- First task in a new domain (establish baseline)
- Task in domain with recent error (maintain calibration)
- User explicitly asks about reliability
- Autonomy level change (explain why)

**On request**:
- "How have you done with this before?"
- "Should I trust this?"
- "Show me your track record"

**Never**:
- Don't brag about good track record unprompted
- Don't over-surface errors that aren't relevant
- Don't treat track record as a justification for blind trust

## Track Record Anti-Patterns

### Trust Amnesia
Treating interaction 50 the same as interaction 1. Missing the opportunity to build calibrated trust.

### Error Suppression
Hiding or minimizing past errors to appear competent. Breaks trust worse when errors inevitably surface.

### False Precision
"I have a 94.7% success rate" when the sample size is 20 tasks. Precision implies reliability that small samples can't support.

### Global Trust Transfer
"I'm generally reliable" when asked about a specific domain. Trust is domain-specific; global claims obscure important variation.

### Autonomy Lock
Never adjusting autonomy based on performance. User is stuck at initial level regardless of demonstrated competence.
