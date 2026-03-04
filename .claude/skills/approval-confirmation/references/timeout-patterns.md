# Time-Bounded Approval Patterns Reference

Timing algorithms, default logic, and state preservation for approval timeouts.

## Timeout Architecture

Every time-bounded approval has four components:

```
┌───────────────────────────────────────────────────────────┐
│                    TIMEOUT ANATOMY                        │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  DEADLINE           When approval expires                 │
│  ────────           "Respond by 3:00 PM"                  │
│                                                           │
│  DEFAULT            What happens on expiry                │
│  ───────            "Will save as draft"                  │
│                                                           │
│  RATIONALE          Why there's a deadline                │
│  ─────────          "Client expects EOD response"         │
│                                                           │
│  EXTENSION          How to get more time                  │
│  ─────────          "Need more time? [Extend 1 hour]"     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

## Deadline Display Patterns

### Absolute Time
Best when: User can reference against their calendar.

```
⏱ Approval needed by 3:00 PM EST
```

### Countdown
Best when: Urgency is key; user is currently active.

```
⏱ 47 minutes remaining
```

### Relative with Absolute
Best of both—relative for urgency, absolute for planning.

```
⏱ 47 minutes (expires 3:00 PM)
```

### Progress Bar
Visual urgency indicator.

```
⏱ [████████████░░░░░░░░░░░░░] 47 min remaining
              ▲
         You are here
```

### Urgency Thresholds

| Time Remaining | Display Treatment |
|----------------|-------------------|
| >1 hour | Static timestamp |
| 15-60 min | Countdown, neutral color |
| 5-15 min | Countdown, warning color |
| <5 min | Countdown, critical color, pulse/animation |

## Default Behavior Matrix

The right default depends on stakes and reversibility:

```
                    │ Reversible │ Irreversible │
────────────────────┼────────────┼──────────────┤
   Low Stakes       │  Proceed   │    Cancel    │
────────────────────┼────────────┼──────────────┤
   High Stakes      │  Cancel    │   Escalate   │
────────────────────┴────────────┴──────────────┘
```

### Default: Proceed
Action is low-risk and recoverable.

```
If you don't respond by 3:00 PM:
→ Email will be sent automatically
→ You can recall within 30 seconds after send
```

**When to use**:
- Routine actions with easy undo
- User has approved similar before
- Delay would cause meaningful harm

### Default: Cancel
Action should not happen without explicit approval.

```
If you don't respond by 3:00 PM:
→ Email will be saved as draft (not sent)
→ You'll be reminded tomorrow at 9:00 AM
→ Draft remains editable
```

**When to use**:
- High-stakes actions
- Irreversible consequences
- User hasn't established pattern

### Default: Escalate
Decision too important to cancel silently.

```
If you don't respond by 3:00 PM:
→ Will escalate to manager@company.com
→ They will see: [summary of action and context]
→ You'll be notified when they respond
```

**When to use**:
- Critical deadlines
- External commitments
- Organizational risk

### Default: Partial
Some items can proceed; others need approval.

```
If you don't respond by 3:00 PM:
→ 4 internal emails will send (routine)
→ 1 external email will save as draft (requires review)
```

## Timeout Communication Timeline

### Standard Timeline (non-urgent)

```
T+0:00   Initial request
         "Ready for approval"
         
T+4:00   First reminder (if no response)
         "Still waiting for your approval on [action]"
         
T+8:00   Second reminder + warning
         "Approval expires in 16 hours. [Default behavior] if no response."
         
T+24:00  Deadline
         Execute default behavior
         
T+24:01  Notification of outcome
         "[Action] was [saved/sent/escalated] per timeout default."
```

### Urgent Timeline

```
T+0:00   Initial request
         "Urgent: Approval needed by [time]"
         
T-15:00  Warning (15 min before deadline)
         "Deadline in 15 minutes. [Default behavior] if no response."
         
T-5:00   Final warning (5 min before deadline)
         "FINAL: 5 minutes remaining. [Default behavior] about to execute."
         
T+0:00   Deadline
         Execute default behavior
         
