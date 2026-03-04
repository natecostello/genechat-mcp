# Consequence Visualization Patterns Reference

Templates and approaches for making approval consequences tangible.

## Consequence Taxonomy

### Immediate Consequences
What happens the moment approval is granted.
- Email sent
- Document modified
- Event created
- File moved

### Downstream Consequences  
What the immediate action triggers.
- Notifications dispatched
- Workflows initiated
- State changes propagated
- Integrations activated

### Reversibility Consequences
What recovery looks like if this was wrong.
- Undo available (how, how long)
- Recovery effort required
- Permanent changes identified

### Rejection Consequences
What happens if user says no.
- Draft preservation
- Retry behavior
- Alternative actions

## Before/After Comparison Layouts

### Side-by-Side (for parallel comparison)

```
┌─────────────────────┬─────────────────────┐
│       BEFORE        │       AFTER         │
├─────────────────────┼─────────────────────┤
│ Status: Draft       │ Status: Published   │
│ Visible to: You     │ Visible to: Public  │
│ Editable: Yes       │ Editable: No        │
│ URL: (none)         │ URL: blog.co/post   │
└─────────────────────┴─────────────────────┘
```

Use when: Comparing discrete states, few properties changing.

### Inline Diff (for text changes)

```
Section 2.1:
───────────────────────────────────────────────
  The project timeline extends from Q3 to 
- October 15, 2024, with delivery scheduled
+ October 22, 2024, with delivery scheduled
  for end of month.
───────────────────────────────────────────────
```

Use when: Text modifications, showing exact changes in context.

### Stacked Comparison (for complex changes)

```
Property changes:

Timeline
├── Before: October 15, 2024
└── After:  October 22, 2024  (+7 days)

Budget
├── Before: $50,000
└── After:  $55,000  (+10%)

Team
├── Before: 4 members
└── After:  5 members  (+1 QA)
```

Use when: Multiple independent properties changing.

## Impact Radius Visualization

### Tree Structure (hierarchical impact)

```
This action affects:
│
├── 📄 Your document
│   └── ✓ Modified (3 sections)
│
├── 👥 People notified (3)
│   ├── alice@company.com (owner)
│   ├── bob@company.com (editor)
│   └── carol@external.com (viewer) ⚠️ external
│
├── 🔗 Linked resources
│   ├── Project_Plan.xlsx (reference updated)
│   └── Timeline.png (embedded, replaced)
│
└── 🔄 Automated workflows
    └── Slack notification to #project-updates
```

### Concentric Circles (blast radius)

```
    ┌───────────────────────────────────────────┐
    │           Organizational impact           │
    │   ┌───────────────────────────────────┐   │
    │   │         Team impact               │   │
    │   │   ┌───────────────────────────┐   │   │
    │   │   │     Direct impact         │   │   │
    │   │   │   ┌─────────────────┐     │   │   │
    │   │   │   │   This action   │     │   │   │
    │   │   │   └─────────────────┘     │   │   │
    │   │   │ • Your calendar           │   │   │
    │   │   │ • Your document           │   │   │
    │   │   └───────────────────────────┘   │   │
    │   │ • Team calendar                   │   │
    │   │ • 5 teammates notified            │   │
    │   └───────────────────────────────────┘   │
    │ • Company directory updated               │
    │ • Visible in org chart                    │
    └───────────────────────────────────────────┘
```

Use when: Emphasizing scope of impact across organizational boundaries.

## Dependency Chain Visualization

### Linear Flow (sequential consequences)

```
Approval
    │
    ▼
Send email ──────────────────────────────────── Immediate
    │
    ▼
Recipient receives notification ─────────────── +seconds
    │
    ▼
Auto-reply possible (if OOO) ────────────────── +seconds
    │
    ▼
Thread appears in shared inbox ──────────────── +minutes
    │
    ▼
Follow-up task auto-created (3 days) ────────── +3 days
```

