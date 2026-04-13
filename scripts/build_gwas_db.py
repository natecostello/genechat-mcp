"""Build GWAS Catalog SQLite table from the downloaded zip.

Thin wrapper around genechat.gwas module. For direct use:
    uv run python scripts/build_gwas_db.py [gwas-catalog.zip] [output.db]
"""

import sys
from pathlib import Path

from genechat.gwas import _default_gwas_db, _default_gwas_zip, build_gwas_db

if __name__ == "__main__":
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_gwas_zip()
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else _default_gwas_db()
    build_gwas_db(zip_path, db_path)
