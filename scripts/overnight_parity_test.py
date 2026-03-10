#!/usr/bin/env python3
"""Overnight parity test: legacy annotated VCF vs raw VCF + patch.db.

This script:
  1. Downloads gnomAD exome VCFs (~8 GB) via `genechat annotate --gnomad`
  2. Creates a temporary config pointing to the raw VCF
  3. Builds a fresh patch.db with all layers (SnpEff + ClinVar + gnomAD)
     via `genechat annotate --all`
  4. Compares query results between legacy mode and patch mode
  5. Writes a detailed report to giab/parity_report.txt

CLI commands executed (for reference):
  genechat annotate --gnomad
  genechat annotate --all  (with config pointing to raw VCF)

Usage:
  uv run python scripts/overnight_parity_test.py
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
GIAB_DIR = REPO_ROOT / "giab"
WORK_DIR = GIAB_DIR / "work"
RAW_VCF = WORK_DIR / "HG001_raw.vcf.gz"
LEGACY_VCF = GIAB_DIR / "HG001_annotated.vcf.gz"
PATCH_DB = WORK_DIR / "HG001_raw.patch.db"
REPORT_PATH = GIAB_DIR / "parity_report.txt"
TEMP_CONFIG = WORK_DIR / "test_config.toml"
LOOKUP_DB = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"

# Ground truth from e2e conftest — known NA12878 genotypes
GROUND_TRUTH = {
    "rs9923231": {
        "gene": "VKORC1",
        "chrom": "chr16",
        "pos": 31096368,
        "expected_zygosity": "heterozygous",
    },
    "rs1801133": {
        "gene": "MTHFR",
        "chrom": "chr1",
        "pos": 11796321,
        "expected_zygosity": "heterozygous",
    },
    "rs4988235": {
        "gene": "MCM6",
        "chrom": "chr2",
        "pos": 135851076,
        "expected_zygosity": "homozygous_alt",
    },
    "rs4244285": {
        "gene": "CYP2C19",
        "chrom": "chr10",
        "pos": 94781859,
        "expected_zygosity": "heterozygous",
    },
    "rs4149056": {
        "gene": "SLCO1B1",
        "chrom": "chr12",
        "pos": 21178615,
        "expected_zygosity": "heterozygous",
    },
}

# Variants expected absent (homozygous ref)
GROUND_TRUTH_ABSENT = {
    "rs6025": {"gene": "F5", "chrom": "chr1", "pos": 169549811},
    "rs429358": {"gene": "APOE", "chrom": "chr19", "pos": 44908684},
    "rs7412": {"gene": "APOE", "chrom": "chr19", "pos": 44908822},
}

# Gene regions to test
GENE_REGIONS = {
    "SLCO1B1": "chr12:21130000-21240000",
    "CYP2C19": "chr10:94750000-94860000",
    "VKORC1": "chr16:31090000-31110000",
    "MTHFR": "chr1:11785000-11810000",
    "BRCA1": "chr17:43044295-43170245",
}


class Logger:
    """Write to both stdout and a log file."""

    def __init__(self, path: Path):
        self.file = open(path, "w")
        self.start = time.time()

    def log(self, msg: str = ""):
        elapsed = time.time() - self.start
        ts = f"[{elapsed:8.1f}s]"
        line = f"{ts} {msg}"
        print(line, flush=True)
        self.file.write(line + "\n")
        self.file.flush()

    def close(self):
        self.file.close()


def run_cmd(
    cmd: list[str], log: Logger, env: dict | None = None
) -> subprocess.CompletedProcess:
    """Run a command, log it, and return the result."""
    cmd_str = " ".join(cmd)
    log.log(f"$ {cmd_str}")
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd, capture_output=True, text=True, env=merged_env, cwd=str(REPO_ROOT)
    )
    if result.stdout:
        for line in result.stdout.strip().split("\n")[:50]:
            log.log(f"  {line}")
        if result.stdout.count("\n") > 50:
            log.log(f"  ... ({result.stdout.count(chr(10))} lines total)")
    if result.returncode != 0:
        log.log(f"  EXIT CODE: {result.returncode}")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:20]:
                log.log(f"  STDERR: {line}")
    return result


def write_temp_config(log: Logger):
    """Write a temporary config pointing to the raw VCF."""
    config_content = f"""[genome]
