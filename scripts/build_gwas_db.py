"""Build GWAS Catalog SQLite table from the downloaded zip.

Thin wrapper around genechat.gwas module. For direct use:
    uv run python scripts/build_gwas_db.py [gwas-catalog.zip] [output.db]
"""

import sys
from pathlib import Path

from genechat.gwas import DEFAULT_GWAS_DB, DEFAULT_GWAS_ZIP, build_gwas_db

if __name__ == "__main__":
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GWAS_ZIP
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_GWAS_DB
    build_gwas_db(zip_path, db_path)
