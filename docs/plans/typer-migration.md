# Plan: Migrate CLI from argparse to Typer

Migrate `src/genechat/cli.py` from argparse to Typer, eliminating parser
boilerplate and custom color helpers while adding shell completion support.

**ADR:** `docs/architecture/0006-typer-cli-framework.md`

---

## Scope

### In scope
- Rewrite `cli.py` argument parsing and dispatch from argparse to Typer
- Replace custom `_style()` / `_red()` / `_green()` / `_yellow()` / `_dim()` with Rich
- Add `--genome` dynamic tab completion (reads labels from config)
- Migrate `tests/test_cli.py` from `main(argv)` + `capsys` to `CliRunner`
- Add `typer` dependency to `pyproject.toml`
- Update entry point if needed

### Out of scope
- Business logic changes (annotation, download, status rendering, etc.)
- New CLI features or subcommands
- Changes to `server.py`, `config.py`, or other modules
- MCP tool changes

---

## Current State

| Metric | Value |
|--------|-------|
| `cli.py` | 1,592 lines |
| `test_cli.py` | 996 lines, ~60 test methods |
| Subcommands | 6: init, add, install, annotate, status, serve |
| Global flags | `--version`, `--no-color` |
| Color helper | 45 lines (custom `_style()` + 4 color functions) |
| Parser setup | ~140 lines (lines 121-293) |
| Entry point | `genechat.server:main` → `genechat.cli:main` |

---

## Migration Strategy

### Approach: In-place rewrite, one file at a time

The parser setup and dispatch logic (lines 121-293) is replaced entirely. The
handler functions (`_run_add`, `_run_install`, `_run_annotate`, `_run_status`,
`_run_init`, `_run_serve`) keep their business logic but have their signatures
updated to accept typed parameters instead of `argparse.Namespace`.

This is **not** incremental — argparse and Typer cannot coexist in the same
parser. The migration is a single PR that rewrites the parser layer and updates
all tests.

---

## Step 1: Add Typer dependency

**File:** `pyproject.toml`

```toml
dependencies = [
    ...,
    "typer>=0.12",
]
```

Typer pulls in `click` and `rich` transitively. No separate `rich` dependency
needed.

**Verification:** `uv sync && uv run python -c "import typer; print(typer.__version__)"`

---

## Step 2: Create Typer app and callback

**File:** `src/genechat/cli.py`

Replace the argparse setup (lines 121-293) with:

```python
import typer

app = typer.Typer(
    name="genechat",
    help="GeneChat MCP server for conversational personal genomics",
    epilog=(
        "Docs:   https://github.com/natecostello/genechat-mcp#readme\n"
        "Issues: https://github.com/natecostello/genechat-mcp/issues"
    ),
    no_args_is_help=False,  # We handle no-args ourselves for TTY detection
    rich_markup_mode="rich",
)
```

Add a callback for `--version`, `--no-color`, and the TTY-aware no-subcommand
behavior:

```python
@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", help="Show version and exit")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable color output")] = False,
):
    if version:
        print(f"genechat {__version__}")
        raise typer.Exit()
    if no_color:
        os.environ["NO_COLOR"] = "1"  # Rich respects this
    if ctx.invoked_subcommand is None:
        if getattr(sys.stdin, "isatty", lambda: False)():
            print(_INTERACTIVE_HELP, end="")
            raise typer.Exit()
        else:
            _run_serve()
```

The `main()` function becomes:

```python
def main(argv: list[str] | None = None):
    try:
        app(argv, standalone_mode=False)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except click.exceptions.Exit as e:
        sys.exit(e.exit_code)
    except SystemExit:
        raise
    except Exception as exc:
        # Rich-styled error if available, plain text fallback
        rprint(f"\n[red]Unexpected error:[/red] {exc}", file=sys.stderr)
        print(
            "Please report this at https://github.com/natecostello/genechat-mcp/issues",
            file=sys.stderr,
        )
        sys.exit(ExitCode.GENERAL_ERROR)
```

**Note:** `standalone_mode=False` prevents Typer/Click from calling `sys.exit()`
directly, so our exception handlers work. We catch `click.exceptions.Exit` to
propagate exit codes correctly.

---

## Step 3: Migrate subcommand handlers

Each subcommand handler gets a `@app.command()` decorator and typed parameters
replacing the `argparse.Namespace` argument.

### 3a. `serve`

```python
@app.command()
def serve():
    """Start the MCP server."""
    _run_serve()
```

Simplest subcommand — no arguments.

### 3b. `add`

```python
@app.command()
def add(
    vcf_path: Annotated[str, typer.Argument(help="Path to your VCF (.vcf.gz)")],
    label: Annotated[str | None, typer.Option(help="Name for this genome")] = None,
):
    """Register a VCF file."""
    _run_add(vcf_path, label)
```