T+0:01   Notification
         "[Action] was [saved/sent/escalated]."
```

### Deadline Arrived (User Present)

If user is actively viewing when deadline arrives:

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Deadline reached                                     │
│                                                         │
│ Choose now:                                             │
│                                                         │
│ [Approve] [Reject] [Extend 1 hour]                      │
│                                                         │
│ Auto-executing default in: 30 seconds                   │
│ Default: Save as draft                                  │
│                                                         │
│ [██████████░░░░░░░░░░░░░░░░░░░░]                        │
└─────────────────────────────────────────────────────────┘
```

## Extension Patterns

### Simple Extension

```
Need more time?
[Extend 1 hour] [Extend to tomorrow]
```

### Extension with Justification

```
Extend deadline?

Original deadline: 3:00 PM (client expects EOD response)

○ Extend 1 hour (new deadline: 4:00 PM)
○ Extend to end of day (new deadline: 6:00 PM)
○ Extend to tomorrow (new deadline: Oct 16, 9:00 AM)
  └── ⚠️ This may disappoint client expectation

[Extend] [Decide now instead]
```

### Extension Limits

```
This approval has been extended twice.

To prevent indefinite delay:
• Maximum one more extension available
• Or: Decide now

[Final extension (+1 hour)] [Decide now] [Cancel action]
```

## Escalation Patterns

### Pre-Escalation Warning

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Approval will escalate in 2 hours                    │
│                                                         │
│ If you don't respond:                                   │
│ • This request will go to: manager@company.com          │
│ • They will see: Action summary and deadline context    │
│ • You will be CC'd on their decision                    │
│                                                         │
│ [Respond now] [Let it escalate] [Extend deadline]       │
└─────────────────────────────────────────────────────────┘
```

### Escalation Notification (to escalation target)

```
┌─────────────────────────────────────────────────────────┐
│ 🔔 Escalated approval request                           │
│                                                         │
│ From: alice@company.com (did not respond by deadline)   │
│                                                         │
│ Action: Send email to client@external.com               │
│ Context: Client follow-up on Q4 proposal                │
│ Original deadline: Oct 15, 3:00 PM                      │
│                                                         │
│ Your options:                                           │
│ [Approve] [Reject] [Return to Alice] [View full context]│
└─────────────────────────────────────────────────────────┘
```

### Escalation Notification (to original requester)

```
┌─────────────────────────────────────────────────────────┐
│ 📤 Approval escalated                                   │
│                                                         │
│ Your approval for [action] timed out.                   │
│ Escalated to: manager@company.com                       │
│                                                         │
│ You can still:                                          │
│ [Respond before they do] [Add context for them]         │
│                                                         │
│ You'll be notified when they decide.                    │
└─────────────────────────────────────────────────────────┘
```

## State Preservation

### What to Preserve on Timeout

| Component | Preserve? | Notes |
|-----------|-----------|-------|
| Draft artifact | Yes | User may want to complete later |
| User's edits | Yes | Don't lose their work |
| Context | Yes | Why this was created |
| Agent reasoning | Yes | Useful for retry |
| Pending modifications | Yes | User's deselections, parameter changes |
| Approval history | Yes | Track record |

### Preserved State Display

```
┌─────────────────────────────────────────────────────────┐
│ 💾 Approval timed out - work preserved                  │
│                                                         │
│ What was saved:                                         │
│ ├── Draft email (in Drafts folder)                      │
│ ├── Your edits (subject line change)                    │
│ ├── Attachment (Q4_Report.xlsx)                         │
│ └── Context: Reply to client's Oct 10 message           │
│                                                         │
│ Resume:                                                 │
│ [Resubmit for approval] [Edit draft] [Send manually]    │
│                                                         │
│ Or start fresh:                                         │
│ [Ask agent to try again] [Cancel entirely]              │
└─────────────────────────────────────────────────────────┘
```

### State Recovery on Return

```
┌─────────────────────────────────────────────────────────┐
│ 📂 Returning to saved approval                          │
│                                                         │
│ This approval expired Oct 15 at 3:00 PM.                │
│ Your draft and edits were preserved.                    │
│                                                         │
│ Since then:                                             │
│ • Client has not followed up                            │
│ • No other emails in this thread                        │
│ • Original context still relevant                       │
│                                                         │
│ [Resume approval] [Review changes since] [Start over]   │
└─────────────────────────────────────────────────────────┘
```

## Timeout Rationale Patterns

### External Commitment

```
Deadline: Oct 15, 3:00 PM

