"""Tests for the enhanced-warning gene system."""

import sqlite3

import pytest

from genechat.seeds.build_db import build_db
from genechat.tools.formatting import _ENHANCED_WARNING, enhanced_warning_for_genes


@pytest.fixture
def warning_db(tmp_path):
    """Create a minimal lookup_tables.db with enhanced_warning_genes."""
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()

    # Minimal genes TSV
    (seed_dir / "genes_grch38.tsv").write_text(
        "symbol\tname\tchrom\tstart\tend\tstrand\n"
        "HTT\tHuntingtin\tchr4\t3074681\t3243960\t+\n"
        "SOD1\tSuperoxide dismutase 1\tchr21\t31659666\t31668931\t+\n"
        "BRCA1\tBRCA1 DNA repair\tchr17\t43044295\t43170245\t-\n"
    )
    # Empty tables for required TSVs
    (seed_dir / "pgx_drugs.tsv").write_text(
        "drug_name\tgene\tguideline_source\tguideline_url\tclinical_summary\tcpic_level\tpgx_testing\n"
    )
    (seed_dir / "pgx_variants.tsv").write_text(
        "gene\trsid\tchrom\tpos\tref\talt\tstar_allele\tfunction_impact\tnotes\n"
    )
    (seed_dir / "prs_weights.tsv").write_text(
        "prs_id\ttrait\trsid\tchrom\tpos\teffect_allele\tweight\n"
    )
    # Enhanced warning genes: HTT and SOD1 should be in the list
    (seed_dir / "enhanced_warning_genes.tsv").write_text(
        "symbol\nHTT\nSOD1\nPRNP\nMAPT\n"
    )

    db_path = tmp_path / "lookup_tables.db"
    build_db(seed_dir=seed_dir, db_path=db_path)
    return db_path


@pytest.fixture
def lookup(warning_db):
    """Create a LookupDB-like object from the test database."""
    conn = sqlite3.connect(warning_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")

    class FakeLookup:
        def __init__(self, conn):
            self._conn = conn

        def is_enhanced_warning_gene(self, symbol):
            row = self._conn.execute(
                "SELECT 1 FROM enhanced_warning_genes WHERE UPPER(symbol) = UPPER(?)",
                (symbol,),
            ).fetchone()
            return row is not None

    yield FakeLookup(conn)
    conn.close()


class TestIsEnhancedWarningGene:
    def test_known_warning_gene(self, lookup):
        assert lookup.is_enhanced_warning_gene("HTT") is True

    def test_known_warning_gene_case_insensitive(self, lookup):
        assert lookup.is_enhanced_warning_gene("htt") is True

    def test_actionable_gene_excluded(self, lookup):
        """BRCA1 is an ACMG SF gene — should not be in the warning list."""
        assert lookup.is_enhanced_warning_gene("BRCA1") is False

    def test_unknown_gene(self, lookup):
        assert lookup.is_enhanced_warning_gene("NOTAREALGENE") is False


class TestEnhancedWarningForGenes:
    def test_returns_warning_for_matching_gene(self, lookup):
        result = enhanced_warning_for_genes(lookup, {"HTT"})
        assert result == _ENHANCED_WARNING

    def test_returns_empty_for_non_matching(self, lookup):
        result = enhanced_warning_for_genes(lookup, {"BRCA1"})
        assert result == ""

    def test_returns_warning_if_any_gene_matches(self, lookup):
        result = enhanced_warning_for_genes(lookup, {"BRCA1", "SOD1", "TP53"})
        assert result == _ENHANCED_WARNING

    def test_returns_empty_for_empty_set(self, lookup):
        result = enhanced_warning_for_genes(lookup, set())
        assert result == ""

    def test_warning_only_returned_once(self, lookup):
        """Even with multiple warning genes, only one warning block is returned."""
        result = enhanced_warning_for_genes(lookup, {"HTT", "SOD1", "PRNP"})
        assert result.count("SENSITIVE RESULT") == 1


class TestWarningTableInBuildDb:
    def test_table_created(self, warning_db):
        with sqlite3.connect(warning_db) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            assert "enhanced_warning_genes" in tables

    def test_table_has_data(self, warning_db):
        with sqlite3.connect(warning_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM enhanced_warning_genes"
            ).fetchone()[0]
            assert count == 4  # HTT, SOD1, PRNP, MAPT

    def test_primary_key_enforced(self, warning_db):
        with sqlite3.connect(warning_db) as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO enhanced_warning_genes VALUES ('HTT')")


class TestFetchWarningGenes:
    def test_build_warning_list_intersection(self):
        from genechat.seeds.fetch_warning_genes import build_warning_list

        clinvar = {"HTT", "BRCA1", "SOD1", "LDLR", "PRNP"}
        hpo = {"HTT", "SOD1", "PRNP", "SOME_OTHER"}
        result = build_warning_list(clinvar, hpo)
        # HTT, SOD1, PRNP should be in (ClinVar ∩ HPO - ACMG)
        assert "HTT" in result
        assert "SOD1" in result
        assert "PRNP" in result
        # BRCA1 is only in ClinVar, not HPO → excluded by intersection
        assert "BRCA1" not in result
        # LDLR is only in ClinVar → excluded
        assert "LDLR" not in result

    def test_acmg_subtraction(self):
        from genechat.seeds.fetch_warning_genes import ACMG_SF_V3_3, build_warning_list

        # RYR1 is in ACMG SF — should be subtracted even if in both sets
        clinvar = {"HTT", "RYR1"}
        hpo = {"HTT", "RYR1"}
        result = build_warning_list(clinvar, hpo)
        assert "HTT" in result
        assert "RYR1" not in result
        assert "RYR1" in ACMG_SF_V3_3
