# Stakes Communication Patterns Reference

Visual and linguistic inventory for communicating approval stakes accurately.

## Stakes Level Definitions

### Routine
- **Consequence cost**: Minutes to recover
- **Reversibility**: Immediate, single action
- **Blast radius**: Self only
- **Examples**: Internal message, file rename, calendar self-reminder

### Notable  
- **Consequence cost**: Hours to recover
- **Reversibility**: Possible but requires effort
- **Blast radius**: Self + immediate team
- **Examples**: Team email, shared document edit, meeting invite (small group)

### Significant
- **Consequence cost**: Days to recover, or meaningful financial/reputational cost
- **Reversibility**: Difficult, may require others' cooperation
- **Blast radius**: Extended team, external parties
- **Examples**: External email, publishing content, financial transaction <$X, calendar invite (large group)

### Critical
- **Consequence cost**: Weeks+ to recover, or major financial/legal/reputational exposure
- **Reversibility**: Impossible or extremely difficult
- **Blast radius**: Organization, public, legal record
- **Examples**: Press communication, contract execution, financial transaction >$X, public publishing, legal filings

## Visual Treatment by Stakes Level

### Routine

```
┌─────────────────────────────────────────────┐
│ Send message to @alice?                     │
│                                             │
│ "Thanks for the update!"                    │
│                                             │
│                         [Send] [Cancel]     │
└─────────────────────────────────────────────┘
```

**Characteristics**:
- Inline or minimal modal
- Neutral colors (default UI chrome)
- Single-click approval
- No confirmation friction
- Undo available post-approval

### Notable

```
┌─────────────────────────────────────────────────────────┐
│ Send email to team (7 recipients)                       │
│                                                         │
│ [Email preview...]                                      │
│                                                         │
│ Recipients: product-team@company.com (7 people)         │
│                                                         │
│                               [Send] [Edit] [Cancel]    │
└─────────────────────────────────────────────────────────┘
```

**Characteristics**:
- Standard modal
- Neutral colors with scope indicators
- Explicit recipient/scope count
- Edit option prominent
- Brief pause acceptable

### Significant

```
┌─────────────────────────────────────────────────────────┐
│ ⚠ External Communication                                │
├─────────────────────────────────────────────────────────┤
│ Send email to client@external.com                       │
│                                                         │
│ [Email preview...]                                      │
│                                                         │
│ This email will leave your organization.                │
│ Recipient is outside company.com domain.                │
│                                                         │
│ You can recall within 30 seconds of sending.            │
│                                                         │
│                    [Send to external] [Edit] [Cancel]   │
└─────────────────────────────────────────────────────────┘
```

**Characteristics**:
- Prominent modal, elevated visual weight
- Warning color accent (yellow/amber)
- Explicit external/elevated indicator
- Consequence statement
- Button label reflects stakes ("Send to external" not just "Send")
- Reversibility stated

### Critical

```
┌─────────────────────────────────────────────────────────┐
│ ⛔ Critical: Irreversible Action                        │
├─────────────────────────────────────────────────────────┤
│ Publish press release to 47 media contacts              │
│                                                         │
│ [Document preview...]                                   │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ This action cannot be undone.                       │ │
│ │ • 47 external recipients will receive immediately   │ │
│ │ • Content will be public record                     │ │
│ │ • Legal review has not been completed               │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ Type "PUBLISH" to confirm: [____________]               │
│                                                         │
│                               [Publish] [Cancel]        │
│                               (disabled until typed)    │
└─────────────────────────────────────────────────────────┘
```

**Characteristics**:
- Maximum visual prominence
- Danger/critical color (red)
- Explicit "irreversible" or "critical" label
- Itemized consequence list
- Confirmation friction (type to confirm, checkbox, countdown)
- Button disabled until friction completed
- No quick path to approval

## Linguistic Patterns by Stakes Level

### Action Statement

