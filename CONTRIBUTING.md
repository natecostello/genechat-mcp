# Contributing

This project uses [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skills to maintain contribution quality. Contributors are expected to use Claude Code with the project's bundled skills.

## Quick Start

1. Fork and clone the repo
2. Install dev dependencies (choose one):

   **Option A — Homebrew (macOS/Linux)**
   ```bash
   brew install python3 uv ruff
   ```

   **Option B — Nix + direnv (reproducible, any platform)**
   ```bash
   # Install Nix: https://nixos.org/download/
   # Install direnv: https://direnv.net/docs/installation.html
   direnv allow   # loads flake.nix → python3, uv, ruff
   ```

3. Follow `docs/FIRST_RUN.md` to initialize project memory
4. The contributing workflow skills ship with the repo in `.claude/skills/`

## Workflow

Every change — feature, fix, refactor, docs, or skill — follows this process:

### 1. File a GitHub issue

File a GitHub issue describing the problem and proposed solution. Use the feature request or bug report template. Small fixes can reference an existing issue.

### 2. Create a branch

Use `/using-git-worktrees` to create an isolated worktree for your work, or create a branch manually.

### 3. Brainstorm the design

Run `/brainstorming` to explore the problem space before writing code. This skill asks clarifying questions, considers alternatives, and produces a design you can review before committing to an approach.

### 4. Write an implementation plan

Run `/writing-plans` to produce a structured plan in `docs/plans/` (a local working directory, not committed). The plan breaks the work into 2-3 self-contained tasks with exact file paths, code, and test commands. Paste the plan into your PR body when you open it.

### 5. Execute the plan

Run `/executing-plans` to implement the plan with checkpoints between tasks.

### 6. Verify before claiming done

`/verification-before-completion` triggers automatically before any completion claim. It requires running verification commands and confirming output — no "it should work" allowed.

### 7. Self-review

Run `/requesting-code-review` to dispatch a code review subagent that checks your work against the plan and project standards.

### 8. Finalize

`/finishing-a-development-branch` triggers automatically when work is complete. It guides you through merge prep, PR creation, or cleanup.

### 9. Open a pull request

Use the PR template. Include:
- Reference to the GitHub issue
- The implementation plan (paste into the collapsible details block)
- Atomic commits — one logical change per commit

## Skill Reference

These skills ship with the repo in `.claude/skills/`. They are loaded automatically by Claude Code.

### Auto-triggered (no explicit invocation needed)

| Skill | When it triggers |
|---|---|
| `/verification-before-completion` | Before any success or completion claim |
| `/code-simplification` | After verification passes, as a pipeline step |
| `/finishing-a-development-branch` | When implementation is complete and tests pass |

### Explicit invocation

| Skill | When to use |
|---|---|
| `/brainstorming` | Before creative work — features, components, behavior changes |
| `/writing-plans` | When you have requirements and need an implementation plan |
| `/executing-plans` | To execute a written plan with checkpoints |
| `/requesting-code-review` | Before submitting a PR, to self-review |
| `/systematic-debugging` | When encountering bugs or test failures |
| `/using-git-worktrees` | To create an isolated worktree for feature work |
| `/writing-clearly-and-concisely` | Final editing pass on prose (docs, commit messages) |
| `/writing-skills` | When creating or modifying skills in `.claude/skills/` |
| `/codify-subsystem` | To create or update a subsystem SPEC.md |

## Project-Specific Guidelines

- **Dependencies.** If you add a dependency, update `flake.nix` (Nix), the Homebrew instructions in this file's Quick Start, the dep check in `.envrc.d/setup.sh`, and the Prerequisites section in `README.md`.
- **Documentation.** If your change affects usage, output, or setup, update `README.md` to match.
- **Subsystem specs.** When a directory grows to 3+ files or contains important invariants, use `/codify-subsystem` to create a SPEC.md. See the Architecture section of CLAUDE.md.

## Contributing Skills

Skills live in `.claude/skills/<skill-name>/SKILL.md`. To add or modify a skill:

1. Use `/writing-skills` — it applies TDD to process documentation
2. Follow the same issue, plan, PR workflow as any other contribution
3. Test the skill by running it in a fresh Claude Code session

## Attribution

Several skills are derived from upstream open-source projects:

- **obra/superpowers** — The following skills originate from [obra/superpowers](https://github.com/obra/superpowers). MIT License. See [LICENSE.superpowers](LICENSE.superpowers). Sync status tracked in `.claude/skills/UPSTREAM-superpowers.md`.
  - Tracked in this repo: `brainstorming`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `verification-before-completion`, `writing-plans`, `writing-skills`
  - Available locally (not committed): `using-superpowers`
- **writing-clearly-and-concisely** — Based on William Strunk Jr.'s *The Elements of Style* (1918, public domain).

If you contribute a skill derived from another source, add appropriate attribution and a license file.

## Code of Conduct

Be kind, be constructive, assume good intent.
