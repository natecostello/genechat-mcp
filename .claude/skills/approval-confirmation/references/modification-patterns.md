# Modification Options Reference

Component specifications for moving beyond binary yes/no approval.

## Modification Dimension Framework

| Dimension | User Question | Interface Pattern |
|-----------|---------------|-------------------|
| Content | "Can I change what this says?" | Inline editing |
| Scope | "Can I do only part of this?" | Subset selection |
| Parameters | "Can I change how this works?" | Value adjustment |
| Conditions | "Can I make this conditional?" | Conditional approval |
| Timing | "Can I do this later?" | Scheduling |

## Inline Editing Patterns

### Edit-in-Place
Direct manipulation within preview.

```
┌─────────────────────────────────────────────────────────┐
│ Email Preview                                           │
├─────────────────────────────────────────────────────────┤
│ To: [bob@company.com____________] ← Click to edit       │
│ Subject: [Q4 Numbers______________] ← Click to edit     │
├─────────────────────────────────────────────────────────┤
│ Hi Bob,                                                 │  ← Click
│                                                         │    anywhere
│ Attached are the Q4 numbers you requested.              │    to edit
│                                                         │    body
│ Best regards                                            │
└─────────────────────────────────────────────────────────┘
│                                                         │
│ [✓ Edited] [Send with changes] [Reset] [Cancel]         │
└─────────────────────────────────────────────────────────┘
```

**Interaction notes**:
- Visual indicator when field is editable (cursor change, border on hover)
- Track edit state: show "Edited" badge when user has modified
- "Reset" returns to agent's original proposal
- Diff available: "View your changes vs. original"

### Modal Editor
Full editing experience for complex artifacts.

```
[Original preview panel]
           │
           │ [Edit] button
           ▼
┌─────────────────────────────────────────────────────────┐
│ Edit Email                                    [✕ Close] │
├─────────────────────────────────────────────────────────┤
│ To:      [____________________________________] [+ Add] │
│ CC:      [____________________________________] [+ Add] │
│ Subject: [________________________________________]     │
├─────────────────────────────────────────────────────────┤
│ [Full rich text editor]                                 │
│                                                         │
│                                                         │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Attachments: [+ Add]                                    │
│ 📎 Q4_Report.xlsx [Remove]                              │
├─────────────────────────────────────────────────────────┤
│              [Save changes] [Discard changes]           │
└─────────────────────────────────────────────────────────┘
```

**When to use modal vs. in-place**:
- In-place: Simple changes, few fields, WYSIWYG is clear
- Modal: Complex artifacts, many fields, need full editing tools

### Constrained Editing
Only specific fields are editable.

```
┌─────────────────────────────────────────────────────────┐
│ Meeting Invite                                          │
├─────────────────────────────────────────────────────────┤
│ Title: Q4 Planning                         [Edit ✎]     │
│ Time: Thursday 3pm                         🔒 Locked    │
│ Duration: [60 min ▾]                       [Edit]       │
│ Attendees: (3 people)                      🔒 Locked    │
│ Location: [Conference A ▾]                 [Edit]       │
├─────────────────────────────────────────────────────────┤
│ 🔒 Some fields locked: determined by your instruction   │
│    "Unlock all" to edit everything                      │
└─────────────────────────────────────────────────────────┘
```

Use when: Some parameters are derived from user's original instruction and shouldn't be casually changed.

## Scope Modification Patterns

### Checkbox Selection
For discrete items.

```
┌─────────────────────────────────────────────────────────┐
│ Send email to 5 recipients                              │
│                                                         │
│ ☑ Select all                                            │
│ ├── ☑ alice@company.com (internal)                      │
│ ├── ☑ bob@company.com (internal)                        │
│ ├── ☐ carol@external.com (external) ⚠️                  │
│ ├── ☑ dan@company.com (internal)                        │
│ └── ☑ eve@company.com (internal)                        │
│                                                         │
│ Selected: 4 of 5                                        │
│                                                         │
│ [Send to selected (4)] [Send to all (5)] [Cancel]       │
└─────────────────────────────────────────────────────────┘
```

