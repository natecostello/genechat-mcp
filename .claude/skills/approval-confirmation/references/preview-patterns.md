# Preview Patterns Reference

Implementation specifications for pre-action previews.

## Preview Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ TRIGGER CONTEXT (why this is happening)                     │
│ "Based on your message: 'Send Bob the Q4 numbers'"          │
├─────────────────────────────────────────────────────────────┤
│ ACTION STATEMENT (what will happen, one line)               │
│ Send email to bob@company.com                               │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ ARTIFACT PREVIEW (WYSIWYG of result)                    │ │
│ │                                                         │ │
│ │ To: bob@company.com                                     │ │
│ │ Subject: Q4 Numbers                                     │ │
│ │                                                         │ │
│ │ Hi Bob,                                                 │ │
│ │ Attached are the Q4 numbers you requested.              │ │
│ │ [attachment: Q4_Report.xlsx]                            │ │
│ │                                                         │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ SCOPE INDICATOR                                             │
│ • Sends email (1 recipient)                                 │
│ • Includes attachment (36KB)                                │
│ • Does NOT modify original spreadsheet                      │
├─────────────────────────────────────────────────────────────┤
│        [Send] [Edit before sending] [Cancel]                │
└─────────────────────────────────────────────────────────────┘
```

## Trigger Context Patterns

The trigger context answers: "Why is the agent doing this now?"

### Explicit Instruction
User told agent to do something.
```
Based on your message: "[quoted instruction]"
```

### Workflow Step
Part of a larger process.
```
Step 3 of 5: Sending confirmation email
(Workflow: Client onboarding)
```

### Scheduled Task
Triggered by time.
```
Scheduled weekly report (set up Oct 15, 2024)
```

### Event Response
Triggered by external event.
```
Responding to: New email from client@external.com (received 10 min ago)
```

### Inferred Intent
Agent inferred user likely wants this.
```
Suggested action: Your calendar shows meeting in 15 min with no agenda sent.
```

**Key principle**: Inferred intent requires softer framing and easier rejection than explicit instruction.

## Artifact Preview Specifications

### Email Preview

```
┌─────────────────────────────────────────────────────────┐
│ To: recipient@domain.com                      [Edit ✎]  │
│ CC: cc@domain.com                            [Edit ✎]  │
│ Subject: Subject line here                    [Edit ✎]  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Email body text rendered with formatting.               │
│                                                         │
│ Paragraphs preserved.                                   │
│                                                         │
│ Links: shown as [link text](url)                        │
│                                                         │
│ Signature block if applicable.                          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Attachments:                                            │
│ 📎 document.pdf (2.1 MB) [Preview] [Remove]             │
│ 📎 image.png (340 KB) [Preview] [Remove]                │
└─────────────────────────────────────────────────────────┘
```

### Calendar Event Preview

```
┌─────────────────────────────────────────────────────────┐
│ 📅 New Event                                            │
├─────────────────────────────────────────────────────────┤
│ Title: Q4 Planning Meeting                   [Edit ✎]   │
│ When: Thursday, Oct 24 · 3:00 PM – 4:00 PM  [Edit ✎]   │
│ Where: Conference Room A (or Zoom)           [Edit ✎]   │
├─────────────────────────────────────────────────────────┤
│ Attendees:                                   [Edit ✎]   │
│ ✓ alice@company.com (organizer)                         │
│ ◦ bob@company.com (pending)                             │
│ ◦ carol@company.com (pending)                           │
├─────────────────────────────────────────────────────────┤
│ Agenda:                                      [Edit ✎]   │
│ 1. Review Q3 outcomes                                   │
│ 2. Discuss Q4 priorities                                │
│ 3. Assign owners                                        │
├─────────────────────────────────────────────────────────┤
│ Notifications: 15 min before                            │
│ Visibility: Team calendar                               │
└─────────────────────────────────────────────────────────┘
```

### Document Change Preview (Diff)

```
┌─────────────────────────────────────────────────────────┐
│ 📄 Changes to: Project_Plan.docx                        │
│ 3 modifications                                         │
├─────────────────────────────────────────────────────────┤
│ Section 2.1 (Timeline):                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ - Delivery date: October 15, 2024                   │ │
│ │ + Delivery date: October 22, 2024                   │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Section 3.4 (Resources):                                │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ + Added: "Additional QA resource required for       │ │
│ │   extended timeline"                                │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ Footer:                                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ - Last updated: Oct 1, 2024                         │ │
│ │ + Last updated: Oct 10, 2024                        │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ [View full document] [View all changes in context]      │
└─────────────────────────────────────────────────────────┘
```

### File Operation Preview

```
┌─────────────────────────────────────────────────────────┐
│ 📁 File Operations (3 items)                            │
├─────────────────────────────────────────────────────────┤
│ Move:                                                   │
│ ├─ report_v1.docx                                       │
│ │  From: /Documents/Drafts/                             │
│ │  To:   /Documents/Archive/2024/                       │
│ │                                                       │
│ Rename:                                                 │
│ ├─ report_final.docx → Q4_Report_Final.docx             │
│ │  Location: /Documents/Reports/                        │
│ │                                                       │
│ Delete:                                                 │
│ └─ temp_notes.txt                                       │
│    Location: /Documents/Drafts/                         │
│    ⚠ This file is not in trash—deletion is permanent   │
└─────────────────────────────────────────────────────────┘
```

## Preview Fidelity Decision Tree

```
Is the exact artifact available?
├── Yes → Exact preview (render the actual email, document, etc.)
│
└── No → Is there a representative example?
         ├── Yes → Representative preview with "[Example]" label
         │         "Will create invoice similar to:"
         │         [Example invoice preview]
         │
         └── No → Structural preview
                  "Will create 5 calendar events following this pattern:"
                  [Template showing structure, not content]
```

## Scope Indicator Patterns

### Affirmative Scope (what WILL happen)
```
This will:
• Send 1 email
• Attach 1 file (36KB)
• Mark conversation as resolved
```

### Negative Scope (what will NOT happen)
Important for setting boundaries on agent authority.
```
This will NOT:
• Send to anyone outside your organization
• Access files outside /Documents/
• Make changes to the original spreadsheet
```

### Change Scope (for modifications)
```
Changes:
• 3 sections modified
• 0 sections added
• 0 sections deleted
Unchanged: 47 other sections
```

## Preview Timing

| Preview Generation | Use When |
|--------------------|----------|
| **Synchronous** | Artifact exists, preview is instant |
| **Async with placeholder** | Generation takes >500ms; show "Generating preview..." |
| **Progressive** | Large artifact; show structure immediately, populate details |

Progressive loading example:
```
1. Show action statement immediately
2. Show artifact structure (headers, sections) at 200ms
3. Populate content as it loads
4. Complete preview ready for approval
```

## Accessibility Requirements

- Screen readers: Action statement must be first focusable element
- Keyboard: Tab order follows visual hierarchy (context → action → preview → buttons)
- High contrast: Diff indicators (red/green) must have secondary indicator (±, strikethrough)
- Zoom: Preview must remain functional at 200% zoom
