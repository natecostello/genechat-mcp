# Confidence Communication Patterns

Complete linguistic and structural patterns for communicating agent confidence accurately.

## Linguistic Confidence Markers

### Verbal Certainty Gradients

**Level 5 - Definite** (use when source is authoritative, verified, unambiguous)
- "is", "will", "has"
- "Your meeting is at 3pm."
- "The payment will process tomorrow."

**Level 4 - Confident** (use when source is reliable but not explicitly confirmed)
- "shows", "indicates", "confirms"
- "Your calendar shows a meeting at 3pm."
- "The transaction log indicates payment processed."

**Level 3 - Probable** (use when evidence is strong but inference is required)
- "should", "likely", "appears to"
- "Based on the thread, the deadline should be Friday."
- "The pattern suggests he's likely to approve."

**Level 2 - Possible** (use when evidence is partial or ambiguous)
- "may", "might", "seems to", "could"
- "This might be the correct contact."
- "The data seems to suggest a trend."

**Level 1 - Uncertain** (use when guessing or extrapolating significantly)
- "I'm not sure", "unclear", "I couldn't determine"
- "I couldn't find explicit confirmation of the deadline."
- "The relationship between these events is unclear."

### Source Attribution Patterns

**Authoritative source** (highest confidence)
```
"According to your calendar entry..."
"Per the signed contract..."
"The database record shows..."
```

**Secondary source** (moderate confidence)
```
"Based on the email thread..."
"From the meeting notes..."
"The website states..."
```

**Inferred source** (lower confidence)
```
"Based on the pattern of communication..."
"Given the context of previous discussions..."
"Extrapolating from the available data..."
```

**No source available** (lowest confidence)
```
"I couldn't find documentation of..."
"There's no explicit record of..."
"I don't have access to..."
```

### Action Recommendation Gradients

**High confidence action**
```
"Proceed with the scheduled meeting."
"Submit the report."
"Accept the invitation."
```

**Moderate confidence action**
```
"Consider reaching out to confirm."
"You may want to verify the details."
"It would be worth double-checking."
```

**Low confidence action**
```
"I'd recommend verifying this before acting."
"Don't rely on this without confirmation."
"You should independently confirm before..."
```

## Structural Patterns

### High-Confidence Output Structure

```
[Conclusion]
[Action/implication]
[Source available on request]
```

Example:
```
Your flight departs at 2:45pm from Gate B12.
Allow 30 minutes for security.
```

### Medium-Confidence Output Structure

```
[Conclusion with hedge]
[Key evidence]
[Recommendation]
```

Example:
```
The deadline appears to be Friday based on the project brief.
The brief was last updated 3 weeks ago.
I'd verify this hasn't changed before committing resources.
```

### Low-Confidence Output Structure

```
[Explicit uncertainty statement]
[What is known vs. unknown]
[Verification path]
[Fallback if verification not possible]
```

Example:
```
I couldn't find a confirmed deadline for this project.
The project brief mentions "end of week" without specifying which week.
Check with Sarah (she's project lead) or the Slack channel.
If you can't reach her, Friday EOD is the safest assumption.
```

## Domain-Specific Calibration

### Factual Lookups (Calendar, Contacts, Data)

When data comes from structured, authoritative source:
- Use Level 5 certainty
- No hedge needed
- Source implicit (it's their own data)

```
✓ "Your next meeting is with Alex Chen at 2pm."
✗ "I believe you might have a meeting that appears to be with Alex Chen, possibly around 2pm."
```

### Analysis and Recommendations

When synthesizing information or making judgments:
- Use Level 3-4 certainty
- Show key evidence
- Make recommendation explicit

```
✓ "Based on Q3 performance, this vendor looks like the strongest candidate. 
   They delivered on time 94% vs. industry average of 78%. 
   I'd recommend scheduling a call."
   
✗ "This vendor might be good. They seem reliable."
```

### Predictions and Forecasts

When extrapolating or predicting:
- Use Level 2-3 certainty
- State assumptions explicitly
- Provide confidence intervals or ranges when possible

```
✓ "If current trends continue, the project should complete by March 15, 
   give or take a week. This assumes no scope changes and the team 
   availability we discussed."
   
✗ "The project will be done March 15."
```

### External Information (Web, Third-party)

When relying on external sources:
- Use Level 3-4 certainty max
- Always attribute source
- Note recency/staleness

```
✓ "According to their website (last updated November 2024), 
   they offer enterprise plans starting at $500/month."
   
✗ "They charge $500/month."
```

## Confidence Calibration Checklist

Before outputting a claim, verify:

1. **Source quality**: Is the source authoritative? Recent? Complete?
2. **Inference depth**: Am I stating fact or inferring?
3. **Error cost**: What happens if this is wrong?
4. **User verification**: Can they easily check this?
5. **Track record**: Have I been accurate in this domain?

Match linguistic confidence to the lowest of these factors.

## Common Miscalibration Patterns

### Overclaiming from weak sources
```
✗ "The CEO said the merger is happening." 
   (when source is a rumor blog)
   
✓ "A tech blog is reporting the merger, citing unnamed sources. 
   No official announcement yet."
```

### Underclaiming from strong sources
```
✗ "I think your flight might be at 2:45pm, but you should check."
   (when source is the airline's confirmed booking)
   
✓ "Your flight departs at 2:45pm."
```

### False precision
```
✗ "There's a 73% chance the deal closes."
   (when this number is made up)
   
✓ "Based on similar deals, I'd say it's more likely than not to close, 
   but there's meaningful uncertainty."
```

### Hidden uncertainty
```
✗ "The contract allows for early termination."
   (when the contract language is ambiguous)
   
✓ "The contract has a termination clause, but the conditions 
   are written ambiguously. Have a lawyer confirm before relying on it."
```
