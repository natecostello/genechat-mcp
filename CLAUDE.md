# GeneChat MCP

## Purpose

A local-first MCP server enabling conversational queries about personal genomic data.

## First-Run Setup

On first use in a fresh clone, follow `docs/FIRST_RUN.md` to initialize project memory files.

## Environment

- **Dependencies**: python3, uv, ruff. Two supported install methods:
  - **Nix (reproducible):** `flake.nix` + direnv. Add packages to `buildInputs`.
  - **Homebrew (quick):** `brew install python3 uv ruff`.
- **Initialization**: `.envrc` sources `use flake` (if Nix is present) and runs scripts from `.envrc.d/` and `.envrc.local.d/`. The `setup.sh` script verifies required tools are on PATH regardless of install method.
- If you add a dependency to `flake.nix`, also add it to the Homebrew instructions in `CONTRIBUTING.md` and the check in `.envrc.d/setup.sh`. Ask the user to restart the session so direnv reloads.

## Architecture

> **Organizing principle:** Code is organized so any subsystem fits in a single
> agent context window. Self-contained units over shared abstractions.

### Directory Structure

**Default: Vertical slices (feature-based)**

Each feature or subsystem gets its own directory containing all its components:
handler, validation, data access, types, tests. An agent should be able to
understand a feature by reading one directory.

    features/
      feature-name/
        SPEC.md          # Subsystem specification (see below)
        handler.ext      # Entry point
        types.ext        # Feature-specific types
        store.ext        # Data access
        tests/
          test_handler.ext

**When vertical slices don't fit:**
- **Libraries/packages:** Organize by module. Each module gets a SPEC.md.
- **CLI tools:** Organize by command. Each command is a slice.
- **Data pipelines:** Organize by stage. Each stage is a slice.
- **The principle stays the same:** one directory = one context load for an agent.

### Subsystem Specifications (SPEC.md)

Every non-trivial directory gets a `SPEC.md` — a machine-readable specification
scoped to that subsystem. Agents load the nearest SPEC.md when working on files.

**When to create one:** When a directory has 3+ files or contains invariants an
agent could violate without knowing. Use `/codify-subsystem` to create one.

**Format:** See `docs/spec-template.md`.

**Routing:** Agents walk up the directory tree from the file being modified and
load the nearest SPEC.md. This mirrors how .gitignore resolution works.

### Subsystem Map

| Subsystem | Path | Purpose |
|---|---|---|
| GeneChat | `src/genechat/` | MCP server: VCF parsing, variant lookup, genomic tools |
| Skills | `.claude/skills/` | Reusable agent instructions as Markdown with YAML frontmatter |

For detailed specifications, read the SPEC.md in each subsystem directory.

### Context Budgeting

- Each subsystem should be understandable from its SPEC.md + source files
  loaded together in ~50% of a context window.
- If a subsystem exceeds this, split it into sub-features.
- Prefer duplication over deep cross-subsystem coupling — an agent working on
  Feature A should rarely need to load Feature B's code.
- **Cross-cutting tasks:** Load the primary subsystem's full spec. For adjacent
  subsystems, load only the Public Interface section (contracts, not internals).
  If a task needs >2 full specs, split it along subsystem boundaries.

### Testing Convention

Tests are anchored to SPEC.md items. Each invariant (INV-N) gets a positive
test verifying the invariant holds. Each failure mode (FAIL-N) gets a negative
test verifying graceful handling. Test names include the spec item ID for
traceability (e.g., test_inv1_total_equals_sum, test_fail2_rejects_expired).

This helps agents write tests that verify *requirements*, not *implementations*.
See docs/spec-template.md for the coverage table format.

## Workflow

All changes follow the process in [CONTRIBUTING.md](CONTRIBUTING.md):
issue, brainstorm (`/brainstorming`), plan (`/writing-plans`), execute
(`/executing-plans`), verify (`/verification-before-completion`), review
(`/requesting-code-review`), finalize (`/finishing-a-development-branch`), PR.

## Writing Standards

- Structured with headers, bullet points, and blockquotes for key statements.
- No filler or padding. Dense, scannable, useful.

## Lessons Learned

<!-- Add project-specific lessons as they arise. -->

## Contributing

All changes follow the workflow in [CONTRIBUTING.md](CONTRIBUTING.md). File a GitHub issue, use the bundled skills to brainstorm, plan, execute, verify, and review, then open a PR with the plan and issue reference.
