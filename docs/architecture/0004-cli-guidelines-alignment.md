---
status: accepted
date: 2026-03-11
decision-makers: natecostello
related ADRs:
  - [0003-pip-installable-package](0003-pip-installable-package.md)
---

# Adopt clig.dev CLI Design Guidelines

## Context and Problem Statement

GeneChat's CLI (`genechat`) has 7 subcommands used for setup, annotation, and
maintenance. The CLI was built iteratively — each subcommand was added as needed
without a unifying design standard. This resulted in inconsistencies: no
`--version` flag, no help when run interactively without a subcommand (the
server starts and hangs on stdin), undifferentiated exit codes, no color, no
download progress, and raw tracebacks on unexpected errors.

[clig.dev](https://clig.dev/) provides a comprehensive, community-maintained set
of CLI design guidelines. This ADR documents the decision to adopt these
guidelines as the design standard for GeneChat's CLI.

## Decision Drivers

- New users who type `genechat` in a terminal get a confusing silent hang
- All errors exit with code 1, making scripted error handling impossible
- No `--version` flag (standard convention)
- No support path or documentation links in `--help`
- No download progress for multi-GB reference files
- Raw Python tracebacks on unexpected errors
- No color output to highlight errors/success

## Considered Options

1. **Adopt clig.dev guidelines wholesale** — Apply every recommendation
2. **Adopt selectively** — Evaluate each guideline for relevance and ROI
3. **Do nothing** — Keep the current CLI as-is

## Decision Outcome

**Chosen option: Option 2 — Selective adoption.**

The full evaluation is documented in the implementation plan (`docs/plans/cli-guidelines-alignment.md`,
commit cfcdd08). Of 40+ individual guidelines across 16 sections, the CLI was already
compliant on ~25. The remaining ~15 were evaluated and prioritized:

- **P0 (3 items):** TTY-aware help, KeyboardInterrupt handler, `--version`
- **P1 (5 items):** Named exit codes, help epilog links, examples, exception handler, `--json` on status
- **P2 (5 items):** Color output, download progress, network timeouts, gnomAD checkpoint recovery, SnpEff startup message
- **Deferred (3 items):** Spelling suggestions, formatted help, man pages — low ROI

### Consequences

**Good:**
- New users get immediate guidance instead of a silent hang
- Scripting support via named exit codes and `--json` on status
- Clean error messages with bug report link
- Progress feedback during long downloads

**Bad:**
- More code in cli.py (~150 lines for color helper, exit codes, exception handler)
- Tests need updating for new exit codes

### Confirmation

- `uv run pytest -x` passes with all new and updated tests
- `genechat` in interactive terminal shows help (not server hang)
- `genechat --version` prints version
- `genechat status --json` outputs valid JSON
- Ctrl-C prints "Interrupted." and exits 130

## Pros and Cons of the Options

### Option 1: Adopt wholesale

- Good: Complete alignment with community standard
- Bad: Some guidelines are low ROI (man pages, spelling suggestions, formatted help)
- Bad: Would require switching from argparse to click/typer for some features

### Option 2: Selective adoption (chosen)

- Good: High-impact improvements with minimal churn
- Good: Stays within argparse — no new dependencies
- Good: Clear priority tiers allow incremental delivery
- Bad: Not 100% clig.dev compliant (3 items deferred)

### Option 3: Do nothing

- Good: No code changes
- Bad: Poor first-run experience persists
- Bad: Missing standard conventions (`--version`, exit codes)

## More Information

- [clig.dev guidelines](https://clig.dev/#guidelines)
- Implementation plan: `docs/plans/cli-guidelines-alignment.md`
- Implemented in PR #35
