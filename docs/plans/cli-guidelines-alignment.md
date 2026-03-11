# Plan: CLI Guidelines Alignment

Audit of GeneChat CLI against [clig.dev guidelines](https://clig.dev/#guidelines), with implementation plan for applicable improvements.

**Context:** GeneChat's CLI (`src/genechat/cli.py`, 1323 lines) uses argparse with 7 subcommands: `init`, `add`, `annotate`, `install`, `update`, `status`, `serve`. It is used primarily by humans setting up their genome for MCP server queries. The MCP server itself (`serve`) is machine-consumed. Most subcommands run once or rarely (setup/maintenance), not continuously.

---

## Section 1: The Basics

### 1.1 Use a command-line argument parsing library
**Status:** COMPLIANT. Uses Python's built-in `argparse`.
**Action:** None.

### 1.2 Return zero exit code on success, non-zero on failure
**Status:** PARTIAL. Most error paths call `sys.exit(1)`. However, several subcommands use bare `return` on success without explicit `sys.exit(0)` — this is fine in Python (implicit 0). The issue is that _all_ failures use exit code 1 indiscriminately. clig.dev says "map the non-zero exit codes to the most important failure modes."
**Action:** APPLY. Define named exit codes for distinct failure modes:
- 1: general/unknown error
- 2: invalid usage (bad arguments, missing required input)
- 3: configuration error (missing config, invalid config)
- 4: VCF error (file not found, invalid VCF, missing index)
- 5: external tool error (bcftools/snpEff not found or failed)
- 6: network error (download failed)

**Implementation:** Add an `ExitCode` IntEnum to `cli.py`. Replace `sys.exit(1)` calls with the appropriate code. Update tests that assert `exc_info.value.code == 1` to use the new codes. Document exit codes in `--help` output and README.

**Files:** `src/genechat/cli.py`, `tests/test_cli.py`, `README.md`

### 1.3 Send output to stdout
**Status:** COMPLIANT. Primary output (status tables, MCP config JSON, progress) goes to stdout.
**Action:** None.

### 1.4 Send messaging to stderr
**Status:** COMPLIANT. Errors use `print(..., file=sys.stderr)`. Warnings go to stderr.
**Action:** None. One minor improvement: some progress messages during annotation (e.g., "Downloading ClinVar...") are informational and go to stdout. These could arguably go to stderr so that only structured output (MCP JSON config) goes to stdout. However, since genechat commands aren't typically piped, this is low priority.

---

## Section 2: Help

### 2.1 Display help text when -h or --help is passed
**Status:** COMPLIANT. argparse handles `-h`/`--help` automatically for the top-level command and all subcommands.
**Action:** None.

### 2.2 Display concise help text when run with no arguments
**Status:** NON-COMPLIANT. Running `genechat` with no arguments silently starts the MCP server (falls through to `_run_serve`). A user who types `genechat` expecting help gets... nothing visible (the server blocks on stdio). This is the worst possible experience for a new user.
**Action:** APPLY. This is a significant UX improvement. When `genechat` is run with no subcommand:
- If stdin is a TTY (interactive terminal): print concise help text showing available subcommands, a quick-start example, and exit. The server should require explicit `genechat serve`.
- If stdin is NOT a TTY (piped/MCP client): start the server as today (backward compatible with existing MCP configs).

**Implementation:**
1. In `main()`, when `args.command is None`: check `sys.stdin.isatty()`.
2. If TTY: print concise help (description, common commands, example, link to docs) and exit 0.
3. If not TTY: call `_run_serve()` as today.
4. This preserves backward compatibility with MCP client configurations that invoke `genechat` without `serve`.

**Files:** `src/genechat/cli.py`, `tests/test_cli.py`

**Risk:** Low. MCP clients pipe stdin (not a TTY), so they'll still get the server. Only interactive terminal users are affected, and they currently get a confusing hang.

### 2.3 Provide a support path for feedback and issues
**Status:** NON-COMPLIANT. No GitHub link in help text.
**Action:** APPLY. Add the GitHub repo URL to the argparse `epilog` so it appears at the bottom of `--help` output.

**Implementation:** Set `parser.epilog = "Report issues: https://github.com/natecostello/genechat-mcp/issues"` and `parser.formatter_class = argparse.RawDescriptionHelpFormatter`.

**Files:** `src/genechat/cli.py`

### 2.4 Link to web documentation in help text
**Status:** NON-COMPLIANT. No links to README or docs.
**Action:** APPLY (low effort). Add `"Documentation: https://github.com/natecostello/genechat-mcp#readme"` to the epilog alongside the issues link.

**Files:** `src/genechat/cli.py`

### 2.5 Lead with examples
**Status:** NON-COMPLIANT. argparse help shows flags/args but no usage examples.
**Action:** APPLY. Add example invocations to key subcommand help text using argparse `description` or `epilog` fields. Priority subcommands: `init`, `annotate`, `status`.

**Implementation:** For each subcommand parser, set `description` to include 1-2 example invocations. For example, `init_p.description = "Full first-time setup for a VCF file.\n\nExamples:\n  genechat init /path/to/raw.vcf.gz\n  genechat init /path/to/raw.vcf.gz --label personal --gnomad"`.

**Files:** `src/genechat/cli.py`

### 2.6 Suggest corrections for mistyped commands
**Status:** NON-COMPLIANT. Typing `genechat inti` gives argparse's generic "invalid choice" error.
**Action:** DEFER. argparse doesn't support spelling suggestions natively. Implementing this would require switching to a library like `click` or `typer`, or writing custom fuzzy-matching logic. Low ROI given 7 subcommands with distinct names.

### 2.7 Display most common flags first
**Status:** COMPLIANT. argparse displays flags in definition order, and flags are already ordered by importance (e.g., `--label` before `--gnomad`).
**Action:** None.

### 2.8 Use formatting in help text
**Status:** NON-COMPLIANT. Help text is plain unformatted argparse output.
**Action:** DEFER. Adding rich formatting (bold headings, etc.) requires either `rich-argparse` or switching to `click`/`typer`. Nice-to-have but not high priority for a tool used infrequently.

---

## Section 3: Documentation

### 3.1 Provide web-based documentation
**Status:** COMPLIANT. README.md on GitHub serves as web documentation. Docs are searchable and linkable.
**Action:** None.

### 3.2 Provide terminal-based documentation
**Status:** COMPLIANT. `--help` on all subcommands provides terminal docs. `genechat status` shows current system state.
**Action:** None (improved by Section 2 changes above).

### 3.3 Consider providing man pages
**Status:** NON-COMPLIANT. No man pages.
**Action:** SKIP. Man pages are not standard for Python CLI tools installed via pip/uv. The target user (technically capable but not a sysadmin) is more likely to use `--help` or the GitHub README. Low ROI.

---

## Section 4: Output

### 4.1 Human-readable output is paramount
**Status:** COMPLIANT. All output is designed for human reading. The MCP server (machine interface) uses a separate protocol.
**Action:** None.

### 4.2 Support --json for machine-readable output
**Status:** NON-COMPLIANT. No `--json` flag on any subcommand.
**Action:** APPLY (targeted). Add `--json` to `genechat status` — this is the subcommand most likely to be consumed by scripts (checking annotation state, VCF registration). The output would be a JSON object with genome configs, annotation metadata, and reference installation status.

**Implementation:** Add `--json` flag to `status` subparser. In `_run_status`, if `args.json`: collect the same data but emit it as `json.dumps(data, indent=2)` to stdout instead of the formatted table.

**Files:** `src/genechat/cli.py`, `tests/test_cli.py`

### 4.3 Display output on success, but keep it brief
**Status:** COMPLIANT. Commands print concise confirmation on success (e.g., "VCF registered as 'personal'"). `init` is more verbose but justified given its multi-step nature.
**Action:** None.

### 4.4 If you change state, tell the user
**Status:** COMPLIANT. `init`, `add`, `annotate` all report what they did. Config writes are announced. Annotation layers report completion with variant counts.
**Action:** None.

### 4.5 Make it easy to see the current state
**Status:** COMPLIANT. `genechat status` shows complete system state (genomes, annotations, references).
**Action:** None.

### 4.6 Suggest commands the user should run next
**Status:** COMPLIANT. `init` suggests `genechat install --gwas`. `status` suggests `genechat update`. `annotate` with no flags shows current state and implies what to do next. `update` suggests `genechat update --apply`.
**Action:** None.

### 4.7 Actions crossing program boundary should be explicit
**Status:** COMPLIANT. Downloads announce what they're fetching. Config writes announce where they write. File creation is reported.
**Action:** None.

### 4.8 Use color with intention
**Status:** NON-COMPLIANT. No color is used anywhere. All output is plain text.
**Action:** APPLY (moderate effort). Add minimal color for key UI elements:
- Red for errors
- Yellow for warnings
- Green for success confirmations
- Dim for secondary information (paths, sizes)

Must respect `NO_COLOR`, `TERM=dumb`, non-TTY stdout, and `--no-color` flag.

**Implementation:** Add a small `_style()` helper in cli.py that wraps text in ANSI codes when color is enabled. Check `NO_COLOR` env var, `TERM`, and TTY status. Add `--no-color` to the top-level parser.

**Files:** `src/genechat/cli.py`, `tests/test_cli.py`

**Alternative:** Use `rich` library for output formatting. This is more capable but adds a dependency. Given genechat's minimal output needs, a lightweight helper is preferable.

### 4.9 Disable color if not in a terminal
**Status:** N/A (no color currently). Will be addressed by 4.8 implementation.
**Action:** Included in 4.8.

### 4.10 Don't display animations if stdout is not a TTY
**Status:** COMPLIANT. Progress output uses simple text (no spinners or animations).
**Action:** None.

### 4.11 Don't treat stderr like a log file
**Status:** COMPLIANT. No log level labels (ERR, WARN) in output. Errors are written as natural-language sentences.
**Action:** None.

---

## Section 5: Errors

### 5.1 Catch errors and rewrite them for humans
**Status:** COMPLIANT. Most error paths provide actionable messages. Examples: "VCF file not found: /path. If your VCF is on an encrypted volume, make sure it is mounted.", "ClinVar queries require a patch database. Run: genechat annotate --all".
**Action:** None.

### 5.2 Signal-to-noise ratio
**Status:** COMPLIANT. Errors are concise, one message per failure. No stack traces shown to users (except for unexpected errors in annotation, where RuntimeError is raised).
**Action:** MINOR IMPROVEMENT. Wrap the top-level `main()` in a try/except for unexpected exceptions. Print a clean error message + link to file a bug report instead of a raw traceback.

**Implementation:** Add a top-level try/except in `main()` that catches `Exception` (but not `SystemExit` or `KeyboardInterrupt`). Print: "Unexpected error: {e}\nPlease report this at https://github.com/natecostello/genechat-mcp/issues" to stderr, then `sys.exit(1)`.

**Files:** `src/genechat/cli.py`

### 5.3 Make it effortless to submit bug reports
**Status:** NON-COMPLIANT. No bug report facilitation.
**Action:** APPLY (via 5.2 above). The top-level error handler will include the issues URL. Consider pre-populating a GitHub issue URL with version info (stretch goal, not in initial implementation).

---

## Section 6: Arguments and Flags

### 6.1 Prefer flags to args
**Status:** MOSTLY COMPLIANT. Only `init` and `add` use positional args (`vcf_path`), which is appropriate — they're the primary action argument. Everything else uses flags.
**Action:** None.

### 6.2 Have full-length versions of all flags
**Status:** COMPLIANT. All flags use `--long-form`. No single-letter shortcuts are defined (except `-h` from argparse).
**Action:** None. Could add `-l` for `--label`, `-g` for `--genome` as convenience shortcuts, but not required.

### 6.3 Use standard names for flags
**Status:** MOSTLY COMPLIANT. `--force` (install), `--all` (annotate) follow conventions. `--json` (status) will be added per Section 4.
**Action:** APPLY. Add `--version` flag to the top-level parser.

**Implementation:** `parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")`. Import `__version__` from `genechat.__init__` (which reads from `importlib.metadata`).

**Files:** `src/genechat/__init__.py`, `src/genechat/cli.py`

### 6.4 Make the default the right thing for most users
**Status:** COMPLIANT. `init` defaults to SnpEff + ClinVar (the minimum useful annotation). gnomAD/dbSNP are opt-in because they're large downloads. `serve` defaults to stdio transport. Config search follows platform conventions.
**Action:** None.

### 6.5 Never require a prompt
**Status:** COMPLIANT. No interactive prompts exist. All input is via flags and args.
**Action:** None.

### 6.6 Do not read secrets directly from flags
**Status:** COMPLIANT. No secrets are handled by the CLI. VCF paths are not secrets (though they're sensitive — the VCF content is the sensitive part).
**Action:** None.

---

## Section 7: Interactivity

### 7.1 Only use prompts if stdin is a TTY
**Status:** COMPLIANT. No prompts are used.
**Action:** None.

---

## Section 8: Subcommands

### 8.1 Be consistent across subcommands
**Status:** MOSTLY COMPLIANT. `--genome` flag is consistently named across `annotate` and `update`. Output formatting is consistent (headers with `===`, indented details). Error messages follow the same pattern.
**Action:** None.

### 8.2 Don't have ambiguous or similarly-named commands
**Status:** REVIEW NEEDED. `update` vs `annotate` could be confusing:
- `annotate` rebuilds annotation layers in patch.db
- `update` checks for newer reference versions and optionally re-annotates

The distinction is: `annotate` = "build/rebuild the database", `update` = "check if sources are stale". This is clear enough given the `--apply` flag on `update`.
**Action:** SKIP. The current naming is defensible. `install` vs `update` is clearer than alternatives like `refresh` or `sync`.

---

## Section 9: Robustness

### 9.1 Validate user input
**Status:** COMPLIANT. VCF paths are validated (exists, readable, has index). Region formats are regex-validated. rsIDs are regex-validated. Genome labels are checked against config.
**Action:** None.

### 9.2 Responsive is more important than fast
**Status:** MOSTLY COMPLIANT. Annotation prints step headers before starting work. Downloads print what they're fetching.
**Action:** MINOR IMPROVEMENT. Some annotation steps (especially SnpEff on large chromosomes) can take 30+ seconds before any output. The per-chromosome progress (`chr1 (1/25)...`) is good, but the initial SnpEff JVM startup produces no output. Add a "Starting SnpEff (JVM may take a few seconds)..." message before the first chromosome.

**Files:** `src/genechat/cli.py`

### 9.3 Show progress if something takes a long time
**Status:** PARTIAL. Annotation shows per-chromosome progress with variant counts. Downloads show no progress (just "Downloading ClinVar..." then silence until done).
**Action:** APPLY. Add download progress indication. The simplest approach: print downloaded size periodically during large downloads (gnomAD chromosomes, dbSNP).

**Implementation:** The download functions in `src/genechat/download.py` use urllib or subprocess. Add a progress callback that prints `\r  Downloaded: {size} MB` to stderr with `flush=True` for downloads > 10 MB.

**Files:** `src/genechat/download.py`

### 9.4 Make things time out
**Status:** PARTIAL. Network operations have no explicit timeouts. The `update` command's HTTP HEAD request to check ClinVar versions could hang indefinitely.
**Action:** APPLY. Add timeouts to all network operations (downloads, version checks). Default: 30 seconds for version checks, 300 seconds for large file downloads.

**Implementation:** Pass `timeout=` to urllib requests. For subprocess-based downloads (bcftools pipes), the subprocess timeout is less critical since the user can Ctrl-C.

**Files:** `src/genechat/download.py`, `src/genechat/update.py`

### 9.5 Make it recoverable / crash-only
**Status:** PARTIAL. Annotation sets metadata `status="pending"` before starting, `status="failed"` on exception, `status="complete"` on success. This allows re-running to pick up where it left off. However, gnomAD incremental mode (download-annotate-delete per chromosome) does NOT record which chromosomes are done — if interrupted, it restarts all chromosomes.
**Action:** DEFER. Record per-chromosome completion in patch.db metadata for gnomAD incremental annotation. On restart, skip chromosomes already completed. Deferred because it involves schema/metadata changes to patch.db that warrant a separate PR with dedicated tests.

**Implementation:** Store a `gnomad_chromosomes_done` list in patch.db metadata. After each chromosome completes, append it. On start, read the list and skip completed chromosomes. On full completion, remove the list and set `status="complete"`.

**Files:** `src/genechat/cli.py` (gnomAD annotation function)

---

## Section 10: Future-proofing

### 10.1 Keep changes additive
**Status:** COMPLIANT. Recent changes (multi-genome, patch.db, pip-installable) have all been additive with backward compatibility.
**Action:** None.

### 10.2 Don't have a catch-all subcommand
**Status:** REVIEW NEEDED. `genechat` with no subcommand currently falls through to `serve`. Per Section 2.2 above, this will be changed to show help when interactive, and serve when piped. The `serve` subcommand will remain as the explicit way to start the server.
**Action:** Addressed by Section 2.2 implementation.

### 10.3 Don't allow arbitrary abbreviations of subcommands
**Status:** COMPLIANT. argparse does not allow abbreviations of subcommand names by default (in Python 3.11+, `allow_abbrev` defaults to True for options but subcommands are exact-match).
**Action:** None.

---

## Section 11: Signals and Control Characters

### 11.1 If user hits Ctrl-C, exit immediately
**Status:** PARTIAL. No explicit signal handling. Python's default `KeyboardInterrupt` propagates, but annotation subprocesses (bcftools, snpEff) may leave orphan processes.
**Action:** APPLY. Add a `KeyboardInterrupt` handler in `main()` that:
1. Prints "\nInterrupted." to stderr
2. Exits with code 130 (standard for SIGINT)

For annotation specifically: the subprocess pipes should handle SIGINT gracefully since the parent Python process dying will send SIGPIPE to children. But adding explicit cleanup is worth considering for long-running annotation.

**Implementation:** Wrap `main()` body in `try: ... except KeyboardInterrupt: print("\nInterrupted.", file=sys.stderr); sys.exit(130)`.

**Files:** `src/genechat/cli.py`

---

## Section 12: Configuration

### 12.1 Follow the XDG spec
**Status:** COMPLIANT. Uses `platformdirs` (`user_config_dir`, `user_data_dir`) which implements XDG on Linux and platform-appropriate paths on macOS/Windows.
**Action:** None.

### 12.2 Apply configuration in order of precedence
**Status:** COMPLIANT. Precedence is: env vars (`GENECHAT_CONFIG`, `GENECHAT_VCF`, `GENECHAT_GENOME`) > config file > defaults. Flags override config where applicable.
**Action:** None.

---

## Section 13: Environment Variables

### 13.1 Environment variable naming
**Status:** COMPLIANT. All env vars use `GENECHAT_` prefix with uppercase letters and underscores.
**Action:** None.

### 13.2 Check general-purpose environment variables
**Status:** PARTIAL.
- `NO_COLOR`: NOT checked (no color support currently — will be addressed by Section 4.8)
- `TERM`: NOT checked
- `HOME`: Used indirectly via platformdirs
- `TMPDIR`: NOT explicitly used (but Python's `tempfile` module respects it)
- `HTTP_PROXY`/`HTTPS_PROXY`: NOT checked by download functions

**Action:** APPLY (as part of color implementation in 4.8). `NO_COLOR` and `TERM=dumb` will be checked. Proxy env vars should be respected by urllib (Python's urllib respects them by default via `urllib.request.getproxies()`), so no action needed there.

### 13.3 Do not read secrets from environment variables
**Status:** COMPLIANT. No secrets in env vars.
**Action:** None.

---

## Section 14: Naming

### 14.1 Simple, memorable word
**Status:** COMPLIANT. "genechat" is descriptive (gene + chat), memorable, and unique.
**Action:** None.

### 14.2 Lowercase letters only
**Status:** COMPLIANT.
**Action:** None.

### 14.3 Keep it short / easy to type
**Status:** ACCEPTABLE. "genechat" is 8 characters. Not the shortest, but reasonable for a tool used infrequently (setup/maintenance, not continuous use).
**Action:** None.

---

## Section 15: Distribution

### 15.1 Distribute as a single binary (or native package)
**Status:** COMPLIANT for the Python ecosystem. Installable via `pip install` or `uv tool install`. Not a single binary, but follows Python conventions. The language-specific tool exception applies ("it's safe to assume the user has an interpreter for that language installed").
**Action:** None.

### 15.2 Make it easy to uninstall
**Status:** COMPLIANT. `pip uninstall genechat-mcp` or `uv tool uninstall genechat-mcp`. Standard Python package uninstall.
**Action:** None.

---

## Section 16: Analytics

### 16.1 Do not phone home without consent
**Status:** COMPLIANT. No analytics, no telemetry, no network calls at runtime. This is a core design principle documented in README and CLAUDE.md.
**Action:** None.

---

## Implementation Priority

### P0 — High impact, low risk
1. **Section 2.2: Show help when run interactively with no subcommand** — Prevents the worst UX issue (silent hang). TTY detection preserves MCP compatibility.
2. **Section 11.1: KeyboardInterrupt handler** — Clean exit on Ctrl-C with exit code 130.
3. **Section 6.3: Add --version flag** — Standard convention, trivial to implement.

### P1 — Moderate impact, moderate effort
4. **Section 1.2: Named exit codes** — Better scripting support, clearer error identification.
5. **Section 2.3 + 2.4: Support path and docs links in help** — Better discoverability.
6. **Section 2.5: Examples in help text** — Most impactful help improvement.
7. **Section 5.2: Top-level exception handler** — Clean error reporting for unexpected failures.
8. **Section 4.2: --json flag on status** — Machine-readable output for the most useful subcommand.

### P2 — Nice to have, higher effort
9. **Section 4.8: Color output** — Visual improvement with NO_COLOR/TTY/TERM support.
10. **Section 9.3: Download progress** — Better UX for long downloads.
11. **Section 9.4: Network timeouts** — Prevents hangs on bad connections.
12. **Section 9.2: SnpEff startup message** — Minor responsiveness improvement.

### Deferred
- **Section 2.6: Spelling suggestions** — Would require library change or custom code. Low ROI.
- **Section 2.8: Formatted help text** — Would require `rich-argparse` or library change. Low ROI.
- **Section 3.3: Man pages** — Not standard for Python CLI tools. Low ROI.
- **Section 9.5: gnomAD checkpoint recovery** — Involves patch.db metadata schema changes; warrants separate PR.

---

## Files Changed

| File | Changes |
|------|---------|
| `src/genechat/cli.py` | Exit codes, TTY-aware no-subcommand behavior, --version, --no-color, --json on status, help examples, epilog links, exception handler, KeyboardInterrupt handler, color helper, SnpEff message, gnomAD checkpointing |
| `src/genechat/__init__.py` | Export `__version__` from package metadata |
| `src/genechat/download.py` | Download progress callbacks, network timeouts |
| `src/genechat/update.py` | Version check timeouts |
| `tests/test_cli.py` | Updated exit codes, new tests for TTY behavior, --json, --version, color, exception handler |
| `README.md` | Document exit codes |
| `CLAUDE.md` | Update CLI section with new flags |

---

## Verification

- `uv run pytest -x` passes with all new and updated tests
- `uv run ruff check . && uv run ruff format .` clean
- `genechat --help` shows description, examples, support link, docs link
- `genechat` in interactive terminal shows concise help (not server)
- `echo "" | genechat` starts server (backward compatible)
- `genechat --version` prints version
- `genechat status --json` outputs valid JSON
- `NO_COLOR=1 genechat status` produces no ANSI codes
- Ctrl-C during `genechat annotate` prints "Interrupted." and exits 130
- `genechat init /nonexistent` exits with code 4 (VCF error), not 1
