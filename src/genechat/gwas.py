"""GWAS Catalog download and SQLite build.

Downloads from EBI FTP and builds a standalone gwas.db file.
This module is used by both the CLI (`genechat install --gwas`)
and the build script (`scripts/build_gwas_db.py`).
"""

import csv
import io
import os
import re
import sqlite3
import zipfile
from pathlib import Path

from genechat.config import get_data_dir

GWAS_URL = (
    "https://ftp.ebi.ac.uk/pub/databases/gwas/releases/latest/"
    "gwas-catalog-associations_ontology-annotated-full.zip"
)

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


_RSID_RE = re.compile(r"^rs\d+$")


def _parse_rsid(snps_field: str) -> str | None:
    if not snps_field:
        return None
    for part in snps_field.split(";"):
        part = part.strip().split("-")[0]
        if _RSID_RE.match(part):
            return part
    return None


def _parse_risk_allele(field: str) -> str | None:
    if not field or "-" not in field:
        return None
    parts = field.split("-", 1)
    allele = parts[1].strip()
    if allele and allele != "?" and len(allele) <= 10:
        return allele
    return None


def _normalize_chrom(chrom: str) -> str | None:
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


def _default_gwas_db() -> Path:
    return get_data_dir() / "gwas.db"


def _default_gwas_zip() -> Path:
    return get_data_dir() / "gwas-catalog-associations.zip"


def download_gwas_catalog(dest_path: Path | None = None) -> Path:
    """Download the GWAS Catalog associations zip. Returns path to the zip."""
    from genechat.download import download_file

    zip_path = dest_path or _default_gwas_zip()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    download_file(GWAS_URL, zip_path, "GWAS Catalog")
    return zip_path


def build_gwas_db(zip_path: Path | None = None, db_path: Path | None = None) -> int:
    """Process GWAS catalog zip into a standalone SQLite DB. Returns row count.

    If zip_path does not exist, downloads it first.
    Deletes the zip after a successful build when using the default cache path.
    """
    using_default_zip = zip_path is None
    zip_path = zip_path or _default_gwas_zip()
    db_path = db_path or _default_gwas_db()

    if not zip_path.exists():
        download_gwas_catalog(zip_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = db_path.with_suffix(".tmp.db")
    tmp_db.unlink(missing_ok=True)  # Remove stale temp from interrupted builds
    conn = sqlite3.connect(str(tmp_db))
    try:
        conn.execute("DROP TABLE IF EXISTS gwas_associations")
        conn.execute(CREATE_TABLE)

        rows_inserted = 0
        rows_skipped = 0

        with zipfile.ZipFile(str(zip_path)) as z:
            tsv_name = z.namelist()[0]
            with z.open(tsv_name) as f:
                reader = csv.reader(
                    io.TextIOWrapper(f, encoding="utf-8"), delimiter="\t"
                )
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

                    batch.append(
                        (
                            _parse_rsid(row[COL_SNPS]),
                            _normalize_chrom(row[COL_CHR]),
                            _safe_int(row[COL_POS]),
                            row[COL_MAPPED_GENE].strip() or None,
                            trait,
                            row[COL_MAPPED_TRAIT].strip() or None,
                            _parse_risk_allele(row[COL_RISK_ALLELE]),
                            _safe_float(row[COL_RAF]),
                            _safe_float(row[COL_PVALUE]),
                            _safe_float(row[COL_OR_BETA]),
                            row[COL_CI].strip() or None,
                            row[COL_PUBMEDID].strip() or None,
                            row[COL_FIRST_AUTHOR].strip() or None,
                            (
                                row[COL_STUDY_ACC].strip()
                                if len(row) > COL_STUDY_ACC
                                else None
                            ),
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
    except Exception:
        conn.close()
        tmp_db.unlink(missing_ok=True)
        raise
    conn.close()

    # Atomic replace — only after successful build
    os.replace(tmp_db, db_path)

    # Clean up zip to free disk space (~58 MB) — only for default cache path
    if using_default_zip and zip_path.exists():
        freed = zip_path.stat().st_size
        zip_path.unlink()
        from genechat.progress import format_size

        print(f"  Cleaned up GWAS zip ({format_size(freed)} freed)")

    print(f"GWAS associations loaded: {rows_inserted:,}")
    if rows_skipped:
        print(f"Rows skipped (malformed): {rows_skipped:,}")
    return rows_inserted


def gwas_db_path() -> Path:
    """Return the default GWAS DB path."""
    return _default_gwas_db()


def gwas_installed() -> bool:
    """Check if the GWAS DB has been downloaded and built."""
    return _default_gwas_db().exists()
