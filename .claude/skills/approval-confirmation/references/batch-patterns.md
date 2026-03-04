# Batch Approval Patterns Reference

Layout specifications and algorithms for handling multiple approval requests.

## Batch Formation Criteria

### When to Batch

| Criterion | Threshold | Example |
|-----------|-----------|---------|
| Same action type | All items same type | 5 emails to send |
| Same trigger | Single user instruction | "Send updates to all clients" |
| Same stakes level | All items same level | All routine, or all significant |
| Temporal proximity | Generated within same workflow | Items from single planning step |
| Logical grouping | Related by business logic | All items for same project |

### When NOT to Batch

| Criterion | Example | Why |
|-----------|---------|-----|
| Mixed stakes | 4 routine + 1 critical | Critical item may be overlooked |
| Unrelated items | Email + calendar + file move | No cognitive benefit to grouping |
| Individual judgment required | Each email needs different review | Batching hides the differences |
| Significant variance | Emails to very different audiences | Audience-specific review needed |

### Batching Decision Tree

```
Multiple items pending approval?
│
├── Same action type?
│   ├── No → Do not batch (show separately or queue)
│   └── Yes → Continue
│       │
│       ├── Same stakes level?
│       │   ├── No → Separate by stakes (batch within levels)
│       │   └── Yes → Continue
│       │       │
│       │       ├── Requires individual judgment?
│       │       │   ├── Yes → Batch with mandatory expansion
│       │       │   └── No → Batch with optional expansion
│       │       │
│       └── Group logically for presentation
```

## Batch Presentation Hierarchy

### Level 1: Summary View
Always visible. Enables quick approval of homogeneous batches.

```
┌─────────────────────────────────────────────────────────┐
│ 📧 5 emails ready to send                               │
│                                                         │
│ All internal recipients • All under 500 words           │
│                                                         │
│ [Approve all (5)] [Review individually] [Reject all]    │
└─────────────────────────────────────────────────────────┘
```

**Required elements**:
- Count and type
- Homogeneity statement (what they have in common)
- Approve all / Review / Reject all buttons

### Level 2: Grouped View
One-click expansion. Shows items grouped by meaningful dimension.

```
┌─────────────────────────────────────────────────────────┐
│ 📧 5 emails ready to send                               │
│                                                         │
│ ▼ By recipient type:                                    │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Internal (3)                    [Approve group]     │ │
│ │ ├── To: team@company.com - Weekly update            │ │
│ │ ├── To: manager@company.com - Status report         │ │
│ │ └── To: hr@company.com - PTO request                │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ External (2) ⚠️                 [Approve group]     │ │
│ │ ├── To: client@external.com - Proposal follow-up    │ │
│ │ └── To: vendor@external.com - Invoice question      │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ [Approve all (5)] [Cancel all]                          │
└─────────────────────────────────────────────────────────┘
```

**Grouping dimensions**:
- Recipient type (internal/external)
- Category/project
- Priority/stakes
- Time sensitivity

### Level 3: Individual View
Full preview for any item. Click to expand.

```
┌─────────────────────────────────────────────────────────┐
│ ▼ To: client@external.com - Proposal follow-up          │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Subject: Following up on Q4 proposal                │ │
│ │                                                     │ │
│ │ Hi Sarah,                                           │ │
│ │                                                     │ │
│ │ I wanted to follow up on the proposal we sent      │ │
│ │ last week. Do you have any questions?              │ │
│ │                                                     │ │
│ │ Best regards,                                       │ │
│ │ [Your name]                                         │ │
│ │                                                     │ │
│ │ 📎 Q4_Proposal.pdf (1.2 MB)                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ [Approve] [Edit] [Remove from batch] [Skip]             │
└─────────────────────────────────────────────────────────┘
```

## Mixed-Stakes Handling

When batch contains different stakes levels, separate them visually and functionally.

### Segregated Display

```
┌─────────────────────────────────────────────────────────┐
│ 7 actions ready for approval                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Routine (approve with one click):                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ☑ 5 calendar updates                                │ │
│ │   └── All self-reminders, no attendees              │ │
│ │                                                     │ │
│ │ [Approve routine (5)]                               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ⚠️ Requires review:                                     │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ ☐ 1 email to external recipient                     │ │
│ │   └── client@external.com                           │ │
│ │                                                     │ │
│ │ ☐ 1 document with edit permissions                  │ │
│ │   └── Shared to contractor@external.com             │ │
│ │                                                     │ │
│ │ [Review these (2)]                                  │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Progressive Stakes

```
Review order (recommended):

1. ⛔ Critical (1 item)
   └── Press release - must review individually
   
2. ⚠️ Significant (2 items)  
   └── External communications - review recommended
   
3. ℹ️ Routine (4 items)
   └── Internal updates - can batch approve

