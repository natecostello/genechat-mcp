---
name: design-principles
description: Use when implementing GUI interfaces - dashboards, admin interfaces, SaaS products, web applications requiring professional polish
---

# Design Principles

Enforce precise, crafted design for enterprise software, SaaS dashboards, admin interfaces, and web applications. Every interface is polished and designed for its specific context.

## Design Direction (Required First Step)

**Commit to a design direction before writing code.** Consider:

- **What does this product do?** Finance tools need different energy than creative tools.
- **Who uses it?** Power users want density; occasional users want guidance.
- **What's the emotional job?** Trust? Efficiency? Delight? Focus?

### Personality Options

**Precision & Density** — Tight spacing, monochrome, information-forward. For power users. Think Linear, Raycast.

**Warmth & Approachability** — Generous spacing, soft shadows, friendly colors. Think Notion, Coda.

**Sophistication & Trust** — Cool tones, layered depth, financial gravitas. Think Stripe, Mercury.

**Boldness & Clarity** — High contrast, dramatic negative space, confident typography. Think Vercel.

**Utility & Function** — Muted palette, functional density, clear hierarchy. Think GitHub.

**Data & Analysis** — Chart-optimized, technical but accessible. For analytics and BI.

Pick one or blend two. Commit.

### Color Foundation

**Match foundation to product context:**
- Warm foundations (creams, warm grays) — approachable, human
- Cool foundations (slate, blue-gray) — professional, serious
- Pure neutrals (true grays, black/white) — minimal, technical
- Tinted foundations — distinctive, branded

**Light vs dark:** Dark feels technical, focused, premium. Light feels open, approachable.

**Accent color:** Pick ONE. Blue for trust. Green for growth. Orange for energy. Violet for creativity.

### Layout Approach

- **Dense grids** for information-heavy interfaces
- **Generous spacing** for focused tasks
- **Sidebar navigation** for multi-section apps
- **Top navigation** for simpler tools
- **Split panels** for list-detail patterns

### Typography

- **System fonts** — fast, native (utility-focused)
- **Geometric sans** (Geist, Inter) — modern, technical
- **Humanist sans** (SF Pro, Satoshi) — warmer, approachable
- **Monospace influence** — technical, data-heavy

## Core Craft Principles

Apply regardless of design direction.

### 4px Grid

All spacing uses 4px base:
- `4px` - micro (icon gaps)
- `8px` - tight (within components)
- `12px` - standard (related elements)
- `16px` - comfortable (section padding)
- `24px` - generous (between sections)
- `32px` - major separation

### Symmetrical Padding

TLBR must match. Exception: when content naturally creates visual balance.

```css
/* Good */
padding: 16px;
padding: 12px 16px; /* Only when horizontal needs more room */

/* Bad */
padding: 24px 16px 12px 16px;
```

### Border Radius

Stick to 4px grid. Sharper = technical, rounder = friendly.
- Sharp: 4px, 6px, 8px
- Soft: 8px, 12px
- Minimal: 2px, 4px, 6px

Don't mix systems.

### Depth Strategy

Match depth approach to design direction:

**Borders-only (flat)** — Clean, technical, dense. Linear, Raycast style. Intentional restraint, not laziness.

**Subtle single shadows** — Soft lift. `0 1px 3px rgba(0,0,0,0.08)` is often enough.

**Layered shadows** — Rich, premium. Stripe/Mercury style. Best for cards as physical objects.

**Surface color shifts** — Background tints establish hierarchy without shadows.

Choose ONE approach. Mixing flat borders with heavy shadows creates inconsistency.

```css
/* Borders-only */
border: 0.5px solid rgba(0, 0, 0, 0.08);

/* Single shadow */
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);

/* Layered shadow */
box-shadow:
  0 0 0 0.5px rgba(0, 0, 0, 0.05),
  0 1px 2px rgba(0, 0, 0, 0.04),
  0 2px 4px rgba(0, 0, 0, 0.03),
  0 4px 8px rgba(0, 0, 0, 0.02);
```

### Card Layouts

Card layouts should vary by content. Metric cards ≠ plan cards ≠ settings cards. Design internal structure for specific content, but keep surface treatment consistent: same border weight, shadow depth, corner radius, padding scale, typography.

### Isolated Controls

UI controls deserve container treatment. Never use native form elements for styled UI—native `<select>`, `<input type="date">` render OS-native controls that cannot be styled.

Build custom components:
- Custom select: trigger button + positioned dropdown
- Custom date picker: input + calendar popover
- Custom checkbox/radio: styled div with state management

**Custom select triggers must use `display: inline-flex` with `white-space: nowrap`** to keep text and chevron on same row.

### Typography Hierarchy

- Headlines: 600 weight, -0.02em letter-spacing
- Body: 400-500 weight, standard tracking
- Labels: 500 weight, slight positive tracking for uppercase
- Scale: 11px, 12px, 13px, 14px (base), 16px, 18px, 24px, 32px

### Monospace for Data

Numbers, IDs, codes, timestamps in monospace. Use `tabular-nums` for columnar alignment.

### Iconography

Use **Phosphor Icons** (`@phosphor-icons/react`). Icons clarify, not decorate—if removing loses no meaning, remove it.

### Animation

- 150ms for micro-interactions, 200-250ms for larger transitions
- Easing: `cubic-bezier(0.25, 1, 0.5, 1)`
- No spring/bouncy effects

### Contrast Hierarchy

Four levels: foreground → secondary → muted → faint. Use all four consistently.

### Color for Meaning Only

Gray builds structure. Color only for status, action, error, success. No decorative color.

## Navigation Context

Include grounding elements:
- Navigation (sidebar or top nav)
- Location indicator (breadcrumbs, page title, active state)
- User context (who's logged in, workspace/org)

Consider same background for sidebar and main content (Linear, Supabase style) with subtle border for separation.

## Dark Mode

- **Borders over shadows** — Shadows less visible on dark backgrounds
- **Adjust semantic colors** — Desaturate status colors for dark backgrounds
- **Same hierarchy, inverted values**

## Anti-Patterns

### Never

- Dramatic drop shadows (`box-shadow: 0 25px 50px...`)
- Large border radius (16px+) on small elements
- Asymmetric padding without reason
- Pure white cards on colored backgrounds
- Thick borders (2px+) for decoration
- Excessive spacing (>48px between sections)
- Spring/bouncy animations
- Decorative gradients
- Multiple accent colors

### Always Question

- "Did I commit to a design direction or default?"
- "Does this direction fit context and users?"
- "Is my depth strategy consistent?"
- "Are all elements on the grid?"
