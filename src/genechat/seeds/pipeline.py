"""Seed data pipeline: fetch from APIs, rebuild SQLite.

Works from both source checkouts and pip installs:
- Source checkout: TSVs in data/seed/, DB in src/genechat/data/
- Pip install: TSVs in a temp directory, DB at the package data path
"""

import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path

from genechat.seeds.build_db import build_db


def _find_project_root() -> Path | None:
    """Walk up from this file to find pyproject.toml (source checkout)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return None


def _default_db_path() -> Path:
    """Resolve the package lookup_tables.db path."""
    ref = resources.files("genechat") / "data" / "lookup_tables.db"
    with resources.as_file(ref) as p:
        return Path(p)


def _count_tsv_rows(path: Path) -> int:
    """Count non-comment, non-header data rows in a TSV file."""
    if not path.exists():
        return 0
    with open(path, encoding="utf-8") as f:
        lines = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]
    return max(0, len(lines) - 1)


def run_pipeline() -> int:
    """Run the full seed data pipeline. Returns 0 on success, 1 on failure.

    In a source checkout, uses scripts/ and writes TSVs to data/seed/.
    In a pip install, uses the packaged fetch modules via subprocess.
    """
    project_root = _find_project_root()

    if project_root:
        # Source checkout: write TSVs to data/seed/, DB to src/genechat/data/
        seed_dir = project_root / "data" / "seed"
        db_path = project_root / "src" / "genechat" / "data" / "lookup_tables.db"
        seed_dir.mkdir(parents=True, exist_ok=True)

        print("GeneChat Seed Data Build Pipeline (source checkout)")
        print("=" * 60)

        # Use the same genechat.seeds modules as pip-install mode
        for module_name, step_desc in [
            ("genechat.seeds.fetch_gene_coords", "gene coordinates"),
            ("genechat.seeds.fetch_cpic_data", "CPIC PGx data"),
            ("genechat.seeds.fetch_prs_data", "PRS data"),
        ]:
            print(f"\n{'=' * 60}")
            print(f"Running {module_name}...")
            print(f"{'=' * 60}")
            result = subprocess.run(
                [sys.executable, "-m", module_name, str(seed_dir)],
            )
            if result.returncode != 0:
                print(f"\nPipeline failed at {step_desc}")
                return 1
    else:
        # Pip install: use packaged modules, write TSVs to temp dir
        db_path = _default_db_path()

        print("GeneChat Seed Data Build Pipeline (pip install)")
        print("=" * 60)

        with tempfile.TemporaryDirectory(prefix="genechat-seeds-") as tmpdir:
            seed_dir = Path(tmpdir)

            # Run each fetch module via python -m
            for module_name, step_desc in [
                ("genechat.seeds.fetch_gene_coords", "gene coordinates"),
                ("genechat.seeds.fetch_cpic_data", "CPIC PGx data"),
                ("genechat.seeds.fetch_prs_data", "PRS data"),
            ]:
                print(f"\n{'=' * 60}")
                print(f"Running {module_name}...")
                print(f"{'=' * 60}")
                result = subprocess.run(
                    [sys.executable, "-m", module_name, str(seed_dir)],
                )
                if result.returncode != 0:
                    print(f"\nPipeline failed at {step_desc}")
                    return 1

            # Build DB from the temp seed dir
            print(f"\n{'=' * 60}")
            print("Building lookup_tables.db...")
            print(f"{'=' * 60}")
            build_db(seed_dir=seed_dir, db_path=db_path)

            _print_summary(seed_dir)
            return 0

    # Source checkout: build DB from data/seed/
    print(f"\n{'=' * 60}")
    print("Building lookup_tables.db...")
    print(f"{'=' * 60}")
    build_db(seed_dir=seed_dir, db_path=db_path)

    _print_summary(seed_dir)
    return 0


def _print_summary(seed_dir: Path):
    """Print row counts for each seed TSV."""
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
        path = seed_dir / filename
        count = _count_tsv_rows(path)
        print(f"  {table_name:20s} {count:>5d} rows  ({filename})")
