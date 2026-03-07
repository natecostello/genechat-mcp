"""Build GWAS Catalog SQLite table from the downloaded zip.

Downloads: https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/
           gwas-catalog-associations_ontology-annotated-full.zip

Usage:
    uv run python scripts/build_gwas_db.py [data/gwas_catalog/gwas-catalog-associations.zip]

Produces (or updates) the lookup database with a `gwas_associations` table.
"""

import csv
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ZIP = REPO_ROOT / "data" / "gwas_catalog" / "gwas-catalog-associations.zip"
DB_PATH = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"

# Columns we extract (index in GWAS catalog TSV)
COL_TRAIT = 7  # DISEASE/TRAIT
COL_CHR = 11  # CHR_ID
COL_POS = 12  # CHR_POS
COL_MAPPED_GENE = 14  # MAPPED_GENE
COL_RISK_ALLELE = 20  # STRONGEST SNP-RISK ALLELE
COL_SNPS = 21  # SNPS (rsID)
COL_RAF = 26  # RISK ALLELE FREQUENCY
COL_PVALUE = 27  # P-VALUE
COL_OR_BETA = 30  # OR or BETA
COL_CI = 31  # 95% CI (TEXT)
COL_MAPPED_TRAIT = 34  # MAPPED_TRAIT (EFO-mapped)
COL_PUBMEDID = 1  # PUBMEDID
COL_FIRST_AUTHOR = 2  # FIRST AUTHOR
COL_STUDY_ACC = 36  # STUDY ACCESSION


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS gwas_associations (
    rsid TEXT,
    chrom TEXT,
    pos INTEGER,
    mapped_gene TEXT,
    trait TEXT NOT NULL,
    mapped_trait TEXT,
    risk_allele TEXT,
    risk_allele_freq REAL,
    p_value REAL,
    or_beta REAL,
    ci_text TEXT,
    pubmed_id TEXT,
    first_author TEXT,
    study_accession TEXT
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_gwas_rsid ON gwas_associations(rsid)",
    "CREATE INDEX IF NOT EXISTS idx_gwas_gene ON gwas_associations(mapped_gene)",
    "CREATE INDEX IF NOT EXISTS idx_gwas_trait ON gwas_associations(trait)",
    "CREATE INDEX IF NOT EXISTS idx_gwas_mapped_trait ON gwas_associations(mapped_trait)",
]


def _safe_float(val: str) -> float | None:
    """Parse a float from GWAS catalog, returning None for missing/invalid."""
    if not val or val == "NR" or val == "NS":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _safe_int(val: str) -> int | None:
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def _parse_rsid(snps_field: str) -> str | None:
    """Extract rsID from SNPS column (may contain 'rs12345' or 'rs12345-A')."""
    if not snps_field:
        return None
    # Take first rsID if multiple
    for part in snps_field.split(";"):
        part = part.strip().split("-")[0]
        if part.startswith("rs"):
            return part
    return None


def _parse_risk_allele(field: str) -> str | None:
    """Extract risk allele from 'rsXXXXX-A' format."""
    if not field or "-" not in field:
        return None
    parts = field.split("-", 1)
    allele = parts[1].strip()
    if allele and allele != "?" and len(allele) <= 10:
        return allele
    return None


def _normalize_chrom(chrom: str) -> str | None:
    """Normalize chromosome to chr-prefix format."""
    if not chrom:
        return None
    chrom = chrom.strip()
    if chrom in ("X", "Y", "MT"):
        return f"chr{chrom}"
    try:
        n = int(chrom)
        if 1 <= n <= 22:
            return f"chr{n}"
    except ValueError:
        pass
    return None


GWAS_URL = "https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/gwas-catalog-associations_ontology-annotated-full.zip"


def _download_gwas(zip_path: Path) -> None:
    """Download the GWAS Catalog associations zip (atomic with temp file)."""
    import urllib.request

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = zip_path.with_suffix(".tmp")
    print("Downloading GWAS Catalog (~58 MB)...")
    try:
        urllib.request.urlretrieve(GWAS_URL, tmp_path)
        os.replace(tmp_path, zip_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    print(f"Downloaded: {zip_path}")


def build_gwas_db(zip_path: Path, db_path: Path) -> int:
    """Process GWAS catalog zip into SQLite. Returns row count."""
    if not zip_path.exists():
        _download_gwas(zip_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS gwas_associations")
    conn.execute(CREATE_TABLE)

    rows_inserted = 0
    rows_skipped = 0

    with zipfile.ZipFile(str(zip_path)) as z:
        tsv_name = z.namelist()[0]
        with z.open(tsv_name) as f:
            import io

            reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t")
            next(reader)  # skip header

            batch = []
            for row in reader:
                if len(row) < 35:
                    rows_skipped += 1
                    continue

                trait = row[COL_TRAIT].strip()
                if not trait:
                    rows_skipped += 1
                    continue

                rsid = _parse_rsid(row[COL_SNPS])
                chrom = _normalize_chrom(row[COL_CHR])
                pos = _safe_int(row[COL_POS])
                mapped_gene = row[COL_MAPPED_GENE].strip() or None
                mapped_trait = row[COL_MAPPED_TRAIT].strip() or None
                risk_allele = _parse_risk_allele(row[COL_RISK_ALLELE])
                raf = _safe_float(row[COL_RAF])
                pvalue = _safe_float(row[COL_PVALUE])
                or_beta = _safe_float(row[COL_OR_BETA])
                ci = row[COL_CI].strip() or None
                pmid = row[COL_PUBMEDID].strip() or None
                author = row[COL_FIRST_AUTHOR].strip() or None
                study_acc = (
                    row[COL_STUDY_ACC].strip() if len(row) > COL_STUDY_ACC else None
                )

                batch.append(
                    (
                        rsid,
                        chrom,
                        pos,
                        mapped_gene,
                        trait,
                        mapped_trait,
                        risk_allele,
                        raf,
                        pvalue,
                        or_beta,
                        ci,
                        pmid,
                        author,
                        study_acc,
                    )
                )
                rows_inserted += 1

                if len(batch) >= 10000:
                    conn.executemany(
                        "INSERT INTO gwas_associations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        batch,
                    )
                    batch.clear()

            if batch:
                conn.executemany(
                    "INSERT INTO gwas_associations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    batch,
                )

    for idx_sql in CREATE_INDEXES:
        conn.execute(idx_sql)

    conn.commit()
    conn.close()

    print(f"GWAS associations loaded: {rows_inserted:,}")
    if rows_skipped:
        print(f"Rows skipped (malformed): {rows_skipped:,}")
    return rows_inserted


if __name__ == "__main__":
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ZIP
    build_gwas_db(zip_path, DB_PATH)
