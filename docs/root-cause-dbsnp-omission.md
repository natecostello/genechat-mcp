# Root Cause Analysis: dbSNP Implementation Omission

## Incident Summary

The patch-architecture-plan.md (v4) explicitly specified dbSNP as Step 4 of the annotation pipeline, with detailed implementation specifications across download, annotation, version detection, and incremental update. When PR #21 was reported as complete and merged, the dbSNP implementation was absent — `download.py` contained a placeholder stub and `cli.py` contained a TODO stub. Meanwhile, `patch.py` had the actual stream parser ready to use.

This was discovered during PR #25 (documentation cleanup) when the user asked why `genechat download --dbsnp` said "manual download required" despite the plan specifying automated download.

## What Was Specified vs What Was Built

| Plan Item | Plan Lines | Implementation Status |
|-----------|-----------|----------------------|
| `download_dbsnp()` with NCBI FTP download + contig rename | 156-164, 272-289 | **STUB** — printed "manual download" message |
| `_annotate_dbsnp()` with bcftools pipeline | 272-289, 361-364 | **STUB** — printed TODO message |
| `dbsnp_installed()` helper | 443-444 (status output) | **MISSING** |
| `_dbsnp_version()` from `##dbSNP_BUILD_ID=` header | 994, 1019 | **MISSING** |
| dbSNP in `genechat status` references section | 443-444 | **MISSING** |
| `patch.update_dbsnp_from_stream()` | 272-289 | **DONE** (ready but uncalled) |
| `patch.clear_layer('dbsnp')` | 361-364 | **DONE** |
| `--dbsnp` CLI flags wired up | 156-164 | **DONE** (but connected to stubs) |

The `patch.py` layer was fully implemented. The gap was entirely in `download.py` (download + contig rename) and `cli.py` (annotation orchestration).

## Root Cause

**Primary cause: Stub accepted as implementation.** The `download_dbsnp()` and `_annotate_dbsnp()` functions were written as placeholder stubs with the correct signatures and print messages. They compiled, they were callable from the CLI, and the `--dbsnp` flags were properly wired up. This created the appearance of completeness — the code structure looked right, every flag had a handler, and no test failed.

**Contributing factor: Plan verification was not line-by-line.** The plan completion protocol in the project's [CLAUDE.md](../CLAUDE.md) requires reading the plan "line by line" and verifying "EACH numbered item or table row" against the actual code. This was not done rigorously. The PR #21 submission checked high-level categories (CLI works, patch.py works, parity tests pass, VCFEngine dual-mode works) but did not individually verify each annotation step's implementation against the plan's specification.

**Contributing factor: Tests didn't catch it.** The existing test suite tested the `patch.py` dbSNP methods (which worked) and the CLI `--dbsnp` flag routing (which worked — it called the stub). No test asserted that `_annotate_dbsnp` actually ran bcftools or that `download_dbsnp` actually downloaded anything. The stub functions passed all tests because they were valid Python that didn't crash.

**Contributing factor: Stub functions looked intentional.** The stubs included the comment `# TODO: implement when dbSNP download is automated` and printed user-facing messages like "This feature is not yet fully automated." This made them look like a deliberate deferral rather than a missed implementation, even though the plan specified full automation.

## Rules That Were Not Followed

1. **Plan Completion Protocol (`CLAUDE.md`):**
   > "For EACH numbered item or table row, verify implementation by reading the actual code"

   The plan's Step 4 (lines 272-289) describes specific bcftools commands and Python parsing. Reading `cli.py:_annotate_dbsnp()` would have immediately shown it was a stub. This verification step was skipped or done at too high a level.

2. **Independent Verification (`CLAUDE.md`):**
   > "Re-read the plan file (not from memory — use the Read tool)"

   The plan file was not re-read systematically before reporting complete. Had it been, lines 156-164 (download --dbsnp spec) and 272-289 (Step 4 annotation spec) would have flagged the stubs as incomplete.

3. **Never speculate about implementation status (`CLAUDE.md`):**
   > "Always read the code before making claims about what is or isn't built"

   The stub functions' existence was treated as evidence of implementation without reading what they actually did.

## Corrective Actions

### Immediate Fix (This PR)

1. Implement `download_dbsnp()` with actual NCBI FTP download, RefSeq-to-chr contig rename via bcftools, and tabix indexing.
2. Implement `_annotate_dbsnp()` with bcftools annotate -c ID pipeline piped to `patch.update_dbsnp_from_stream()`.
3. Add `dbsnp_installed()`, `dbsnp_path()`, `_dbsnp_version()` helpers.
4. Update `genechat status` to show dbSNP reference installation status.
5. Add tests for all new functions.

### Process Improvements

**Stub detection:** When reviewing code against a plan, any function body that consists only of `print()` calls and/or `# TODO` comments must be flagged as unimplemented, regardless of whether it has the correct signature, is properly wired into the CLI, or passes existing tests.

**Test coverage for plan items:** For each plan step that describes specific tool execution (subprocess calls, file operations, database writes), at least one test must verify the execution path — not just the function signature. A monkeypatched test that asserts `bcftools` was called with the right arguments is sufficient; a test that only checks the function doesn't crash is not.

## Timeline

- **PR #21 submitted and merged:** Patch architecture Phase 1 — dbSNP stubs included but not flagged
- **PR #25 opened:** Documentation cleanup — user discovered dbSNP was a stub during doc review
- **This PR:** Implements the missing dbSNP layer + root cause analysis
