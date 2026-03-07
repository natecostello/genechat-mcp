#!/usr/bin/env python3
"""Build the GeneChat SQLite lookup database from seed TSV files.

Reads data/seed/*.tsv and writes src/genechat/data/lookup_tables.db.
Idempotent: drops and recreates tables on each run.
"""

import csv
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "seed"
DB_PATH = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"

SCHEMAS = {
    "genes": """
        CREATE TABLE genes (
            symbol TEXT PRIMARY KEY,
            name TEXT,
            chrom TEXT NOT NULL,
            start INTEGER NOT NULL,
            end INTEGER NOT NULL,
            strand TEXT
        );
        CREATE INDEX idx_genes_chrom ON genes(chrom, start, end);
    """,
    "pgx_drugs": """
        CREATE TABLE pgx_drugs (
            drug_name TEXT NOT NULL,
            gene TEXT NOT NULL,
            guideline_source TEXT,
            guideline_url TEXT,
            clinical_summary TEXT,
            cpic_level TEXT,
            pgx_testing TEXT
        );
        CREATE INDEX idx_pgx_drug ON pgx_drugs(drug_name);
    """,
    "pgx_variants": """
        CREATE TABLE pgx_variants (
            gene TEXT NOT NULL,
            rsid TEXT,
            chrom TEXT NOT NULL,
            pos INTEGER NOT NULL,
            ref TEXT NOT NULL,
            alt TEXT NOT NULL,
            star_allele TEXT,
            function_impact TEXT,
            notes TEXT
        );
        CREATE INDEX idx_pgx_var_gene ON pgx_variants(gene);
    """,
    "prs_weights": """
        CREATE TABLE prs_weights (
            prs_id TEXT NOT NULL,
            trait TEXT NOT NULL,
            rsid TEXT NOT NULL,
            chrom TEXT NOT NULL,
            pos INTEGER NOT NULL,
            effect_allele TEXT NOT NULL,
            weight REAL NOT NULL
        );
        CREATE INDEX idx_prs_id ON prs_weights(prs_id);
    """,
}

# Map table name -> TSV filename
TSV_FILES = {
    "genes": "genes_grch38.tsv",
    "pgx_drugs": "pgx_drugs.tsv",
    "pgx_variants": "pgx_variants.tsv",
    "prs_weights": "prs_weights.tsv",
}

# Columns that should be stored as INTEGER
INT_COLUMNS = {"start", "end", "pos"}
# Columns that should be stored as REAL
FLOAT_COLUMNS = {"weight"}


def load_tsv(path: Path) -> list[dict]:
    """Read a TSV file and return list of row dicts. Skips comment lines (#)."""
    with open(path, newline="", encoding="utf-8") as f:
        # Skip comment lines before the header
        lines = [line for line in f if not line.startswith("#")]
    import io

    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    rows = []
    for row in reader:
        # Replace '.' with None for missing values
        cleaned = {}
        for k, v in row.items():
            if v == "." or v == "":
                cleaned[k] = None
            elif k in INT_COLUMNS and v is not None:
                cleaned[k] = int(v)
            elif k in FLOAT_COLUMNS and v is not None:
                cleaned[k] = float(v)
            else:
                cleaned[k] = v
        rows.append(cleaned)
    return rows


def build_db(seed_dir: Path | None = None, db_path: Path | None = None):
    """Build the SQLite database from seed TSVs.

    Args:
        seed_dir: Directory containing seed TSV files. Defaults to data/seed/.
        db_path: Output database path. Defaults to src/genechat/data/lookup_tables.db.
    """
    seed_dir = seed_dir or SEED_DIR
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for table_name, schema_sql in SCHEMAS.items():
        tsv_file = seed_dir / TSV_FILES[table_name]
        if not tsv_file.exists():
            print(f"WARNING: {tsv_file} not found, skipping {table_name}")
            continue

        # Drop existing table
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")

        # Create table and indexes
        cursor.executescript(schema_sql)

        # Load data
        rows = load_tsv(tsv_file)
        if not rows:
            print(f"WARNING: {tsv_file} has no data rows")
            continue

        columns = list(rows[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

        for row in rows:
            cursor.execute(insert_sql, [row[c] for c in columns])

        conn.commit()
        print(f"  {table_name}: {len(rows)} rows loaded from {tsv_file.name}")

    conn.close()
    print(f"\nDatabase written to: {db_path}")
    print(f"Size: {db_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    print("Building GeneChat lookup database...")
    build_db()
    print("Done.")