Why: Client expects response by end of day.
     (Based on: "I'll get back to you by EOD" in your Oct 14 email)
```

### Internal Process

```
Deadline: Oct 15, 5:00 PM

Why: Invoice must be submitted before monthly close.
     (Finance deadline: Oct 15 5:00 PM)
```

### Inferred Urgency

```
Deadline: 1 hour from now

Why: Email is reply to message received 3 hours ago.
     Typical response time for this contact: 2 hours.
     (You can adjust this expectation in settings)
```

### Agent-Proposed

```
Deadline: Oct 16, 9:00 AM

Why: No specific deadline detected.
     Default: 24 hours for non-urgent approvals.
     (You can approve now, extend, or set custom deadline)
```

## Notification Channel Selection

| Urgency | Primary Channel | Fallback |
|---------|-----------------|----------|
| Non-urgent | In-app notification | Daily digest email |
| Moderate | Push notification | Email within 1 hour |
| Urgent | Push + SMS | Email + in-app alert |
| Critical | All channels simultaneously | Phone call escalation |

### User Preferences Override

```
Approval notifications:
├── Non-urgent: [In-app only ▾]
├── Moderate: [Push notification ▾]
├── Urgent: [Push + email ▾]
└── Critical: [All channels ▾]

Quiet hours: [10 PM - 8 AM ▾]
└── During quiet hours: [Queue until morning ▾]
```

## Edge Cases

### User Responds After Timeout

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ This approval has expired                            │
│                                                         │
│ Outcome: Email was saved as draft (default behavior)    │
│ Expired: 2 hours ago                                    │
│                                                         │
│ You can still:                                          │
│ [Send now] [Edit first] [Keep as draft]                 │
└─────────────────────────────────────────────────────────┘
```

### Escalation Target Also Times Out

```
Primary: alice@company.com (timed out)
Escalation: manager@company.com (also timed out)

Next action:
○ Escalate to: [director@company.com ▾]
○ Execute safe default: Save as draft
○ Cancel action entirely

[Proceed]
```

### Conflicting Responses (User + Escalation Target)

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Conflicting responses                                │
│                                                         │
│ You: Approved (just now)                                │
│ manager@company.com: Rejected (10 minutes ago)          │
│                                                         │
│ Manager's rejection takes precedence per policy.        │
│                                                         │
│ Action was NOT executed.                                │
│                                                         │
│ [View manager's note] [Request override] [Accept]       │
└─────────────────────────────────────────────────────────┘
```

### Network Failure at Deadline

```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Could not execute timeout default                    │
│                                                         │
│ Deadline passed, but execution failed:                  │
│ Error: Network unavailable                              │
│                                                         │
│ Your approval is still pending.                         │
│ Will retry when connection restored.                    │
│                                                         │
│ [Retry now] [Change to different default] [Cancel]      │
└─────────────────────────────────────────────────────────┘
```

## Timeout Configuration

### System Defaults

```
Default timeout by action type:
├── Email (internal): 24 hours → Save draft
├── Email (external): 12 hours → Save draft
├── Calendar (self): 4 hours → Create event
├── Calendar (others): 12 hours → Save draft
├── Document edit: 24 hours → Save changes
├── Financial: No timeout → Must explicitly approve
└── Publishing: No timeout → Must explicitly approve
```

### User Customization

```
Your timeout preferences:

Email approvals:
├── Timeout: [24 hours ▾]
├── Default on timeout: [Save as draft ▾]
└── Escalate to: [None ▾]

Calendar approvals:
├── Timeout: [4 hours ▾]
├── Default on timeout: [Create event ▾]
└── Escalate to: [assistant@company.com ▾]

[Save preferences] [Reset to system defaults]
```
