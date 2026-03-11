"""Build the GeneChat SQLite lookup database from seed TSV files.

Reads TSVs from a seed directory and writes lookup_tables.db.
Idempotent: drops and recreates tables on each run.
"""

import csv
import io
import sqlite3
from pathlib import Path

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

TSV_FILES = {
    "genes": "genes_grch38.tsv",
    "pgx_drugs": "pgx_drugs.tsv",
    "pgx_variants": "pgx_variants.tsv",
    "prs_weights": "prs_weights.tsv",
}

EXPECTED_COLUMNS = {
    "genes": ["symbol", "name", "chrom", "start", "end", "strand"],
    "pgx_drugs": [
        "drug_name",
        "gene",
        "guideline_source",
        "guideline_url",
        "clinical_summary",
        "cpic_level",
        "pgx_testing",
    ],
    "pgx_variants": [
        "gene",
        "rsid",
        "chrom",
        "pos",
        "ref",
        "alt",
        "star_allele",
        "function_impact",
        "notes",
    ],
    "prs_weights": [
        "prs_id",
        "trait",
        "rsid",
        "chrom",
        "pos",
        "effect_allele",
        "weight",
    ],
}

INT_COLUMNS = {"start", "end", "pos"}
FLOAT_COLUMNS = {"weight"}


def load_tsv(path: Path) -> list[dict]:
    """Read a TSV file and return list of row dicts. Skips comment lines (#)."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]

    reader = csv.DictReader(io.StringIO("".join(lines)), delimiter="\t")
    rows = []
    for row in reader:
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


def build_db(seed_dir: Path, db_path: Path):
    """Build the SQLite database from seed TSVs.

    Args:
        seed_dir: Directory containing seed TSV files.
        db_path: Output database path.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for table_name, schema_sql in SCHEMAS.items():
        # Always drop and recreate the table to keep the build idempotent,
        # even if the corresponding TSV is missing.
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        cursor.executescript(schema_sql)

        tsv_file = seed_dir / TSV_FILES[table_name]
        if not tsv_file.exists():
            print(f"WARNING: {tsv_file} not found, created empty table {table_name}")
            continue

        rows = load_tsv(tsv_file)
        if not rows:
            print(f"WARNING: {tsv_file} has no data rows")
            continue

        # Validate TSV headers match expected columns
        expected = EXPECTED_COLUMNS[table_name]
        actual = list(rows[0].keys())
        if actual != expected:
            raise ValueError(
                f"{tsv_file.name}: header mismatch for table '{table_name}'. "
                f"Expected {expected}, got {actual}"
            )

        columns = expected
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
