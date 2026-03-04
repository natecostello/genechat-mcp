# Re-delegation Patterns

## The Version Control Mental Model

Human intervention is a branch. Return-of-control is a merge.

```
Agent working
     │
     ▼
[Checkpoint] ──────────────────────────────────────────┐
     │                                                 │
Human takes over                                       │
     │                                                 │
  [Branch: Human modifications]                        │
     │                                                 │
Human returns control                                  │
     │                                                 │
  [Merge: Agent incorporates changes]                  │
     │                                                 │
     ▼
Agent continues (with human's modifications integrated)
```

### What the "Merge" Requires

1. **State diff**: What changed during human intervention?
2. **Intent inference**: Why did human make these changes?
3. **Preference update**: What does this reveal about user preferences?
4. **Continuation plan**: How does agent proceed from new state?

## Return-of-Control Protocol

### Human Initiates Return

Human signals completion of intervention:
```
"I've [description of changes]. Continue from here."
"Done editing. Pick up where you left off."
"Fixed the issue. Resume."
```

### Agent Confirms Understanding

Agent summarizes what it understands about human's intervention:
```
"Got it. You [summary of changes]. This means [interpretation].
I'll continue with [next steps]. Anything else before I proceed?"
```

**Critical**: Agent must surface its interpretation. Silent assumptions lead to errors.

### Confirmation Patterns

**Simple intervention**:
```
You: "Changed the meeting to 3pm instead of 2pm."
Agent: "Got it—meeting is now at 3pm. I'll send updated invites. Proceed?"
```

**Complex intervention**:
```
You: "Rewrote the email and added a section on pricing."
Agent: "Got it. You:
  - Changed opening from [x] to [y]
  - Added pricing section with [summary]
  - Kept [unchanged elements]
  
I'll continue with sending to the approval list. 
Should I update my email drafting approach based on your changes?"
```

### Learning from Intervention

Every human intervention is data. Extract preference signals:

| Intervention | Possible Signal |
|--------------|-----------------|
| Changed tone | Tone preference for this context |
| Added information | Information I should include by default |
| Removed content | Verbosity preference |
| Changed recipient | Communication routing preference |
| Changed timing | Scheduling preference |

**Surfacing learned preferences**:
```
"I noticed you added pricing to this email. Should I:
○ Include pricing section in similar emails automatically
○ Ask before adding pricing
○ No change (I'll continue as before)"
```

## Post-Failure Re-delegation

When handoff was triggered by agent error, re-delegation requires trust repair.

### Acknowledgment Before Resumption

Coordinate with trust-calibration Level 5 (Calibration Failure Recovery):

```
"Before I continue: the error that caused handoff was [specific failure].
I've [specific correction/adjustment]. For this type of task going forward,
I recommend [updated protocol]. 

Ready to resume with [next steps]?"
```

### Reset Expectations

User should know what to expect differently:
```
"Previously I [old behavior that failed]. Now I'll [new behavior].
You may see [visible difference] as a result."
```

### Graduated Trust Restoration

Don't immediately return to pre-failure autonomy level:
```
[Before failure]: Act autonomously for calendar
[After failure]: Recommend and get approval for calendar (until track record rebuilds)
```

Surface the change:
```
"Given the scheduling error, I'll ask before making calendar changes
until we've rebuilt confidence. You can adjust this in settings."
```

## Anti-Patterns

### Silent Resumption
```
✗ Agent continues without confirming it understood human's changes
   → Risks operating on wrong assumptions
```

### Interpretation Overconfidence
```
✗ Agent assumes it knows why human made changes
   → Should surface interpretation for confirmation
```

### Preference Overlearning
```
✗ Agent changes behavior dramatically after single intervention
   → Wait for pattern (multiple instances) before adjusting defaults
```

### Trust Amnesia (Post-Failure)
```
✗ Agent resumes at pre-failure autonomy level without acknowledgment
   → Trust should be explicitly rebuilt after errors
```

### Return Path Friction
```
✗ Complex or unclear process for handing back control
   → Users avoid intervening because they fear getting stuck with the task
```

## Design Principles

1. **Make return-of-control as easy as takeover**
   Friction in either direction discourages the handoff pattern we want.

2. **Always confirm interpretation**
   Agent's understanding of human changes might be wrong. Surface it.

3. **Treat intervention as learning opportunity**
   But learn from patterns, not single instances.

4. **Post-failure requires explicit acknowledgment**
   Don't pretend the error didn't happen.

5. **Graduated trust restoration**
   One successful resumption doesn't erase the failure.
