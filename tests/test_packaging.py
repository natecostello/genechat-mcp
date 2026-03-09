"""Tests for package data availability via importlib.resources."""

from importlib import resources
from pathlib import Path


class TestPackageData:
    def test_lookup_db_accessible_via_importlib(self):
        """lookup_tables.db is accessible via importlib.resources."""
        ref = resources.files("genechat") / "data" / "lookup_tables.db"
        with resources.as_file(ref) as p:
            assert Path(p).exists()
            assert Path(p).stat().st_size > 0

    def test_data_init_exists(self):
        """genechat.data is a proper Python package."""
        ref = resources.files("genechat") / "data" / "__init__.py"
        with resources.as_file(ref) as p:
            assert Path(p).exists()