`_run_add()` already takes `(vcf_path_str: str, label: str | None)` — no
internal changes needed.

### 3c. `install`

```python
@app.command()
def install(
    gwas: Annotated[bool, typer.Option("--gwas", help="Install GWAS Catalog (~58 MB download)")] = False,
    seeds: Annotated[bool, typer.Option("--seeds", help="Refresh seed data from upstream APIs")] = False,
    force: Annotated[bool, typer.Option("--force", help="Re-download even if present")] = False,
):
    """Install genome-independent reference databases."""
    _run_install(gwas=gwas, seeds=seeds, force=force)
```

**Internal change:** `_run_install(args)` → `_run_install(gwas, seeds, force)`.
Replace `getattr(args, "gwas", False)` with direct parameter access.

### 3d. `status`

```python
@app.command()
def status(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """Show genome info and annotation state."""
    _run_status(json_output=json_output)
```

`_run_status()` already takes `json_output: bool` — no internal changes needed.

### 3e. `annotate`

```python
def _genome_completer(incomplete: str) -> list[str]:
    """Dynamic completion for --genome: returns matching genome labels."""
    try:
        config = load_config()
        return [l for l in config.genomes if l.startswith(incomplete)]
    except Exception:
        return []

@app.command()
def annotate(
    clinvar: Annotated[bool, typer.Option("--clinvar", help="Re-annotate ClinVar layer")] = False,
    gnomad: Annotated[bool, typer.Option("--gnomad", help="Re-annotate gnomAD layer")] = False,
    snpeff: Annotated[bool, typer.Option("--snpeff", help="Re-annotate SnpEff layer")] = False,
    dbsnp: Annotated[bool, typer.Option("--dbsnp", help="Re-annotate dbSNP layer")] = False,
    all_layers: Annotated[bool, typer.Option("--all", help="Re-annotate all layers")] = False,
    force: Annotated[bool, typer.Option("--force", help="Override guards")] = False,
    genome: Annotated[str | None, typer.Option(help="Which genome to annotate", autocompletion=_genome_completer)] = None,
):
    """Build or update the annotation database (patch.db)."""
    _run_annotate(
        clinvar=clinvar, gnomad=gnomad, snpeff=snpeff, dbsnp=dbsnp,
        all_layers=all_layers, force=force, genome=genome,
    )
```

**Internal change:** `_run_annotate(args)` → `_run_annotate(clinvar, gnomad, snpeff, dbsnp, all_layers, force, genome)`. This is the largest signature change. Replace all `args.clinvar` etc. with direct parameters. The `--all` flag maps to `all_layers` to avoid shadowing Python's `all()` builtin.

### 3f. `init`

```python
@app.command()
def init(
    vcf_path: Annotated[str, typer.Argument(help="Path to your raw VCF (.vcf.gz)")],
    label: Annotated[str | None, typer.Option(help="Name for this genome")] = None,
    gnomad: Annotated[bool, typer.Option("--gnomad", help="Also annotate gnomAD frequencies")] = False,
    dbsnp: Annotated[bool, typer.Option("--dbsnp", help="Also download dbSNP (~20 GB)")] = False,
    gwas: Annotated[bool, typer.Option("--gwas", help="Also download GWAS Catalog")] = False,
):
    """Full first-time setup for a VCF file."""
    _run_init(vcf_path=vcf_path, label=label, gnomad=gnomad, dbsnp=dbsnp, gwas=gwas)
```

**Internal change:** `_run_init(args)` → `_run_init(vcf_path, label, gnomad, dbsnp, gwas)`. Currently `_run_init` constructs `argparse.Namespace` objects to pass to `_run_install` and `_run_annotate` — these become direct keyword calls after the other handlers are updated.

---

## Step 4: Replace color helpers with Rich

**Remove:** `_COLOR_ENABLED`, `_color_enabled()`, `_style()`, `_red()`, `_green()`, `_yellow()`, `_dim()` (lines 49-93, ~45 lines).

**Replace with Rich markup** throughout the file:

| Before | After |
|--------|-------|
| `_red("Error:")` | `[red]Error:[/red]` via `rich.print()` |
| `_green("Done")` | `[green]Done[/green]` |
| `_yellow("Warning:")` | `[yellow]Warning:[/yellow]` |
| `_dim(path)` | `[dim]{path}[/dim]` |
| `print(f"{_red('Error:')} ...")` | `rprint(f"[red]Error:[/red] ...")` |

Rich respects `NO_COLOR` env var natively. The `--no-color` callback sets
`os.environ["NO_COLOR"] = "1"` which Rich checks automatically.

**Import:** `from rich import print as rprint` — use `rprint` for styled output,
keep `print` for plain output (JSON, MCP server messages).

