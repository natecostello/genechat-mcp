#!/usr/bin/env python3
"""Build seed data pipeline: fetch from APIs, rebuild SQLite.

Usage: uv run python scripts/build_seed_data.py

Pipeline:
1. fetch_gene_coords.py   -> data/seed/genes_grch38.tsv (HGNC + Ensembl)
2. fetch_cpic_data.py      -> data/seed/pgx_drugs.tsv, pgx_variants.tsv (CPIC API)
3. fetch_prs_data.py       -> data/seed/prs_weights.tsv (PGS Catalog FTP)
4. build_lookup_db.py      -> src/genechat/data/lookup_tables.db

Idempotent -- safe to re-run anytime. Requires internet access (build-time only).
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
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

    # Step 2: Fetch CPIC PGx data
    if not run_script("fetch_cpic_data.py"):
        print("\nPipeline failed at step 2 (CPIC PGx data)")
        return 1

    # Step 3: Fetch PRS data from PGS Catalog
    if not run_script("fetch_prs_data.py"):
        print("\nPipeline failed at step 3 (PRS data)")
        return 1

    # Step 4: Rebuild SQLite
    if not run_script("build_lookup_db.py"):
        print("\nPipeline failed at step 4 (SQLite rebuild)")
        return 1

    # Summary
    print(f"\n{'=' * 60}")
    print("Pipeline complete! Row counts:")
    print(f"{'=' * 60}")
    files = {
        "genes_grch38.tsv": "genes",
        "pgx_drugs.tsv": "pgx_drugs",
        "pgx_variants.tsv": "pgx_variants",
        "prs_weights.tsv": "prs_weights",
    }
    for filename, table_name in files.items():
        path = SEED_DIR / filename
        count = count_tsv_rows(path)
        print(f"  {table_name:20s} {count:>5d} rows  ({filename})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
