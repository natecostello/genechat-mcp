#!/usr/bin/env python3
"""Build seed data pipeline: fetch coordinates from Ensembl, merge with curated metadata, rebuild SQLite.

Usage: uv run python scripts/build_seed_data.py

Pipeline:
1. fetch_gene_coords.py   → data/seed/genes_grch38.tsv
2. fetch_variant_coords.py → data/seed/trait_variants.tsv, data/seed/pgx_variants.tsv
3. fetch_prs_coords.py    → data/seed/prs_weights.tsv
4. Copy carrier_metadata   → data/seed/carrier_genes.tsv
5. pgx_drugs.tsv unchanged (fully curated)
6. build_lookup_db.py      → src/genechat/data/lookup_tables.db

Idempotent — safe to re-run anytime.
"""

import csv
import io
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
CURATED_DIR = REPO_ROOT / "data" / "seed" / "curated"
SEED_DIR = REPO_ROOT / "data" / "seed"


def run_script(name: str) -> bool:
    """Run a Python script and return True on success."""
    script = SCRIPTS_DIR / name
    print(f"\n{'=' * 60}")
    print(f"Running {name}...")
    print(f"{'=' * 60}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"ERROR: {name} failed with exit code {result.returncode}")
        return False
    return True


def copy_carrier_metadata():
    """Copy carrier_metadata.tsv to carrier_genes.tsv (same format, no coordinates needed)."""
    src = CURATED_DIR / "carrier_metadata.tsv"
    dst = SEED_DIR / "carrier_genes.tsv"

    if not src.exists():
        print(f"ERROR: {src} not found")
        return False

    # Load and write without comment lines (build_lookup_db handles comments, but keep it clean)
    with open(src, encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    rows = list(reader)

    fieldnames = [
        "gene",
        "condition_name",
        "inheritance",
        "carrier_frequency",
        "acmg_recommended",
    ]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})

    print(f"Copied {len(rows)} carrier genes: {src.name} -> {dst.name}")
    return True


def count_tsv_rows(path: Path) -> int:
    """Count non-comment, non-header data rows in a TSV file."""
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        lines = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]
    return max(0, len(lines) - 1)  # subtract header


def main():
    print("GeneChat Seed Data Build Pipeline")
    print("=" * 60)

    # Step 1: Fetch gene coordinates
    if not run_script("fetch_gene_coords.py"):
        print("\nPipeline failed at step 1 (gene coordinates)")
        return 1

    # Step 2: Fetch variant coordinates (trait + pgx)
    if not run_script("fetch_variant_coords.py"):
        print("\nPipeline failed at step 2 (variant coordinates)")
        return 1

    # Step 3: Fetch PRS coordinates
    if not run_script("fetch_prs_coords.py"):
        print("\nPipeline failed at step 3 (PRS coordinates)")
        return 1

    # Step 4: Copy carrier metadata
    print(f"\n{'=' * 60}")
    print("Copying carrier metadata...")
    print(f"{'=' * 60}")
    if not copy_carrier_metadata():
        print("\nPipeline failed at step 4 (carrier metadata)")
        return 1

    # Step 5: pgx_drugs.tsv is fully curated, no changes needed
    pgx_drugs = SEED_DIR / "pgx_drugs.tsv"
    if pgx_drugs.exists():
        print(
            f"\npgx_drugs.tsv: {count_tsv_rows(pgx_drugs)} rows (unchanged, fully curated)"
        )
    else:
        print(f"\nWARNING: {pgx_drugs} not found")

    # Step 6: Rebuild SQLite
    if not run_script("build_lookup_db.py"):
        print("\nPipeline failed at step 6 (SQLite rebuild)")
        return 1

    # Summary
    print(f"\n{'=' * 60}")
    print("Pipeline complete! Row counts:")
    print(f"{'=' * 60}")
    files = {
        "genes_grch38.tsv": "genes",
        "pgx_drugs.tsv": "pgx_drugs",
        "pgx_variants.tsv": "pgx_variants",
        "trait_variants.tsv": "trait_variants",
        "carrier_genes.tsv": "carrier_genes",
        "prs_weights.tsv": "prs_weights",
    }
    for filename, table_name in files.items():
        path = SEED_DIR / filename
        count = count_tsv_rows(path)
        print(f"  {table_name:20s} {count:>5d} rows  ({filename})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