### Branching Flow (conditional consequences)

```
Approval
    │
    ├──► Calendar event created
    │         │
    │         ├──► [If room available]
    │         │         Room A booked
    │         │         
    │         └──► [If room unavailable]
    │                   Zoom link generated
    │                   Room request queued
    │
    └──► Invitations sent
              │
              ├──► [If internal recipient]
              │         Calendar updated immediately
              │         
              └──► [If external recipient]
                        Email sent (may require acceptance)
```

## Reversibility Statements

### Fully Reversible
```
Undo available:
• Click "Undo" within 30 seconds, or
• Find in Sent folder and recall, or
• Contact recipient to disregard
```

### Partially Reversible
```
Partially reversible:
✓ Document can be restored from version history
✓ Your changes can be reverted
✗ Notifications already sent cannot be recalled
✗ Comments from others may reference deleted content
```

### Irreversible
```
⛔ This action cannot be undone:
• Published content enters public record
• External recipients retain their copies
• Search engines may index before removal
• Legal retention requirements may apply
```

### Time-Bounded Reversibility
```
Recovery window:

[████████░░░░░░░░░░░░░░░░░░░░░░] 30 seconds
   Full recall available

[░░░░░░░░████████░░░░░░░░░░░░░░] 30s - 2min
   Request recall (may fail)

[░░░░░░░░░░░░░░░░██████████████] >2 min
   Cannot recall; must send correction
```

## Rejection Consequence Patterns

### Preservation Statement
```
If you reject:
────────────────────────────────────────────
Preserved:
• Email saved as draft (editable)
• All attachments retained
• Recipient list saved

Not preserved:
• Send time (will need to reschedule)
• Thread position (if reply)
```

### Agent Behavior Statement
```
If you reject:
────────────────────────────────────────────
Agent will:
• Save current work as draft
• Not retry without your instruction
• Ask for feedback (optional): What should be different?

Agent will NOT:
• Send to any recipient
• Modify original files
• Schedule automatic retry
```

### Alternative Action Statement
```
If you reject:
────────────────────────────────────────────
Alternatives available:
• [Edit and retry] - Modify and resubmit
• [Send to subset] - Approve for some recipients
• [Schedule for later] - Delay send
• [Cancel entirely] - Discard draft
```

## Confidence Markers for Consequences

### Certain Consequences
```
Will happen:
✓ Email delivered to recipient server
✓ Timestamp recorded
✓ Appears in your Sent folder
```

### Likely Consequences
```
Likely to happen:
◐ Recipient reads within 24 hours (based on past behavior)
◐ Auto-reply if recipient OOO (common for this contact)
```

### Possible Consequences
```
May happen:
○ Email forwarded to others
○ Triggers discussion in recipient's team
○ Referenced in future communications
```

### Unknown Consequences
```
Cannot determine:
? Whether recipient will respond
? How recipient will interpret tone
? Whether attachment will open correctly on their device
```

## Progressive Disclosure for Consequences

### Level 1: Summary (always visible)
```
This will send email to 3 recipients externally.
```

### Level 2: Key impacts (one click to expand)
```
▶ View impact details

Key impacts:
• 3 external recipients will receive
• 1 attachment (2.1MB) included
• Reply-to set to your work address
```

### Level 3: Full analysis (on demand)
```
▶ View full consequence analysis

[Complete dependency tree]
[All downstream workflows]
[Historical context from similar actions]
[Recovery procedures if needed]
```

## Consequence Visualization Decision Tree

```
What type of action?
│
├── State change (document, settings)
│   └── Use: Before/After comparison
│
├── Communication (email, message)
│   └── Use: Impact radius + recipient tree
│
├── Creation (new file, event)
│   └── Use: Artifact preview + downstream flow
│
├── Deletion
│   └── Use: What's lost + reversibility emphasis
│
└── Multi-step workflow
    └── Use: Dependency chain + branch points
```
