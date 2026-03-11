"""Seed data pipeline: fetch from APIs and rebuild lookup_tables.db.

This package can be run from both source checkouts (via scripts/) and pip
installs (via ``genechat install --seeds``).
"""

from genechat.seeds.build_db import build_db
from genechat.seeds.pipeline import run_pipeline

__all__ = ["build_db", "run_pipeline"]