[Start review] [Approve all routine now]
```

## Batch Modification Patterns

### Bulk Parameter Change

```
┌─────────────────────────────────────────────────────────┐
│ 5 calendar events                                       │
│                                                         │
│ Bulk settings:                                          │
│ ├── Duration: [60 min ▾] Apply to all                   │
│ ├── Buffer: [15 min ▾] Apply to all                     │
│ └── Reminder: [15 min before ▾] Apply to all            │
│                                                         │
│ Or customize individually below...                      │
│                                                         │
│ [Apply bulk settings] [Show all details]                │
└─────────────────────────────────────────────────────────┘
```

### Partial Approval

```
┌─────────────────────────────────────────────────────────┐
│ 5 emails ready to send                                  │
│                                                         │
│ ☑ alice@company.com - Project update      [Preview]     │
│ ☑ bob@company.com - Status report         [Preview]     │
│ ☐ carol@external.com - Client follow-up   [Preview]     │ ← Deselected
│ ☑ dan@company.com - Team sync             [Preview]     │
│ ☑ eve@company.com - Quick question        [Preview]     │
│                                                         │
│ Selected: 4 of 5                                        │
│                                                         │
│ Deselected items will be saved as drafts.               │
│                                                         │
│ [Send selected (4)] [Send all (5)] [Cancel]             │
└─────────────────────────────────────────────────────────┘
```

### Exception Handling

```
┌─────────────────────────────────────────────────────────┐
│ Apply permission change to 12 users:                    │
│                                                         │
│ Standard change: Editor → Viewer                        │
│                                                         │
│ ☑ Apply to 10 users as-is                               │
│                                                         │
│ Exceptions (2):                                         │
│ ├── alice@company.com: Keep as Editor (project lead)    │
│ └── bob@company.com: Set to Admin (needs oversight)     │
│                                                         │
│ [Apply with exceptions] [Apply uniformly] [Cancel]      │
└─────────────────────────────────────────────────────────┘
```

## Batch Size Guidelines

### Cognitive Load Thresholds

| Batch Size | Presentation | Review Expectation |
|------------|--------------|-------------------|
| 1-5 | List all, expand by default | User reviews each |
| 6-15 | Grouped, collapsed by default | User spot-checks |
| 16-50 | Summary + sampling | User approves pattern |
| 50+ | Summary only | User approves policy |

### Large Batch Handling

```
┌─────────────────────────────────────────────────────────┐
│ 127 calendar events to create                           │
│                                                         │
│ Pattern: Weekly team sync, every Monday 10am            │
│ Duration: 2.5 years (through December 2026)             │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Sample (5 random):                        [Refresh] │ │
│ │ • Mon, Oct 28, 2024 10:00 AM                        │ │
│ │ • Mon, Feb 3, 2025 10:00 AM                         │ │
│ │ • Mon, Jun 9, 2025 10:00 AM                         │ │
│ │ • Mon, Oct 20, 2025 10:00 AM                        │ │
│ │ • Mon, Mar 2, 2026 10:00 AM                         │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ [View all 127] [Search/filter]                          │
│                                                         │
│ [Create all (127)] [Create first 3 months] [Cancel]     │
└─────────────────────────────────────────────────────────┘
```

### Search and Filter for Large Batches

```
┌─────────────────────────────────────────────────────────┐
│ 127 events │ [Search: __________] [Filter ▾]            │
│                                                         │
│ Filter by:                                              │
│ ├── Date range: [Any ▾]                                 │
│ ├── Day of week: [Any ▾]                                │
│ └── Conflicts: [Show conflicts only]                    │
│                                                         │
│ Showing: 3 events with conflicts                        │
│ ├── Mon, Dec 23, 2024 - Holiday conflict                │
│ ├── Mon, Dec 30, 2024 - Holiday conflict                │
│ └── Mon, Jul 4, 2025 - Holiday conflict                 │
│                                                         │
│ [Exclude these (3)] [Review individually]               │
└─────────────────────────────────────────────────────────┘
```

## Batch Progress and Completion

### Progress During Execution

```
┌─────────────────────────────────────────────────────────┐
│ Sending 5 emails...                                     │
│                                                         │
│ [████████████████████░░░░░░░░░░] 3 of 5                 │
│                                                         │
│ ✓ alice@company.com - Sent                              │
│ ✓ bob@company.com - Sent                                │
│ ✓ carol@company.com - Sent                              │
│ ◌ dan@company.com - Sending...                          │
│ ○ eve@company.com - Queued                              │
│                                                         │
│ [Cancel remaining]                                      │
└─────────────────────────────────────────────────────────┘
```

### Partial Failure Handling

```
┌─────────────────────────────────────────────────────────┐
│ Batch completed with errors                             │
│                                                         │
│ ✓ Successful: 4 of 5                                    │
│ ✗ Failed: 1                                             │
│                                                         │
│ Failed item:                                            │
│ └── carol@invalid-domain.com                            │
│     Error: Invalid recipient address                    │
│     [Edit and retry] [Remove] [View details]            │
│                                                         │
│ [Done] [Retry failed]                                   │
└─────────────────────────────────────────────────────────┘
```

## Batch Undo

```
┌─────────────────────────────────────────────────────────┐
│ ✓ 5 emails sent                              [Undo all] │
│                                                         │
│ Undo window: 28 seconds remaining                       │
│                                                         │
│ [████████████████░░░░░░░░░░░░░░░]                       │
└─────────────────────────────────────────────────────────┘
```

After undo window:
```
┌─────────────────────────────────────────────────────────┐
│ ✓ 5 emails sent                                         │
│                                                         │
│ Undo window expired. Recall may still be possible       │
│ for some recipients.                                    │
│                                                         │
│ [View sent items] [Attempt recall]                      │
└─────────────────────────────────────────────────────────┘
```

## Batch Notification Design

When batches complete in background:

```
┌─────────────────────────────────────────────────────────┐
│ 🔔 Batch complete: 5 emails sent                        │
│                                                         │
│ All delivered successfully.                             │
│ View: [Sent folder] [Dismiss]                           │
└─────────────────────────────────────────────────────────┘
```

With failures:
```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Batch complete: 4 of 5 emails sent                   │
│                                                         │
│ 1 delivery failed (invalid address).                    │
│ [View details] [Retry] [Dismiss]                        │
└─────────────────────────────────────────────────────────┘
```
