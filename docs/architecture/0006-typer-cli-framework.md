---
status: accepted
date: 2026-03-11
decision-makers: natecostello
related ADRs:
  - [0004-cli-guidelines-alignment](0004-cli-guidelines-alignment.md)
  - [0005-genome-ux-redesign](0005-genome-ux-redesign.md)
---

# Migrate CLI from argparse to Typer

## Context and Problem Statement

GeneChat's CLI uses Python's built-in `argparse` with 6 subcommands, a custom
color helper, parent parser inheritance for global flags, and hand-written
`_INTERACTIVE_HELP` text. ADR-0004 (CLI guidelines alignment) added exit codes,
`--version`, `--no-color`, `--json`, examples in help, and color output — all
implemented manually on top of argparse.

This works, but the amount of boilerplate is growing. The CLI is ~1,400 lines,
and roughly 40% is argument parser setup, help text construction, and color
plumbing rather than business logic. Argparse also lacks built-in tab completion,
which was the original trigger for this investigation.

## Decision Drivers

- **Tab completion**: Users type `genechat ann<TAB>` or `genechat annotate --ge<TAB>`
  and nothing happens. Shell completion would significantly improve the CLI UX,
  especially for `--genome <label>` where labels are user-defined.
- **Boilerplate reduction**: Each new flag requires parser setup, `args.flag_name`
  extraction, and forwarding to the handler function. Typer derives this from
  type annotations.
- **Help text quality**: argparse's default help formatting is plain and hard to
  customize without `RawDescriptionHelpFormatter` workarounds. Typer (via Rich)
  produces styled, readable help automatically.
- **Color output**: We maintain a custom `_style()` / `_red()` / `_green()` helper.
  Typer uses Rich for styled output natively, eliminating this code.
- **Consistency with function signatures**: The subcommand handlers (`_run_init`,
  `_run_status`, etc.) already accept typed parameters but are called via an
  `argparse.Namespace` intermediary. Some use `args` directly, others unpack
  attributes — the interface is inconsistent. Typer eliminates this mismatch by
  making the function signature *be* the CLI interface.

## Considered Options

1. **Stay on argparse, add `argcomplete`** — Bolt-on tab completion only
2. **Migrate to Click** — Mature, decorator-based CLI framework
3. **Migrate to Typer** — Type-hint-driven CLI built on Click

## Pros and Cons of the Options

### Option 1 — argparse + argcomplete

- Pros:
  - Minimal change; argcomplete is a small add-on
  - No rewrite of existing parser code
  - Supports dynamic completions (e.g., genome labels from config)
- Cons:
  - Does not reduce boilerplate — all the manual parser setup remains
  - Custom color helper still needed
  - Help text still plain argparse formatting
  - argcomplete requires user-side shell activation (`eval "$(register-python-argcomplete genechat)"`)
  - Does not address the `Namespace` → function signature mismatch

### Option 2 — Click

- Pros:
  - Mature, well-tested, widely adopted
  - Built-in shell completion (bash/zsh/fish) with dynamic support
  - `@click.group()` / `@click.command()` decorators are clean
  - `click.style()` and `click.echo()` for color output
  - Good testing via `CliRunner`
- Cons:
  - Decorator-heavy; parameters defined in decorators rather than function signatures
  - Type information duplicated between decorator and function signature
  - More verbose than Typer for the same result
  - Would still need manual `Annotated` or `click.Option` for complex defaults

### Option 3 — Typer (chosen)

- Pros:
  - Function signature *is* the CLI interface — zero duplication
  - Type annotations drive argument parsing, help text, and validation
  - Built-in shell completion (via Click) including dynamic completions
  - Rich integration for styled help and error output
  - `typer.Exit(code=N)` maps directly to our `ExitCode` enum
  - Testing via `CliRunner` (inherited from Click)
  - Our handler functions are already structured as `def _run_init(vcf_path: str, label: str | None = None, ...)` — Typer's model matches this exactly
  - Active development, Python 3.11+ support confirmed
- Cons:
  - Adds `typer` and `rich` as runtime dependencies (~2 MB)
  - Full rewrite of argument parser setup (not incremental)
  - Team needs to learn Typer conventions
  - Some argparse edge cases (parent parser inheritance, `dest` renaming) need
    Typer equivalents

## Decision Outcome

**Chosen option: 3 — Migrate to Typer.**

The CLI's function-based architecture maps naturally to Typer's model. The
migration eliminates ~400 lines of parser boilerplate and custom color code,
adds tab completion for free, and produces better help output. The two new
dependencies (typer, rich) are well-maintained and widely used in the Python
ecosystem.

### Key Migration Decisions

- **Entry point stays at `genechat.server:main`**, which delegates to `cli.main()`
- **`ExitCode` enum retained** — used via `raise typer.Exit(code=ExitCode.VCF_ERROR)`
- **Custom color helpers replaced** by `rich.print()` / `typer.echo()` with Rich markup
- **TTY-aware no-subcommand behavior preserved** — Typer's `callback` with `invoke_without_command=True`
- **`--no-color` handled via** `typer` + Rich's `NO_COLOR` env var support (already standard)
- **Tab completion** for `--genome` uses Typer's dynamic completion callback reading config
- **Testing** migrates from `main(argv)` + `capsys` to `typer.testing.CliRunner`

### Consequences

**Good:**
- Tab completion works out of the box (bash/zsh/fish)
- ~400 lines of boilerplate eliminated
- Help output is styled and readable
- Function signatures are the single source of truth for CLI interface
- `CliRunner` provides cleaner test assertions than `capsys` + `SystemExit`

**Bad:**
- Two new runtime dependencies (typer ~150 KB, rich ~1.5 MB)
- Every test that calls `main()` needs updating for `CliRunner`
- One-time migration effort across ~60 tests

**Neutral:**
- Click is pulled in transitively (Typer depends on it)
- Rich is pulled in transitively (Typer depends on it for styled output)

## Confirmation

- `uv run pytest -x` passes with all migrated tests
- `genechat --help` shows Rich-formatted help
- `genechat <TAB>` completes subcommands in bash/zsh
- `genechat annotate --genome <TAB>` completes registered genome labels
- `genechat --version` prints version
- `NO_COLOR=1 genechat status` produces no ANSI codes
- All `ExitCode` values preserved (verified by exit code tests)
- `genechat` with no subcommand in interactive terminal shows help
- `echo "" | genechat` starts MCP server (backward compatible)

## More Information

- [Typer documentation](https://typer.tiangolo.com/)
- [clig.dev guidelines](https://clig.dev/) (ADR-0004)
- Implementation plan: `docs/plans/typer-migration.md` (commit `0f74c62`)
- Implemented in PR #__ (to be filled)
