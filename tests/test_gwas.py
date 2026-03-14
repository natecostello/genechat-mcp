"""Tests for the GWAS module (gwas.py)."""

import zipfile
from pathlib import Path

from genechat.gwas import (
    _normalize_chrom,
    _parse_risk_allele,
    _parse_rsid,
    _safe_float,
    _safe_int,
    build_gwas_db,
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


class TestGwasZipCleanup:
    _GWAS_TSV = (
        "DATE ADDED TO CATALOG\tPUBMEDID\tFIRST AUTHOR\tDATE\tJOURNAL\t"
        "LINK\tSTUDY\tDISEASE/TRAIT\tINITIAL SAMPLE SIZE\tREPLICATION SAMPLE SIZE\t"
        "REGION\tCHR_ID\tCHR_POS\tREPORTED GENE(S)\tMAPPED_GENE\t"
        "UPSTREAM_GENE_ID\tDOWNSTREAM_GENE_ID\tSNP_GENE_IDS\t"
        "UPSTREAM_GENE_DISTANCE\tDOWNSTREAM_GENE_DISTANCE\t"
        "STRONGEST SNP-RISK ALLELE\tSNPS\tMERGED\tSNP_ID_CURRENT\tCONTEXT\t"
        "INTERGENIC\tRISK ALLELE FREQUENCY\tP-VALUE\tPVALUE_MLOG\t"
        "P-VALUE (TEXT)\tOR or BETA\t95% CI (TEXT)\tPLATFORM [SNPS PASSING QC]\t"
        "CNV\tMAPPED_TRAIT\tMAPPED_TRAIT_URI\tSTUDY ACCESSION\t"
        "GENOTYPING TECHNOLOGY\n"
        "2024-01-01\t12345\tSmith\t2024\tNature\tlink\tstudy\tTest Trait\t"
        "1000 cases\t\tregion\t1\t100\tGENE1\tGENE1\t\t\t\t\t\t"
        "rs12345-A\trs12345\t0\t\t\t0\t0.05\t1e-8\t8\t\t1.5\t1.2-1.8\t"
        "platform\t0\ttest trait\turi\tGCST000001\ttechnology\n"
    )

    def test_default_zip_deleted_after_build(self, tmp_path, monkeypatch, capsys):
        """Verify default cache zip is deleted after successful DB build."""
        zip_path = tmp_path / "gwas.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("gwas-catalog.tsv", self._GWAS_TSV)

        # Point DEFAULT_GWAS_ZIP to our test zip so it's treated as default
        monkeypatch.setattr("genechat.gwas.DEFAULT_GWAS_ZIP", zip_path)

        db_path = tmp_path / "gwas.db"
        build_gwas_db(db_path=db_path)  # zip_path=None → uses default

        assert db_path.exists()
        assert not zip_path.exists()
        assert "freed" in capsys.readouterr().out

    def test_custom_zip_preserved_after_build(self, tmp_path, capsys):
        """Verify caller-provided zip is NOT deleted after build."""
        zip_path = tmp_path / "custom.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("gwas-catalog.tsv", self._GWAS_TSV)

        db_path = tmp_path / "gwas.db"
        build_gwas_db(zip_path=zip_path, db_path=db_path)

        assert db_path.exists()
        assert zip_path.exists()  # NOT deleted
