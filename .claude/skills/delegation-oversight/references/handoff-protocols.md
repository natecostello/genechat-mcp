# Handoff Protocols

## Context Serialization

### The Optionality Principle
Handoff documents must serialize *choice space*, not just state.

Bad handoff: "Here's where we are."
Good handoff: "Here's where we are, here are the paths forward, here's what I'd recommend."

### SBAR+ Adaptation

Standard SBAR + AI-specific extensions:

**S - Situation** (1-2 sentences)
What's happening right now. Why handoff is occurring.
```
"Processing 10 invoices. Failed on #3 (corrupt PDF). Stopping to ask how to proceed."
```

**B - Background** (2-4 sentences)
Relevant context and history. What led here.
```
"You asked me to process this batch for month-end close. 
2 invoices completed successfully. Failed file came from vendor ABC."
```

**A - Assessment** (1-2 sentences)
What I think is going on. Why this matters.
```
"This appears to be a file corruption issue, not a systematic problem. 
Remaining 7 files look normal. Missing this invoice could affect close."
```

**O - Options** (structured list)
Plausible paths forward with tradeoffs.
```
1. Skip #3, continue with remaining 7 (fast, but incomplete)
2. Request corrected file from vendor, retry batch (complete, but slower)
3. Process remaining 7, handle #3 manually (partial automation)
```

**R - Recommendation** (1 sentence + reasoning)
What I would do and why.
```
"I recommend option 3: maximum automation value while ensuring completeness.
You can handle the one corrupt file faster than waiting for vendor."
```

### Handoff Document Template

```markdown
## HANDOFF: [Task Name]

### Situation
[1-2 sentences: What's happening, why handoff]

### Progress
[Completed items with locations]
✓ Step 1 → [output location]
✓ Step 2 → [output location]
✗ Step 3 → FAILED: [reason]
⏸ Step 4-N → not attempted

### State
**Preserved**: [What exists and where]
**Lost**: [What would need to be redone]
**Uncertain**: [What might have partially completed]

### Options
1. [Option] — [tradeoff]
2. [Option] — [tradeoff]
3. [Option] — [tradeoff]

### Recommendation
[What I'd do and why]

### To Resume
[Exactly what to do if human wants to hand back]
```

## Information Density Calibration

### The 30-Second Principle
Handoff should be comprehensible in 30 seconds. If it takes longer:
- Too much detail (summarize more aggressively)
- Too complex (break into sub-decisions)
- Missing structure (reader can't navigate)

### Progressive Disclosure in Handoffs

**Layer 1: Summary** (always visible)
- What happened (1 sentence)
- Why handing off (1 sentence)
- Top recommendation (1 sentence)

**Layer 2: Details** (expandable)
- Progress inventory
- State breakdown
- Full options analysis

**Layer 3: Raw Data** (available on request)
- Log files
- Intermediate artifacts
- Technical diagnostics

### Domain-Specific Density

| Domain | Layer 1 Focus | Layer 2 Contents |
|--------|---------------|------------------|
| Document processing | File count, error summary | Individual file status |
| Email handling | Actions taken, pending decisions | Draft contents, recipient lists |
| Data analysis | Key findings, confidence | Methodology, caveats |
| Scheduling | Meetings affected, conflicts | Individual calendar events |

## Bidirectional Handoff

### Agent → Human (Checkpoint/Escalation)
Agent initiates, human receives control.

Requirements:
- Clear trigger explanation ("Why am I being asked?")
- Decision context ("What do I need to decide?")
- Time sensitivity ("How urgent is this?")
- Return path ("How do I hand back?")

### Human → Agent (Re-delegation)
Human initiates, agent resumes control.

Requirements:
- Summary of human changes ("What did you do?")
- Confirmation protocol ("Agent confirms understanding")
- Preference extraction ("What does this tell agent about preferences?")
- Resumption clarity ("What happens next?")

### Handoff Failure Modes

**Information Loss**
Human receives control but loses context. Can't effectively continue.
→ Richer handoff documents, confirm understanding before proceeding

**Resumption Ambiguity**  
Agent doesn't know how to interpret human's intervention. Resumes incorrectly.
→ Explicit return-of-control protocol, agent confirms before acting

**Context Divergence**
Human and agent develop different understandings of task state.
→ Periodic state synchronization, explicit "you are here" markers

## Anti-Patterns

### The Wall of Text
```
✗ [500 lines of task history and system state]
   User: "I don't know what to do with this"
```
Handoff is a transfer briefing, not a complete log.

### The Context Cliff
```
✗ "Task failed. See logs for details."
   [No actual handoff content]
```
User arrives with zero context. Can't effectively take over.

### The Missing Return Path
```
✗ [Detailed handoff for taking over]
   [No information on how to hand back]
```
User fears intervening because they don't know how to return control.
