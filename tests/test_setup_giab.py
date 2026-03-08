"""Unit tests for setup_giab.py helper functions.

Tests the pure functions (chrom prefix fix) without downloading any files.
"""

import sys
from pathlib import Path

# Add scripts directory to path so we can import setup_giab
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from setup_giab import fix_chrom


class TestFixChrom:
    def test_bare_number(self):
        assert fix_chrom("1") == "chr1"

    def test_bare_x(self):
        assert fix_chrom("X") == "chrX"

    def test_bare_mt(self):
        assert fix_chrom("MT") == "chrMT"

    def test_already_prefixed(self):
        assert fix_chrom("chr1") == "chr1"

    def test_already_prefixed_x(self):
        assert fix_chrom("chrX") == "chrX"

    def test_two_digit(self):
        assert fix_chrom("22") == "chr22"
