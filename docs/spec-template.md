# Subsystem Specification Template

> Copy this template into a subsystem directory as `SPEC.md` and fill in each
> section. Use `/codify-subsystem` to create one interactively.

## Target Size

100-400 lines. Under 100 means missing invariants or failure modes. Over 400
means the subsystem should be split.

---

# [Subsystem Name]

## Purpose

[One paragraph: what this subsystem does and why it exists. Include the
problem it solves and the key design decision that shaped it.]

## Core Mechanism

[How it works — the mental model an agent needs to modify this code correctly.
Include key algorithms, data flows, and architectural decisions. Reference
specific files and functions by path.]

**Key files:**
- `path/to/entry-point.py` — [role]
- `path/to/core-logic.py` — [role]

## Public Interface

[What other subsystems depend on. Exports, APIs, events, shared types.
An agent modifying this subsystem must not break these contracts.]

| Export | Used By | Contract |
|---|---|---|
| | | |

## Invariants

[Things that must ALWAYS be true. These are the correctness pillars — an agent
that violates any of these has introduced a bug. Each invariant gets an ID for
test traceability.]

| ID | Invariant | Why It Matters |
|---|---|---|
| INV-1 | | |

## Failure Modes

[Known ways this subsystem breaks and how to fix them. An agent encountering
these symptoms should try the fix before investigating further. Each failure
mode gets an ID for test traceability.]

| ID | Symptom | Cause | Fix |
|---|---|---|---|
| FAIL-1 | | | |

## Testing

[How to run tests for this subsystem. Include the exact command, any required
fixtures or environment setup, and the mocking strategy.]

```bash
# Run subsystem tests
[exact command here]
```

### Coverage

Every INV-N must have at least one positive test (verifies the invariant holds).
Every FAIL-N must have at least one negative test (verifies graceful handling).
Test names include the spec item ID for bidirectional traceability.

**Naming convention:** `test_inv1_description` for invariants, `test_fail1_description` for failure modes.

| Spec Item | Test | Description |
|---|---|---|
| INV-1 | `test_inv1_[description]` | Verifies [invariant] holds |
| FAIL-1 | `test_fail1_[description]` | Verifies [failure mode] is handled |

## Dependencies

[What this subsystem depends on — other subsystems, external services,
libraries. An agent working here should load these SPEC.md files too if
making changes that cross boundaries.]

| Dependency | Type | SPEC.md Path |
|---|---|---|
| | internal/external | |