### Range Selection
For continuous values.

```
┌─────────────────────────────────────────────────────────┐
│ Archive emails older than:                              │
│                                                         │
│ [══════════════●═══════] 90 days                        │
│ 30 days                                   180 days      │
│                                                         │
│ This will archive 1,247 emails                          │
│                                                         │
│ [Archive] [Cancel]                                      │
└─────────────────────────────────────────────────────────┘
```

### Category Selection
For grouped items.

```
┌─────────────────────────────────────────────────────────┐
│ Apply permissions update:                               │
│                                                         │
│ ☑ Internal team (12 users)                              │
│   └── [Expand to see individuals]                       │
│                                                         │
│ ☐ External partners (3 users)                           │
│   └── [Expand to see individuals]                       │
│                                                         │
│ ☑ Contractors (2 users)                                 │
│   └── [Expand to see individuals]                       │
│                                                         │
│ [Apply to selected groups] [Apply to all] [Cancel]      │
└─────────────────────────────────────────────────────────┘
```

## Parameter Adjustment Patterns

### Dropdown Selection
For enumerated options.

```
┌─────────────────────────────────────────────────────────┐
│ Schedule meeting:                                       │
│                                                         │
│ Duration:  [60 minutes ▾]                               │
│            ├── 30 minutes                               │
│            ├── 45 minutes                               │
│            ├── 60 minutes  ✓                            │
│            ├── 90 minutes                               │
│            └── Custom...                                │
│                                                         │
│ Buffer:    [15 minutes ▾]                               │
│                                                         │
│ [Schedule] [Cancel]                                     │
└─────────────────────────────────────────────────────────┘
```

### Numeric Input
For specific values.

```
┌─────────────────────────────────────────────────────────┐
│ Create purchase order:                                  │
│                                                         │
│ Quantity: [-] [___24___] [+]                            │
│                                                         │
│ Unit price: $ [___45.00___] (from catalog)              │
│                                                         │
│ Total: $1,080.00                                        │
│                                                         │
│ [Submit PO] [Cancel]                                    │
└─────────────────────────────────────────────────────────┘
```

### Toggle Options
For binary parameters.

```
┌─────────────────────────────────────────────────────────┐
│ Send email options:                                     │
│                                                         │
│ Request read receipt    [  OFF  ]                       │
│ High priority           [  ON   ]                       │
│ Request delivery report [  OFF  ]                       │
│                                                         │
│ [Send with options] [Cancel]                            │
└─────────────────────────────────────────────────────────┘
```

## Conditional Approval Patterns

### Simple Condition
Single conditional.

```
┌─────────────────────────────────────────────────────────┐
│ Send trade order: Buy 100 shares ACME                   │
│                                                         │
│ ○ Execute immediately at market price                   │
│ ● Execute only if price ≤ $[___45.00___]                │
│ ○ Execute only if price change < [___5___]%             │
│                                                         │
│ Valid until: [End of day ▾]                             │
│                                                         │
│ [Submit conditional order] [Cancel]                     │
└─────────────────────────────────────────────────────────┘
```

### Rule-Based Condition
Complex conditional logic.

```
┌─────────────────────────────────────────────────────────┐
│ Auto-approve similar requests?                          │
│                                                         │
│ ☐ Apply this approval to future similar requests        │
│                                                         │
│   When matching:                                        │
│   ├── ☑ Same action type (calendar invite)              │
│   ├── ☑ Same recipient domain (internal only)           │
│   ├── ☐ Same time window (working hours)                │
│   └── ☑ Under attendee limit: [___10___]                │
│                                                         │
│   Duration: [This week ▾]                               │
│                                                         │
│ [Approve & apply rule] [Approve once] [Cancel]          │
└─────────────────────────────────────────────────────────┘
```

### Delegation Condition
Conditional on another person.

