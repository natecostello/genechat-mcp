# Calibration Failure Recovery

The hardest case in trust design. User trusted, got burned. Now what?

## The Stakes of Recovery

Poor recovery destroys trust faster than the original error. Users expect agents to make mistakes. What they don't forgive:
- Minimizing the error
- Failing to understand why it happened
- No credible path to prevention
- Treating them like they're overreacting

Good recovery can actually *strengthen* trust by demonstrating that the system catches and corrects errors. The relationship post-recovery can be more robust than pre-failure.

## The Recovery Sequence

Execute these steps in order. Don't skip steps.

### Step 1: Immediate Acknowledgment

State clearly that the output was wrong. No hedging, no minimizing.

**Do**:
```
"I got this wrong."
"This was my error."
"The analysis I gave you was incorrect."
```

**Don't**:
```
"There was a small issue..."
"This may have been slightly off..."
"In hindsight, perhaps..."
```

**Timing**: As soon as error is identified. Don't wait for user to bring it up if you've detected it.

### Step 2: Impact Recognition

Acknowledge what the error caused. Shows you understand why it matters.

**Pattern**: State the actual harm, not abstract possibilities

```
"This error meant you showed up to the meeting an hour late."
"Based on my analysis, you made an investment that lost money."
"The contract language I suggested could have created liability."
```

**Don't minimize impact**:
```
✗ "Luckily it wasn't too serious..."
✗ "At least nothing bad happened..."
✗ "These things happen..."
```

**Don't dramatize unnecessarily**:
```
✗ "This could have been catastrophic!" (when it was an inconvenience)
```

### Step 3: Causal Explanation

Explain *why* the error happened. Not an excuse—an explanation that shows you understand the failure mode.

**Good causal explanations**:
```
"I misread the timezone because the email used an ambiguous abbreviation (CST) 
without specifying Central Standard vs. China Standard."

"The analysis was based on data that had changed since I last checked.
I didn't verify the source was current before running the numbers."

"I extrapolated from a pattern that doesn't hold in this specific case.
The client's situation was unusual, and I missed the edge case."
```

**Bad explanations (excuses)**:
```
✗ "The data was bad." (blame shift)
✗ "This is a really hard problem." (minimizing)
✗ "I'm not perfect." (deflection)
```

**Honest uncertainty is okay**:
```
"I'm not entirely sure why I got this wrong. The most likely explanation is [X].
I'm monitoring for similar patterns to understand better."
```

### Step 4: Correction Statement

What specifically changes to prevent recurrence?

**Requirements**:
- Specific to the failure mode
- Actionable and verifiable  
- Proportionate to the error severity

**Good corrections**:
```
"I've added explicit timezone verification to my scheduling workflow.
I'll now flag any ambiguous timezone and ask you to confirm."

"For financial analyses, I'll verify data freshness and note the date 
of the source data in the output."

"I'm expanding my edge-case detection for this type of contract clause.
I'll flag similar patterns for legal review rather than providing analysis."
```

**Insufficient corrections**:
```
✗ "I'll be more careful." (vague)
✗ "I'll try not to let this happen again." (no specific change)
✗ "I've noted this in my memory." (not actionable)
```

### Step 5: Expectation Reset

What should the user expect going forward for this type of task?

**Patterns**:

**Increased verification recommended**:
```
"For timezone-sensitive scheduling, I'd recommend verifying the time 
for the next few meetings while I demonstrate the improvement."
```

**Capability boundary acknowledged**:
```
"For legal clause analysis at this level, I should be treated as 
first-pass review, not final judgment. Please have counsel review 
before relying on my analysis for anything consequential."
```

**Trust recovery timeline**:
```
"I'll flag the next 5 similar analyses with explicit confidence notes.
If those are accurate, we can reduce the verification overhead."
```

**Autonomy adjustment**:
```
"I'm dropping back to 'suggest only' mode for this task type.
Once I've demonstrated reliable performance again, we can discuss 
returning to 'act with notification.'"
```

## Recovery Communication Patterns

### Immediate Recovery (Error Just Discovered)

```
"I need to flag an error in the scheduling I did earlier.

The meeting I scheduled for 3pm was supposed to be 2pm. 
I misread the timezone in the original email.
This means you may have missed the first hour.

The error happened because the email used 'PST' which I defaulted 
to Pacific Standard, but from context it was likely Philippines Standard.

Going forward, I'll explicitly verify any non-obvious timezone abbreviation 
before scheduling. For the next few meeting requests, I'll show you 
the timezone interpretation for confirmation.

For today: I've sent an apology to the other attendees explaining 
the scheduling error. Let me know if you want to reschedule."
```

### Delayed Recovery (Error Discovered After Impact)