---

## Step 5: Replace sys.exit() with typer.Exit

**Current pattern:**
```python
sys.exit(ExitCode.VCF_ERROR)
```

**New pattern:**
```python
raise typer.Exit(code=ExitCode.VCF_ERROR)
```

The `ExitCode` enum is retained unchanged. All `sys.exit()` calls within
subcommand handlers become `raise typer.Exit(code=...)`. The `main()` wrapper
catches these and calls `sys.exit()` with the correct code.

**Exception:** `sys.exit()` in the top-level exception handler stays as-is since
it's outside Typer's dispatch.

---

## Step 6: Migrate tests to CliRunner

**File:** `tests/test_cli.py`

### Test invocation pattern change

Before:
```python
from genechat.cli import main

with pytest.raises(SystemExit) as exc_info:
    main(["status"])
assert exc_info.value.code == 0
out = capsys.readouterr().out
```

After:
```python
from typer.testing import CliRunner
from genechat.cli import app

runner = CliRunner()
result = runner.invoke(app, ["status"])
assert result.exit_code == 0
assert "Genomes:" in result.output
```

### Key changes across tests

1. **Replace `capsys` with `result.output` and `result.stderr`** (CliRunner
   captures both)
2. **Replace `pytest.raises(SystemExit)` with `result.exit_code` assertion** —
   CliRunner doesn't raise SystemExit
3. **Replace `main(argv)` calls with `runner.invoke(app, argv)`**
4. **`capsys` fixture removed** from test methods that use CliRunner
5. **Tests that monkeypatch `sys.stdin.isatty`** may need adjustment — CliRunner
   has its own stdin handling. Use `runner.invoke(app, [], input="")` for
   non-TTY simulation.

### Fixture

Add a shared fixture:

```python
@pytest.fixture
def cli():
    return CliRunner()
```

Typer's `CliRunner` does not support `mix_stderr`; stdout and stderr are mixed
in `result.output`. Tests use `result.output` for all assertions.

---

## Step 7: Update entry point

The entry point in `pyproject.toml` stays as:

```toml
[project.scripts]
genechat = "genechat.server:main"
```

`server.py:main()` already delegates to `cli.main()`. No change needed — the
interface (`main()` callable with no required args) is preserved.

---

## Step 8: Shell completion setup

Typer generates completion scripts via:

```bash
genechat --install-completion bash   # or zsh, fish
```

This is built-in to Typer — no code needed. Add a note to README under a
"Shell Completion" section:

````markdown
### Shell Completion

Enable tab completion for your shell:

```bash
genechat --install-completion
```

This enables completion for subcommands, flags, and `--genome` labels.
````

---

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Add `typer>=0.12` dependency |
| `src/genechat/cli.py` | Rewrite parser layer (~250 lines replaced), remove color helpers (~45 lines), update handler signatures, replace `sys.exit` with `typer.Exit` |
| `tests/test_cli.py` | Migrate all ~60 tests to CliRunner |
| `README.md` | Add shell completion section |

**Estimated net line change:** cli.py shrinks by ~200 lines (parser boilerplate
+ color helpers eliminated, Typer decorators are more compact). test_cli.py
stays roughly the same size (CliRunner is slightly more concise but similar).

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Typer help output differs from argparse | Verify all help text renders correctly; use `rich_markup_mode="rich"` for formatting control |
| `standalone_mode=False` changes error behavior | Comprehensive exception handler in `main()` catches all exit paths |
| TTY detection differs in CliRunner | Test both TTY and non-TTY paths explicitly; CliRunner simulates non-TTY by default |
| `--all` flag name shadows builtin | Rename parameter to `all_layers`, keep CLI flag as `--all` |
| Dynamic completion fails on broken config | `_genome_completer` wraps in try/except, returns empty list on error |
| Rich markup in error messages leaks to non-TTY | Rich respects `NO_COLOR`; also test with `NO_COLOR=1` |

---

## Verification

- `uv run pytest -x` passes (all ~60 CLI tests migrated)
- `uv run ruff check . && uv run ruff format .` clean
- `genechat --help` shows Rich-formatted help with epilog links
- `genechat --version` prints version
- `genechat` (interactive) shows help; `echo "" | genechat` starts server
- `genechat annotate --genome <TAB>` completes genome labels
- `genechat <TAB>` completes subcommand names
- `NO_COLOR=1 genechat status` produces no ANSI codes
- `genechat status --json` outputs valid JSON (no Rich markup in JSON)
- Exit codes preserved: `genechat init /nonexistent` exits 4, Ctrl-C exits 130
- `genechat install` (no flags) shows usage guidance
- `genechat annotate` (no flags, multi-genome) shows usage with genome list