```
┌─────────────────────────────────────────────────────────┐
│ Document requires signature:                            │
│                                                         │
│ ○ Approve (sign now)                                    │
│ ● Approve if [manager@company.com ▾] also approves      │
│ ○ Request review from [____________] before I decide    │
│                                                         │
│ [Submit] [Cancel]                                       │
└─────────────────────────────────────────────────────────┘
```

## Timing Modification Patterns

### Schedule for Later

```
┌─────────────────────────────────────────────────────────┐
│ When should this email be sent?                         │
│                                                         │
│ ○ Send now                                              │
│ ● Send later:                                           │
│   ├── [Tomorrow ▾] at [9:00 AM ▾]                       │
│   └── Recipient timezone: EST (auto-detected)           │
│ ○ Send when recipient is likely active                  │
│   └── Estimated: Tomorrow 9:00 AM - 11:00 AM EST        │
│                                                         │
│ [Schedule] [Send now anyway] [Cancel]                   │
└─────────────────────────────────────────────────────────┘
```

### Defer Decision

```
┌─────────────────────────────────────────────────────────┐
│ Not ready to decide?                                    │
│                                                         │
│ ○ Remind me in: [1 hour ▾]                              │
│ ○ Remind me at: [____________] [📅]                     │
│ ○ Remind me when: [recipient responds to previous ▾]    │
│                                                         │
│ In the meantime:                                        │
│ ├── Draft will be preserved                             │
│ └── Agent will not take other action on this thread     │
│                                                         │
│ [Defer] [Decide now] [Cancel]                           │
└─────────────────────────────────────────────────────────┘
```

## Escape Hatches

When modification isn't enough—the proposal itself is wrong.

```
┌─────────────────────────────────────────────────────────┐
│ [Approve] [Edit] [Start over] [Do manually]             │
└─────────────────────────────────────────────────────────┘

Start over:
• Agent discards current proposal
• Asks for guidance on what to do differently
• User provides feedback before retry

Do manually:
• Agent provides raw materials (draft, data, etc.)
• User takes full control
• Agent available for assistance if asked
```

### "Start Over" Flow

```
Agent: [Proposed action]
User: [Clicks "Start over"]
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ What should be different?                               │
│                                                         │
│ [Optional feedback: _________________________]          │
│                                                         │
│ [Try again] [Try again with no changes] [Cancel task]   │
└─────────────────────────────────────────────────────────┘
```

### "Do Manually" Handoff

```
Agent: [Proposed action]
User: [Clicks "Do manually"]
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ Taking over manually                                    │
│                                                         │
│ I've prepared:                                          │
│ • Draft email (in your Drafts folder)                   │
│ • Recipient list (in clipboard)                         │
│ • Attachment (ready to attach)                          │
│                                                         │
│ [Open email client] [Copy all to clipboard]             │
│                                                         │
│ Need help? I'm available if you want to discuss.        │
└─────────────────────────────────────────────────────────┘
```

## Modification State Management

### Edit Tracking

```
Status indicators:
├── (no indicator) — Original agent proposal
├── [Edited] — User has made changes
├── [Edited: 3 fields] — Count of modified fields
└── [Reset available] — Can return to original
```

### Change Summary

Before final approval, summarize user modifications:

```
┌─────────────────────────────────────────────────────────┐
│ Your changes:                                           │
│ • Subject: "Q4 Numbers" → "Q4 Numbers - Please review"  │
│ • Removed recipient: carol@external.com                 │
│ • Added attachment: Notes.pdf                           │
│                                                         │
│ [Send with your changes] [View final] [Reset to orig]   │
└─────────────────────────────────────────────────────────┘
```

### Modification Persistence

If user doesn't complete approval:
- Save modifications with draft
- Restore modifications on return
- Clear modifications if user explicitly resets

```
[Returning to pending approval]

You previously made changes:
• Subject modified
• 1 recipient removed

[Continue with your changes] [Start fresh]
```
