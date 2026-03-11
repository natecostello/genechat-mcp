#!/usr/bin/env python3
"""Build the GeneChat SQLite lookup database from seed TSV files.

Thin wrapper — delegates to genechat.seeds.build_db.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "data" / "seed"
DB_PATH = REPO_ROOT / "src" / "genechat" / "data" / "lookup_tables.db"

if __name__ == "__main__":
    from genechat.seeds.build_db import build_db

    print("Building GeneChat lookup database...")
    build_db(seed_dir=SEED_DIR, db_path=DB_PATH)
    print("Done.")