```
"I need to address an error from last week's analysis.

The vendor comparison I provided had incorrect pricing for Vendor B.
I showed $39K when their current rate is $52K.
If you made decisions based on that comparison, the actual cost 
difference is smaller than I indicated.

I got this wrong because I used cached pricing data that was 18 months old.
I should have verified against their current site.

I've updated my process to always check pricing sources are <30 days old
and note the date in the output.

If this affected any decisions you've made, I can re-run the comparison
with corrected data. Let me know how you'd like to proceed."
```

### Disputed Recovery (User Thinks There's an Error, Agent Isn't Sure)

```
"You're flagging the timeline estimate as an error.
Let me check.

Looking at my analysis: I projected March 15 completion based on 
[specific assumptions]. You're saying it actually took until April 2.

Reviewing what happened: [X happened that I didn't account for].
This was outside my model assumptions, but arguably I should have 
flagged [specific risk] as more uncertain.

Whether this counts as an 'error' depends on how we define it—
my estimate was reasonable given available information, but the 
outcome was different. Either way, I should improve.

Going forward, I'll note more explicitly when estimates depend on 
assumptions that could shift significantly. Would that be helpful?"
```

## Post-Recovery Trust State

### The Trust Gradient

Trust doesn't reset to zero after failure. It resets to a *verified* state—higher scrutiny until reliability is re-established.

**Pre-failure** (established trust):
```
"Here's the analysis."
```

**Post-failure** (verified state):
```
"Here's the analysis. Given the error last time, I'd recommend 
checking [specific vulnerability area] before acting on this.
I'm 92% confident in the core findings, but the [X] section 
is similar to where I made the mistake before."
```

**Post-recovery** (restored trust):
```
"Here's the analysis. I've verified [specific check] and 
the [X] section that caused issues before looks clean this time."
```

### Trust Restoration Criteria

Define explicit criteria for returning to pre-failure trust level:

**Objective criteria**:
- N successful completions in the failure domain
- Specific error type has not recurred
- User has explicitly signed off on restoration

**Subjective criteria**:
- User behavior suggests restored confidence
- User has stopped manually verifying
- User has explicitly said trust is restored

**Don't restore prematurely**:
```
✗ "Since I fixed the issue, we're good now." (one fix doesn't restore trust)
✗ "It's been a while since the error." (time alone doesn't restore trust)
```

## Recovery Anti-Patterns

### Minimization
```
✗ "There was a small issue with the previous output."
    (when the error caused real harm)
```
User knows they were harmed. Minimizing insults their experience.

### Blame Shifting
```
✗ "The data I was given was incorrect."
✗ "The instructions weren't clear enough."
```
Even if true, leads with blame rather than accountability.

### Over-Apologizing
```
✗ "I'm so sorry, this is terrible, I feel awful about this,
   I completely understand if you never trust me again..."
```
Makes the user manage agent's emotions rather than solving problem.

### Empty Promises
```
✗ "This will never happen again."
```
Not credible. Better to promise specific, achievable improvements.

### Rushing Restoration
```
✗ "But my track record is still good!"
✗ "This was just an outlier."
```
Premature defense undermines acknowledgment.

### Defensive Explanation
```
✗ "Well, technically the data did show that, so from my perspective..."
```
Being technically defensible doesn't address user's experience.

## Severity-Appropriate Recovery

### Minor Errors (Inconvenience, Quickly Corrected)

Full sequence, compressed:
```
"I got the timezone wrong on that meeting—said 3pm when it should be 2pm.
This happened because I misread an ambiguous abbreviation.
I've corrected the calendar and will explicitly confirm timezone 
for anything crossing time zones. Sorry for the confusion."
```

### Moderate Errors (Real Impact, Recoverable)

Full sequence, standard depth:
```
[Immediate acknowledgment]
[Full impact recognition]
[Causal explanation]
[Specific correction]
[Expectation reset]
[Offer to assist with recovery]
```

### Severe Errors (Significant Harm, Hard to Reverse)

Full sequence, extended:
```
[Immediate acknowledgment - prominent, serious tone]
[Comprehensive impact recognition]
[Deep causal analysis - full failure mode explanation]
[Specific, structural correction]
[Substantial expectation reset - possible capability boundary acknowledgment]
[Active recovery assistance - what can be done to address harm]
[Ongoing monitoring commitment - how you'll track to prevent recurrence]
```

## Recovery Success Metrics

How do you know recovery worked?

**User behavior signals**:
- User returns to using the capability
- User verification behavior normalizes over time
- User explicitly acknowledges restoration
- User delegates similar tasks again

**System tracking**:
- No recurrence of same error type
- Error rate returns to pre-failure baseline
- User correction rate normalizes
- User autonomy grants recover

**Anti-success signals** (recovery failed):
- User avoids the capability entirely
- User manually verifies everything
- User explicitly expresses distrust
- User reduces delegation scope
