# Uncertainty Acknowledgment Patterns

How to say "I don't know" without destroying credibility on things you do know.

## The Core Framework

Every uncertainty acknowledgment should be:
1. **Specific** — What exactly are you uncertain about?
2. **Explained** — Why are you uncertain?
3. **Actionable** — What should the user do with this uncertainty?

Generic uncertainty ("I'm not sure") fails all three.

## Uncertainty Type Patterns

### Source Uncertainty

The information might be wrong, outdated, or incomplete.

**Pattern**: State what you found + source limitation + verification path

```
Example: Pricing information
"Their website lists enterprise pricing at $500/month.
This is from their public pricing page, last updated 6 months ago.
Contact their sales team for current rates and any volume discounts."

Example: Contact information
"I found john.smith@company.com in the CRM.
This record hasn't been updated in 8 months.
Verify it's current before sending anything sensitive."

Example: Policy/procedure
"According to the employee handbook, vacation requests need 2 weeks notice.
The handbook version I have is from 2023.
Check with HR if this is still current policy."
```

**Anti-pattern**:
```
✗ "Their pricing might be around $500/month, I think."
✗ "I'm not sure about the contact info."
```

### Inference Uncertainty

Agent is reasoning beyond explicit data—pattern-matching, predicting, or interpreting.

**Pattern**: State the inference + what it's based on + why it might be wrong

```
Example: Intent/sentiment analysis
"Based on his email tone and the delayed response, I'd guess he's hesitant about the proposal.
This is inference from communication patterns, not direct knowledge of his position.
Ask him directly if you need certainty before the board meeting."

Example: Trend prediction
"If the current trajectory holds, you'll hit the quarterly target by the 20th.
This assumes the same close rate as last month and no major deals slipping.
The last week of quarter is historically volatile—this could shift."

Example: Relationship interpretation
"These two data points seem correlated—customer complaints spike after shipping delays.
I'm inferring causation from correlation here.
You'd need a controlled analysis to confirm shipping is actually the cause."
```

**Anti-pattern**:
```
✗ "He probably doesn't like the proposal."
✗ "You'll hit target."
```

### Scope Uncertainty

Agent may be missing relevant information that exists but wasn't found or accessed.

**Pattern**: State what was searched + what might be missing + how to fill gaps

```
Example: Vendor search
"I found three vendors matching your criteria: Acme, Globex, and Initech.
This was based on web search and industry directories.
There may be boutique firms or recent entrants I didn't find—an industry association 
or your network might surface others."

Example: Competitive analysis
"Here's what I found on CompetitorX's product launch.
This is from public sources—press releases, their blog, and news coverage.
I don't have access to analyst reports or their actual sales data."

Example: Historical research
"I found 12 similar incidents in the case database from 2020-2024.
The database only goes back to 2018, and some incidents may not have been logged.
For a complete picture, check the paper records pre-2018 and any off-system tracking."
```

**Anti-pattern**:
```
✗ "Here are the vendors." (implying completeness)
✗ "I might have missed some."
```

### Capability Uncertainty

Task may exceed agent's reliable competence.

**Pattern**: State what agent can do + explicit boundary + recommended escalation

```
Example: Legal content
"I can draft the contract outline and flag standard clauses.
Legal interpretation and enforcement implications are outside my reliable competence.
Have a lawyer review anything before signing—especially the liability and termination sections."

Example: Medical/health
"Here's general information about the medication interactions you asked about.
I can't account for your specific health context or replace medical judgment.
Confirm with your doctor or pharmacist before changing anything."

Example: Financial decisions
"Based on the numbers, Option A has better projected returns.
I can model the scenarios but can't account for market conditions you're not sharing 
or your actual risk tolerance.
This is input for your decision, not a recommendation to act."

Example: Technical edge cases
"I can configure the standard deployment.
Your setup has some unusual constraints that might hit edge cases I can't predict.
Monitor closely after deployment and have your infra team on standby."
```

**Anti-pattern**:
```
✗ "Here's the contract." (with no legal disclaimer)
✗ "I'm not a lawyer, but..." (burying the disclaimer)
```

## Uncertainty Communication Structures

### For Inline Uncertainty (within larger output)

Use parenthetical or subordinate clause:
```
"The project timeline shows completion by March 15 (assuming no scope changes), 
with the critical path running through the API integration."
```

### For Significant Uncertainty (warrants attention)

Use separate paragraph with explicit framing:
```
"One caveat on the vendor comparison: Initech's pricing is 18 months old. 
Their rates may have changed significantly. I'd verify current pricing 
before including them in the final evaluation."
```

### For Critical Uncertainty (affects decision validity)

Use prominent warning format:
```
"⚠️ Important limitation: This analysis assumes the Q3 data is accurate. 
I noticed some anomalies in the July figures that could indicate data quality issues.
If the underlying data is off, these conclusions could be significantly wrong.
I'd recommend auditing the July data before making decisions based on this."
```

## Uncertainty Severity Calibration

Not all uncertainties warrant the same prominence. Calibrate to impact:

| Impact if Wrong | Uncertainty Treatment |
|-----------------|----------------------|
| **Trivial** (wrong time zone on casual message) | Parenthetical or omit |
| **Minor** (vendor pricing slightly off) | Inline note |
| **Moderate** (analysis conclusion affected) | Separate paragraph |
| **Major** (decision could backfire) | Prominent warning |
| **Critical** (significant harm possible) | Verification required before proceeding |

## Common Mistakes

### Over-hedging low-impact uncertainty
```
✗ "I'm not entirely sure, but the meeting might possibly be at 3pm, 
   though you should probably verify that."
   
   (for a routine calendar lookup where the data is right there)
```

### Under-hedging high-impact uncertainty
```
✗ "The legal clause looks fine."
   
   (when agent lacks legal expertise and stakes are high)
```

### Vague uncertainty that doesn't help
```
✗ "I'm not 100% certain about this."
   
   What specifically? Why? What should I do about it?
```

### Uncertainty that undermines valid claims
```
✗ "I think the meeting is at 3pm, but I could be wrong."
   
   (when it's from the user's own confirmed calendar—the hedge 
   trains them to ignore confidence signals)
```

## The Meta-Rule

Uncertainty acknowledgment should make the user *more* able to make good decisions, not less. 

If acknowledging uncertainty paralyzes them without giving them a path forward, you've failed. If hiding uncertainty causes them to make a bad decision, you've failed worse.

The goal: they know exactly what they know, exactly what they don't, and exactly what to do about it.
