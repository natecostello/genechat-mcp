# Evidence Surfacing Patterns

How much work to show, when, and to whom.

## The Fundamental Tradeoff

**Too little evidence**: User can't evaluate output quality. Creates blind trust or blind rejection.

**Too much evidence**: User is overwhelmed. Creates learned helplessness—they stop reading entirely.

The optimum is context-dependent. These patterns help find it.

## Progressive Disclosure Architecture

### The Three-Layer Model

```
Layer 1: Summary        → What user needs to know/decide
Layer 2: Key Evidence   → 2-4 most important supporting points
Layer 3: Full Trail     → Complete reasoning, all sources, methodology
```

**Implementation principle**: Each layer should be complete at its level. User who stops at Layer 1 has what they need. User who wants depth can drill down.

### Layer 1: Summary

The output itself. Contains:
- Conclusion or recommendation
- Most critical caveat (if any)
- Next action (if applicable)

```
Example (scheduling):
"Meeting confirmed for Thursday 3pm with Alex. Calendar invite sent."

Example (analysis):
"Vendor A is the strongest option. They're 15% more expensive but deliver 
40% faster with better quality scores. Recommend scheduling demo."

Example (research):
"Found 7 relevant precedents. 5 support your position, 2 cut against. 
The balance favors proceeding, but not overwhelmingly."
```

### Layer 2: Key Evidence

Available on request or when stakes warrant proactive surfacing. Contains:
- Primary sources for main claims
- Key data points
- Alternative interpretations considered (if relevant)

```
Example (continuing vendor analysis):
"Key factors:
- Delivery time: Vendor A averages 3 days, B averages 5 days (your deadline needs 4)
- Quality scores: A has 4.8/5 (127 reviews), B has 4.2/5 (89 reviews)  
- Pricing: A is $45K, B is $39K
- Risk: A has been reliable for 3 years, B is newer with less track record"
```

### Layer 3: Full Trail

Available on demand. Contains:
- Complete source list
- Methodology description
- Confidence assessment for each claim
- Edge cases and limitations
- Alternative approaches not taken (and why)

This layer should be expandable/collapsible in UI, never dumped into main output.

## Stakes-Based Evidence Calibration

### Low Stakes (Routine, Reversible, Low Cost)

Examples: scheduling, simple lookups, formatting, routine communications

**Evidence pattern**: Summary only. Source implicit or on hover.

```
Output: "Rescheduled to Thursday 3pm."
Evidence: None proactively surfaced
Available on request: "Moved from original Tuesday slot per your request. 
                      Alex confirmed via email at 2:15pm."
```

### Medium Stakes (Meaningful Impact, Recoverable)

Examples: recommendations, analysis, prioritization, resource allocation

**Evidence pattern**: Summary + key evidence. Full trail available.

```
Output: "I'd prioritize the Johnson deal over the Smith deal this week."

Key evidence (proactively surfaced):
"Johnson has a hard deadline Friday (they mentioned budget expiration).
Smith is interested but their timeline is flexible per last week's call.
Johnson deal value is 2.3x larger."

Full trail (available on expand):
[Email excerpts, call notes, deal values, timeline analysis]
```

### High Stakes (Significant Consequences, Hard to Reverse)

Examples: financial decisions, legal content, medical information, public statements

**Evidence pattern**: Summary + key evidence + explicit uncertainty + verification recommendation

```
Output: "Based on the analysis, the acquisition looks favorable at the offered price."

Key evidence (always shown):
"Revenue projections come from their audited financials (FY23).
Synergy estimates are my modeling based on your cost structure.
Key risk is the pending litigation—outcome could swing value ±15%."

Uncertainty (always shown):
"The litigation outcome is genuinely uncertain. I can't assess probability.
This is the largest source of variance in the valuation."

Recommendation (always shown):
"Have legal counsel assess litigation risk before finalizing.
Consider whether price justifies the downside scenario."
```

## User Expertise Calibration

### Expert Users

Want: raw data, methodology, edge cases, what might go wrong
Don't want: basic explanations, obvious caveats, hand-holding

```
Expert-calibrated output:
"DCF gives $47M, comps give $52M. I weighted 60/40 per your usual approach.
Sensitivity to discount rate is ±8% per 100bps. Main assumption risk is 
the terminal growth rate—I used 2.5% but their industry is volatile."
```

### General Users

Want: implications, recommendations, what to do, key takeaways
Don't want: methodology details, technical jargon, overwhelming options

```
General-calibrated output:
"The company looks fairly valued at the current price.
Main uncertainty is a pending lawsuit that could hurt them.
If you're comfortable with that risk, it's a reasonable buy.
If you want to be conservative, wait until the lawsuit resolves."
```

### Unknown Expertise

Default to general user level. Offer depth:
```
"[General-calibrated output]
I can share the detailed analysis and methodology if helpful."
```

## Evidence UI Patterns

### Inline Citation

For claims that benefit from immediate source access:
```
"The deadline is Friday [email from Sarah, Nov 12]."
"Revenue grew 23% [Q3 Report, p.7]."
```

### Expandable Sections

For detailed evidence that some users want:
```
Summary visible
[▸ Show key evidence]
[▸ Show methodology]  
[▸ Show sources]
```

### Confidence Indicators

Visual signals for claim reliability:
```
● High confidence (verified, authoritative source)
◐ Medium confidence (reliable inference, secondary source)
○ Low confidence (uncertain, requires verification)
```

### Source Quality Markers

```
🔒 Primary source (contract, database, user input)
📄 Secondary source (report, article, summary)
🔗 External source (web, third-party)
💭 Inference (pattern matching, extrapolation)
```

## Evidence Surfacing Anti-Patterns

### The Firehose

Dumping all evidence regardless of relevance:
```
✗ "Here's the recommendation, plus 47 sources, my complete reasoning chain,
   alternative approaches I considered, confidence intervals, methodology notes,
   edge cases, and disclaimers..."
```

User stops reading at sentence 2. All that evidence is wasted.

### The Black Box

No evidence, no way to verify:
```
✗ "The deal looks good. Proceed."
```

User either blindly trusts (risky) or blindly rejects (wasteful).

### The Disclaimer Dump

Evidence buried in legalese:
```
✗ "[solid analysis] This analysis is provided for informational purposes only 
   and should not be construed as financial advice. Past performance does not 
   guarantee future results. Always consult a qualified professional..."
```

User learns to skip the disclaimer. When real uncertainty exists, they miss it.

### Evidence Misalignment

Wrong evidence for the audience:
```
✗ [to executive] "Here's the DCF model with sensitivity tables and 
   assumption documentation..."
   
✗ [to analyst] "The company looks good. You should buy it."
```

## The Evidence Sufficiency Test

Before finalizing output, verify:

1. **Could the user catch a mistake?** If not, more evidence needed.
2. **Is the user drowning in detail?** If so, move evidence to Layer 3.
3. **Does evidence match stakes?** High stakes need proactive evidence.
4. **Does evidence match expertise?** Adjust depth to audience.
5. **Is the path to more detail clear?** User should know how to drill down.