vcf_path = "{RAW_VCF}"
"""
    TEMP_CONFIG.write_text(config_content)
    log.log(f"Wrote temp config: {TEMP_CONFIG}")
    log.log(f"  vcf_path = {RAW_VCF}")


def step1_download_gnomad(log: Logger) -> bool:
    """Step 1: Download gnomAD exome VCFs."""
    log.log("=" * 70)
    log.log("STEP 1: Download gnomAD exome VCFs (~8 GB)")
    log.log("=" * 70)
    log.log()
    log.log("CLI command: uv run genechat annotate --gnomad")
    log.log()

    result = run_cmd(
        ["uv", "run", "genechat", "annotate", "--gnomad"],
        log,
    )
    if result.returncode != 0:
        log.log("FAILED: gnomAD download failed")
        return False
    log.log("gnomAD download complete.")
    return True


def step2_build_patch_db(log: Logger) -> bool:
    """Step 2: Build fresh patch.db from raw VCF with all layers."""
    log.log()
    log.log("=" * 70)
    log.log("STEP 2: Build patch.db (SnpEff + ClinVar + gnomAD)")
    log.log("=" * 70)
    log.log()

    # Remove existing patch.db if present
    if PATCH_DB.exists():
        log.log(f"Removing existing patch.db: {PATCH_DB}")
        PATCH_DB.unlink()

    write_temp_config(log)
    log.log()
    log.log(
        f"CLI command: GENECHAT_CONFIG={TEMP_CONFIG} uv run genechat annotate --all"
    )
    log.log()

    result = run_cmd(
        ["uv", "run", "genechat", "annotate", "--all"],
        log,
        env={"GENECHAT_CONFIG": str(TEMP_CONFIG)},
    )
    if result.returncode != 0:
        log.log("FAILED: patch.db build failed")
        return False

    if PATCH_DB.exists():
        size_mb = PATCH_DB.stat().st_size / 1024 / 1024
        log.log(f"patch.db built: {PATCH_DB} ({size_mb:.0f} MB)")
    else:
        log.log(f"ERROR: patch.db not found at expected path: {PATCH_DB}")
        return False

    return True


def step3_compare(log: Logger) -> dict:
    """Step 3: Compare legacy vs patch mode across comprehensive queries."""
    log.log()
    log.log("=" * 70)
    log.log("STEP 3: Parity comparison (legacy vs patch)")
    log.log("=" * 70)
    log.log()

    # Import after ensuring we're in the right env
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from genechat.config import AppConfig
    from genechat.vcf_engine import VCFEngine

    # Create both engines
    legacy_config = AppConfig(
        genome={"vcf_path": str(LEGACY_VCF), "genome_build": "GRCh38"},
        databases={"lookup_db": str(LOOKUP_DB)},
        server={"max_variants_per_response": 10000},
    )
    patch_config = AppConfig(
        genome={
            "vcf_path": str(RAW_VCF),
            "genome_build": "GRCh38",
            "patch_db": str(PATCH_DB),
        },
        databases={"lookup_db": str(LOOKUP_DB)},
        server={"max_variants_per_response": 10000},
    )

    legacy = VCFEngine(legacy_config)
    patch = VCFEngine(patch_config)

    log.log(f"Legacy engine: {LEGACY_VCF}")
    log.log(f"  Patch mode: {legacy._use_patch}")
    log.log(f"Patch engine: {RAW_VCF} + {PATCH_DB}")
    log.log(f"  Patch mode: {patch._use_patch}")
    log.log()

    results = {
        "ground_truth_rsids": {},
        "absent_rsids": {},
        "gene_regions": {},
        "clinvar": {},
        "stats": {},
        "gnomad_freq": {},
        "summary": {"pass": 0, "fail": 0, "warn": 0},
    }

    # --- Test 1: Ground truth rsIDs ---
    log.log("-" * 50)
    log.log("Test 1: Ground truth rsID lookups")
    log.log("-" * 50)

    for rsid, info in GROUND_TRUTH.items():
        log.log(f"  {rsid} ({info['gene']}):")
        lv = legacy.query_rsid(rsid)
        pv = patch.query_rsid(rsid)

        result = {"legacy_count": len(lv), "patch_count": len(pv)}

        if len(lv) != len(pv):
            result["status"] = "FAIL"
            result["detail"] = f"Count mismatch: legacy={len(lv)}, patch={len(pv)}"
            log.log(f"    FAIL: count mismatch legacy={len(lv)} patch={len(pv)}")
            results["summary"]["fail"] += 1
        elif len(lv) == 0:
            result["status"] = "FAIL"
            result["detail"] = "Both returned empty (expected variant)"
            log.log("    FAIL: both returned empty")
            results["summary"]["fail"] += 1
        else:
            lv0, pv0 = lv[0], pv[0]
            mismatches = compare_variant_detail(lv0, pv0)
            if mismatches:
                result["status"] = (
                    "WARN" if all("freq" in m.lower() for m in mismatches) else "FAIL"
                )
                result["detail"] = "; ".join(mismatches)
                log.log(f"    {result['status']}: {result['detail']}")
                results["summary"][
                    "warn" if result["status"] == "WARN" else "fail"
                ] += 1
            else:
                result["status"] = "PASS"
                log.log(
                    f"    PASS: genotype={lv0['genotype']['display']}, "
                    f"zygosity={lv0['genotype']['zygosity']}"
                )
                results["summary"]["pass"] += 1

            # Check zygosity matches ground truth
            if lv0["genotype"]["zygosity"] != info["expected_zygosity"]:
                log.log(
                    f"    NOTE: zygosity={lv0['genotype']['zygosity']}, "
                    f"expected={info['expected_zygosity']}"
                )

            # Log gnomAD frequencies
            lf = lv0.get("population_freq", {})
            pf = pv0.get("population_freq", {})
            if lf or pf:
                log.log(f"    AF: legacy={lf}, patch={pf}")

        results["ground_truth_rsids"][rsid] = result
    log.log()

    # --- Test 2: Absent rsIDs ---
    log.log("-" * 50)
    log.log("Test 2: Absent rsID lookups (expected hom ref)")
    log.log("-" * 50)

    for rsid, info in GROUND_TRUTH_ABSENT.items():
        log.log(f"  {rsid} ({info['gene']}):")
        lv = legacy.query_rsid(rsid)
        pv = patch.query_rsid(rsid)

        if len(lv) == 0 and len(pv) == 0:
            result = {"status": "PASS", "detail": "Both empty (correctly absent)"}
            log.log("    PASS: correctly absent")
            results["summary"]["pass"] += 1
        else:
            result = {"status": "FAIL", "detail": f"legacy={len(lv)}, patch={len(pv)}"}
            log.log(f"    FAIL: not absent legacy={len(lv)} patch={len(pv)}")
            results["summary"]["fail"] += 1

        results["absent_rsids"][rsid] = result
    log.log()

    # --- Test 3: Gene region queries ---
    log.log("-" * 50)
    log.log("Test 3: Gene region queries")
    log.log("-" * 50)

    for gene, region in GENE_REGIONS.items():
        log.log(f"  {gene} ({region}):")
        lv = legacy.query_region(region)
        pv = patch.query_region(region)

        result = {"legacy_count": len(lv), "patch_count": len(pv)}

        if len(lv) != len(pv):
            result["status"] = "WARN"
            result["detail"] = f"Count mismatch: legacy={len(lv)}, patch={len(pv)}"
            log.log(f"    WARN: count mismatch legacy={len(lv)} patch={len(pv)}")
            results["summary"]["warn"] += 1

            # Show which variants differ
            legacy_positions = {(v["chrom"], v["pos"], v["ref"], v["alt"]) for v in lv}
            patch_positions = {(v["chrom"], v["pos"], v["ref"], v["alt"]) for v in pv}
            only_legacy = legacy_positions - patch_positions
            only_patch = patch_positions - legacy_positions
            if only_legacy:
                log.log(f"    Only in legacy ({len(only_legacy)}):")
                for p in sorted(only_legacy)[:5]:
                    log.log(f"      {p[0]}:{p[1]} {p[2]}>{p[3]}")
            if only_patch:
                log.log(f"    Only in patch ({len(only_patch)}):")
                for p in sorted(only_patch)[:5]:
                    log.log(f"      {p[0]}:{p[1]} {p[2]}>{p[3]}")
        else:
            # Compare variants positionally
            field_mismatches = 0
            for i, (lvar, pvar) in enumerate(zip(lv, pv)):
                mismatches = compare_variant_detail(lvar, pvar)
                if mismatches:
                    field_mismatches += 1
                    if field_mismatches <= 3:
                        log.log(
                            f"    Mismatch at {lvar['chrom']}:{lvar['pos']}: "
                            f"{'; '.join(mismatches)}"
                        )

            if field_mismatches == 0:
                result["status"] = "PASS"
                log.log(f"    PASS: {len(lv)} variants match")
                results["summary"]["pass"] += 1
            else:
                result["status"] = "WARN"
                result["detail"] = (
                    f"{field_mismatches}/{len(lv)} variants with field differences"
                )
                log.log(
                    f"    WARN: {field_mismatches}/{len(lv)} variants with differences"
                )
                results["summary"]["warn"] += 1

        results["gene_regions"][gene] = result
    log.log()

    # --- Test 4: ClinVar queries ---
    log.log("-" * 50)
    log.log("Test 4: ClinVar significance queries")
    log.log("-" * 50)

    for sig in ["Pathogenic", "Likely_pathogenic", "drug_response", "risk_factor"]:
        log.log(f"  Significance: {sig}")
        t0 = time.time()
        lv = legacy.query_clinvar(sig)
        t1 = time.time()
        pv = patch.query_clinvar(sig)
        t2 = time.time()

        result = {
            "legacy_count": len(lv),
            "patch_count": len(pv),
            "legacy_time": f"{t1 - t0:.1f}s",
            "patch_time": f"{t2 - t1:.1f}s",
        }

        if len(lv) == len(pv):
            # Spot-check first few
            mismatches = 0
            for lvar, pvar in zip(lv[:20], pv[:20]):
                if compare_variant_detail(lvar, pvar):
                    mismatches += 1

            if mismatches == 0:
                result["status"] = "PASS"
                log.log(
                    f"    PASS: {len(lv)} variants (legacy: {t1 - t0:.1f}s, patch: {t2 - t1:.1f}s)"
                )
                results["summary"]["pass"] += 1
            else:
                result["status"] = "WARN"
                result["detail"] = f"{mismatches} field mismatches in first 20"
                log.log(
                    f"    WARN: {mismatches} mismatches in first 20 "
                    f"(legacy: {t1 - t0:.1f}s, patch: {t2 - t1:.1f}s)"
                )
                results["summary"]["warn"] += 1
        else:
            result["status"] = "WARN"
            result["detail"] = f"Count: legacy={len(lv)}, patch={len(pv)}"
            log.log(
                f"    WARN: count legacy={len(lv)} patch={len(pv)} "
                f"(legacy: {t1 - t0:.1f}s, patch: {t2 - t1:.1f}s)"
            )
            results["summary"]["warn"] += 1

        results["clinvar"][sig] = result
    log.log()

    # --- Test 5: Stats ---
    log.log("-" * 50)
    log.log("Test 5: Variant statistics")
    log.log("-" * 50)

    t0 = time.time()
    ls = legacy.stats()
    t1 = time.time()
    ps = patch.stats()
    t2 = time.time()

    log.log(f"  Legacy stats ({t1 - t0:.1f}s): {json.dumps(ls)}")
    log.log(f"  Patch stats  ({t2 - t1:.1f}s): {json.dumps(ps)}")

    stats_match = True
    for key in ls:
        if ls[key] != ps[key]:
            log.log(f"  MISMATCH: {key}: legacy={ls[key]}, patch={ps[key]}")
            stats_match = False

    results["stats"] = {
        "legacy": ls,
        "patch": ps,
        "status": "PASS" if stats_match else "FAIL",
    }
    if stats_match:
        log.log("  PASS: all stats match")
        results["summary"]["pass"] += 1
    else:
        results["summary"]["fail"] += 1
    log.log()

    # --- Test 6: gnomAD frequency comparison ---
    log.log("-" * 50)
    log.log("Test 6: gnomAD allele frequency comparison")
    log.log("-" * 50)

    # Check known pharmacogenomic variants for frequency data
    freq_rsids = ["rs4149056", "rs4244285", "rs9923231", "rs1801133", "rs4988235"]
    freq_pass = 0
    freq_warn = 0

    for rsid in freq_rsids:
        lv = legacy.query_rsid(rsid)
        pv = patch.query_rsid(rsid)

        if not lv or not pv:
            log.log(f"  {rsid}: skipped (empty result)")
            continue

        lf = lv[0].get("population_freq", {})
        pf = pv[0].get("population_freq", {})
        log.log(f"  {rsid}:")
        log.log(f"    Legacy AF: {lf}")
        log.log(f"    Patch  AF: {pf}")

        # Check if both have AF or neither has AF
        if bool(lf) == bool(pf):
            if lf and pf:
                # Both have data — compare values
                af_match = True
                for key in set(list(lf.keys()) + list(pf.keys())):
                    lval = lf.get(key)
                    pval = pf.get(key)
                    if lval is not None and pval is not None:
                        if abs(lval - pval) > 0.01:
                            log.log(
                                f"    WARN: {key} differs: legacy={lval:.4f} patch={pval:.4f}"
                            )
                            af_match = False
                    elif lval != pval:
                        log.log(
                            f"    WARN: {key} present in one but not other: "
                            f"legacy={lval} patch={pval}"
                        )
                        af_match = False
                if af_match:
                    log.log("    PASS")
                    freq_pass += 1
                else:
                    freq_warn += 1
            else:
                log.log("    PASS (both empty)")
                freq_pass += 1
        else:
            log.log("    WARN: frequency availability differs")
            freq_warn += 1

    results["gnomad_freq"] = {
        "pass": freq_pass,
        "warn": freq_warn,
        "status": "PASS" if freq_warn == 0 else "WARN",
    }
    if freq_warn == 0:
        results["summary"]["pass"] += 1
    else:
        results["summary"]["warn"] += 1
    log.log()

    # --- Test 7: Batch rsID query ---
    log.log("-" * 50)
    log.log("Test 7: Batch rsID query (query_rsids)")
    log.log("-" * 50)

    batch_rsids = list(GROUND_TRUTH.keys())
    t0 = time.time()
    lr = legacy.query_rsids(batch_rsids)
    t1 = time.time()
    pr = patch.query_rsids(batch_rsids)
    t2 = time.time()

    log.log(f"  Legacy: {t1 - t0:.2f}s, Patch: {t2 - t1:.2f}s")
    batch_match = True
    for rsid in batch_rsids:
        lcount = len(lr.get(rsid, []))
        pcount = len(pr.get(rsid, []))
        if lcount != pcount:
            log.log(f"  MISMATCH: {rsid}: legacy={lcount}, patch={pcount}")
            batch_match = False
        elif lcount > 0:
            mismatches = compare_variant_detail(lr[rsid][0], pr[rsid][0])
            if mismatches:
                log.log(f"  WARN: {rsid}: {'; '.join(mismatches)}")
                batch_match = False

    if batch_match:
        log.log("  PASS: batch rsID results match")
        results["summary"]["pass"] += 1
    else:
        log.log("  WARN: some batch rsID differences")
        results["summary"]["warn"] += 1
    log.log()

    # --- Test 8: Annotation versions ---
    log.log("-" * 50)
    log.log("Test 8: Annotation version metadata")
    log.log("-" * 50)

    lversions = legacy.annotation_versions()
    pversions = patch.annotation_versions()
    log.log(f"  Legacy versions: {json.dumps(lversions)}")
    log.log(f"  Patch versions:  {json.dumps(pversions)}")

    # Patch should report SnpEff, ClinVar, gnomAD
    for expected in ["SnpEff", "ClinVar", "gnomAD"]:
        if expected in pversions:
            log.log(f"  PASS: {expected} version present: {pversions[expected]}")
            results["summary"]["pass"] += 1
        else:
            log.log(f"  FAIL: {expected} version missing from patch metadata")
            results["summary"]["fail"] += 1
    log.log()

    # Clean up
    legacy.close()
    patch.close()

    return results


def compare_variant_detail(lv: dict, pv: dict) -> list[str]:
    """Compare two variant dicts and return a list of mismatch descriptions."""
    mismatches = []

    # Core fields
    for key in ("chrom", "pos", "ref", "alt"):
        if lv.get(key) != pv.get(key):
            mismatches.append(f"{key}: {lv.get(key)} vs {pv.get(key)}")

    # rsID
    if lv.get("rsid") != pv.get("rsid"):
        mismatches.append(f"rsid: {lv.get('rsid')} vs {pv.get('rsid')}")

    # Genotype
    if lv.get("genotype") != pv.get("genotype"):
        mismatches.append(
            f"genotype: {lv.get('genotype', {}).get('display')} vs "
            f"{pv.get('genotype', {}).get('display')}"
        )

    # Annotation — compare key fields
    la = lv.get("annotation", {})
    pa = pv.get("annotation", {})
    for field in ("gene", "effect", "impact"):
        if la.get(field) != pa.get(field):
            mismatches.append(f"annotation.{field}: {la.get(field)} vs {pa.get(field)}")

    # ClinVar
    lc = lv.get("clinvar", {})
    pc = pv.get("clinvar", {})
    if lc.get("significance") != pc.get("significance"):
        mismatches.append(
            f"clinvar.significance: {lc.get('significance')} vs {pc.get('significance')}"
        )

    # Population frequency (softer comparison)
    lf = lv.get("population_freq", {})
    pf = pv.get("population_freq", {})
    for key in set(list(lf.keys()) + list(pf.keys())):
        lval = lf.get(key)
        pval = pf.get(key)
        if lval is not None and pval is not None:
            if abs(lval - pval) > 0.001:
                mismatches.append(f"freq.{key}: {lval:.4f} vs {pval:.4f}")
        elif lval is not None or pval is not None:
            mismatches.append(f"freq.{key}: {lval} vs {pval}")

    return mismatches


def main():
    """Run the full overnight parity test."""
    start_time = datetime.now(timezone.utc)
    # Ensure output directories exist before opening the report file.
    GIAB_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    log = Logger(REPORT_PATH)

    log.log("=" * 70)
    log.log("GeneChat Overnight Parity Test")
    log.log(f"Started: {start_time.isoformat()}")
    log.log("=" * 70)
    log.log()
    log.log("Purpose: Compare legacy annotated VCF vs raw VCF + patch.db")
    log.log(f"  Legacy VCF:  {LEGACY_VCF}")
    log.log(f"  Raw VCF:     {RAW_VCF}")
    log.log(f"  Patch DB:    {PATCH_DB}")
    log.log(f"  Lookup DB:   {LOOKUP_DB}")
    log.log()

    # Validate prerequisites
    if not RAW_VCF.exists():
        log.log(f"ERROR: Raw VCF not found: {RAW_VCF}")
        log.log("Run: uv run python scripts/setup_giab.py ./giab")
        log.close()
        sys.exit(1)
    if not LEGACY_VCF.exists():
        log.log(f"ERROR: Legacy VCF not found: {LEGACY_VCF}")
        log.close()
        sys.exit(1)
    if not LOOKUP_DB.exists():
        log.log(f"ERROR: Lookup DB not found: {LOOKUP_DB}")
        log.close()
        sys.exit(1)

    # Step 1: Download gnomAD
    if not step1_download_gnomad(log):
        log.log("ABORT: gnomAD download failed. Cannot continue.")
        log.close()
        sys.exit(1)

    # Step 2: Build patch.db
    if not step2_build_patch_db(log):
        log.log("ABORT: patch.db build failed. Cannot continue.")
        log.close()
        sys.exit(1)

    # Step 3: Compare
    results = step3_compare(log)

    # Final summary
    end_time = datetime.now(timezone.utc)
    duration = end_time - start_time
    log.log()
    log.log("=" * 70)
    log.log("FINAL SUMMARY")
    log.log("=" * 70)
    log.log(f"  Duration: {duration}")
    log.log(f"  PASS: {results['summary']['pass']}")
    log.log(f"  WARN: {results['summary']['warn']}")
    log.log(f"  FAIL: {results['summary']['fail']}")
    log.log()

    # Write JSON results
    json_path = GIAB_DIR / "parity_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    log.log(f"JSON results: {json_path}")
    log.log(f"Full report:  {REPORT_PATH}")
    log.log()

    # CLI commands summary
    log.log("=" * 70)
    log.log("CLI COMMANDS EXECUTED")
    log.log("=" * 70)
    log.log()
    log.log("# 1. Download gnomAD exome VCFs (~8 GB, 24 per-chromosome files)")
    log.log("uv run genechat annotate --gnomad")
    log.log()
    log.log("# 2. Write a temporary config pointing to the raw (unannotated) VCF")
    log.log(f"cat > {TEMP_CONFIG} << 'EOF'")
    log.log("[genome]")
    log.log(f'vcf_path = "{RAW_VCF}"')
    log.log("EOF")
    log.log()
    log.log(
        "# 3. Build patch.db with all annotation layers (SnpEff + ClinVar + gnomAD)"
    )
    log.log(f"GENECHAT_CONFIG={TEMP_CONFIG} uv run genechat annotate --all")
    log.log()
    log.log("# 4. Comparison was done programmatically (see results above)")
    log.log(
        "# Both VCFEngine instances were created with max_variants_per_response=10000"
    )
    log.log(f"# Legacy config: vcf_path={LEGACY_VCF}")
    log.log(f"# Patch config:  vcf_path={RAW_VCF}, patch_db={PATCH_DB}")
    log.log()

    log.close()

    # Print final status
    total = (
        results["summary"]["pass"]
        + results["summary"]["warn"]
        + results["summary"]["fail"]
    )
    if results["summary"]["fail"] == 0:
        print(f"\nAll {total} tests passed ({results['summary']['warn']} warnings).")
    else:
        print(f"\n{results['summary']['fail']} FAILURES out of {total} tests.")
        sys.exit(1)


if __name__ == "__main__":
    main()