| Stakes | Pattern | Example |
|--------|---------|---------|
| Routine | Bare action | "Send message?" |
| Notable | Action + scope | "Send email to 7 recipients" |
| Significant | Action + consequence hint | "Send email externally to client@external.com" |
| Critical | Labeled action + consequence | "⛔ Publish: Send press release to 47 media contacts" |

### Consequence Statement

| Stakes | Presence | Example |
|--------|----------|---------|
| Routine | Omit | — |
| Notable | On request | "View details" expandable |
| Significant | Present | "This email will leave your organization." |
| Critical | Prominent | "This action cannot be undone. Content becomes public record." |

### Button Labels

| Stakes | Primary Action | Cancel |
|--------|----------------|--------|
| Routine | "Send", "Save", "Do it" | "Cancel" or just X |
| Notable | "Send", "Confirm" | "Cancel" |
| Significant | "Send externally", "Publish to team" | "Cancel" |
| Critical | "I understand, publish", "Confirm irreversible action" | "Cancel" or "Go back" |

### Reversibility Statement

| Stakes | Pattern |
|--------|---------|
| Routine | Omit (assume reversible) |
| Notable | "Can be undone" or omit |
| Significant | "You can recall within [time]" or "Difficult to reverse" |
| Critical | "This cannot be undone" — explicit, prominent |

## Color and Iconography

### Semantic Color Mapping

| Stakes | Primary Color | Usage |
|--------|---------------|-------|
| Routine | None (default) | No color treatment |
| Notable | None or muted blue | Optional scope indicator |
| Significant | Amber/Yellow | Warning banner, icon accent |
| Critical | Red | Border, icon, confirmation area |

### Icons

| Stakes | Icon | Usage |
|--------|------|-------|
| Routine | None | — |
| Notable | ℹ️ or scope icon | Optional |
| Significant | ⚠️ | Header |
| Critical | ⛔ or 🚨 | Header, prominent |

## Anti-Inflation Enforcement

To prevent stakes inflation:

### System-Level Rules
1. Maintain stakes registry with approval from design owner
2. Each action type has assigned stakes level
3. Elevation requires explicit justification
4. Audit: track approval-to-stakes ratio per level

### User-Level Calibration
1. Learn from response patterns: <2s response suggests overcategorization
2. Surface learning: "You always approve these quickly. Lower stakes level?"
3. Allow per-user stakes override for specific action types
4. Never lower Critical—users cannot self-demote truly critical actions

### Calibration Metrics

| Signal | Interpretation |
|--------|----------------|
| Approval time <2s | Stakes likely overcategorized |
| Approval time >30s | Stakes appropriate OR user confused |
| Edit rate >20% | Preview insufficient OR stakes overcategorized |
| Rejection rate >10% | Agent proposing wrong actions |

## Context-Sensitive Stakes

Same action type can have different stakes based on context:

### Email Stakes Factors
| Factor | Impact |
|--------|--------|
| Recipient domain | Internal < External |
| Recipient count | Few < Many |
| Attachment presence | No < Yes |
| Attachment sensitivity | Public < Confidential |
| Reply vs. new | Reply < New (more context in reply) |

### Document Stakes Factors
| Factor | Impact |
|--------|--------|
| Visibility | Private < Shared < Public |
| Edit type | Format < Content < Delete |
| Version | Draft < Final |
| Legal/financial | No < Yes |

### Calendar Stakes Factors
| Factor | Impact |
|--------|--------|
| Attendees | Self < Team < External |
| Attendee count | Few < Many |
| Resource booking | No < Yes |
| Recurring | Single < Recurring |

## Transition Cues

When action crosses stakes threshold, signal the transition:

```
┌─────────────────────────────────────────────────────────┐
│ 📧 → 📧⚠️                                               │
│                                                         │
│ Adding external recipient elevates this email.          │
│ carol@external.com is outside your organization.        │
│                                                         │
│ Previous: Internal email (routine)                      │
│ Now: External email (requires review)                   │
│                                                         │
│              [Continue with external] [Remove external] │
└─────────────────────────────────────────────────────────┘
```

This prevents surprise when users modify and action escalates.
