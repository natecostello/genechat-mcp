"""Tests for the GWAS module (gwas.py)."""

from pathlib import Path

from genechat.gwas import (
    _normalize_chrom,
    _parse_risk_allele,
    _parse_rsid,
    _safe_float,
    _safe_int,
    gwas_db_path,
    gwas_installed,
)


class TestParsingHelpers:
    def test_safe_float(self):
        assert _safe_float("1.5") == 1.5
        assert _safe_float("") is None
        assert _safe_float("NR") is None
        assert _safe_float("NS") is None
        assert _safe_float("not_a_number") is None

    def test_safe_int(self):
        assert _safe_int("42") == 42
        assert _safe_int("") is None
        assert _safe_int("abc") is None

    def test_parse_rsid(self):
        assert _parse_rsid("rs12345") == "rs12345"
        assert _parse_rsid("rs12345; rs67890") == "rs12345"
        assert _parse_rsid("rs12345-A") == "rs12345"
        assert _parse_rsid("") is None
        assert _parse_rsid("chr1:100") is None
        assert _parse_rsid("rsABC") is None  # non-numeric suffix rejected

    def test_parse_risk_allele(self):
        assert _parse_risk_allele("rs12345-A") == "A"
        assert _parse_risk_allele("rs12345-?") is None
        assert _parse_risk_allele("") is None
        assert _parse_risk_allele("no_dash") is None

    def test_normalize_chrom(self):
        assert _normalize_chrom("1") == "chr1"
        assert _normalize_chrom("22") == "chr22"
        assert _normalize_chrom("X") == "chrX"
        assert _normalize_chrom("MT") == "chrMT"
        assert _normalize_chrom("") is None
        assert _normalize_chrom("random") is None


class TestGwasDbPath:
    def test_returns_path(self):
        p = gwas_db_path()
        assert isinstance(p, Path)
        assert p.name == "gwas.db"

    def test_gwas_installed_false_when_no_db(self, monkeypatch):
        monkeypatch.setattr(
            "genechat.gwas.DEFAULT_GWAS_DB", Path("/nonexistent/gwas.db")
        )
        assert gwas_installed() is False
