"""Tests for SQLite lookup layer."""

import sqlite3
from pathlib import Path

from genechat.config import AppConfig
from genechat.lookup import LookupDB


class TestGetGene:
    def test_known_gene(self, test_db):
        gene = test_db.get_gene("SLCO1B1")
        assert gene is not None
        assert gene["symbol"] == "SLCO1B1"
        assert gene["chrom"] == "chr12"

    def test_case_insensitive(self, test_db):
        gene = test_db.get_gene("slco1b1")
        assert gene is not None
        assert gene["symbol"] == "SLCO1B1"

    def test_unknown_gene(self, test_db):
        assert test_db.get_gene("FAKEGENE") is None


class TestGetGeneRegion:
    def test_region_with_padding(self, test_db):
        region = test_db.get_gene_region("BRCA1", padding=2000)
        assert region is not None
        assert region.startswith("chr17:")
        assert "-" in region

    def test_unknown_gene(self, test_db):
        assert test_db.get_gene_region("FAKEGENE") is None


class TestSearchPgx:
    def test_by_drug_name(self, test_db):
        results = test_db.search_pgx_by_drug("simvastatin")
        assert len(results) >= 1
        assert any(r["gene"] == "SLCO1B1" for r in results)

    def test_by_drug_case_insensitive(self, test_db):
        results = test_db.search_pgx_by_drug("Simvastatin")
        assert len(results) >= 1

    def test_by_gene(self, test_db):
        results = test_db.search_pgx_by_gene("CYP2D6")
        assert len(results) >= 1

    def test_unknown_drug(self, test_db):
        results = test_db.search_pgx_by_drug("fakemed")
        assert results == []


class TestPgxVariants:
    def test_known_gene(self, test_db):
        variants = test_db.get_pgx_variants("CYP2D6")
        assert len(variants) >= 1
        assert all(v["gene"] == "CYP2D6" for v in variants)

    def test_has_star_alleles(self, test_db):
        variants = test_db.get_pgx_variants("CYP2C9")
        assert any(v.get("star_allele") for v in variants)


class TestPrsWeights:
    def test_by_trait(self, test_db):
        results = test_db.get_prs_weights(trait="coronary")
        assert len(results) >= 1

    def test_by_prs_id(self, test_db):
        results = test_db.get_prs_weights(prs_id="PGS000010")
        assert len(results) >= 1

    def test_unknown_trait(self, test_db):
        results = test_db.get_prs_weights(trait="faketraitthatdoesnotexist")
        assert results == []


# ---------------------------------------------------------------------------
# GWAS ATTACH DATABASE support
# ---------------------------------------------------------------------------


class TestGwasAttach:
    def _create_lookup_db(self, path: Path):
        """Create a minimal lookup DB with genes table only (no GWAS)."""
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE genes (symbol TEXT PRIMARY KEY, name TEXT, "
            "chrom TEXT, start INTEGER, end INTEGER, strand TEXT)"
        )
        conn.execute(
            "INSERT INTO genes VALUES ('TP53', 'tumor protein p53', "
            "'chr17', 7668421, 7687490, '-')"
        )
        conn.commit()
        conn.close()

    def _create_gwas_db(self, path: Path):
        """Create a minimal standalone GWAS DB."""
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE gwas_associations ("
            "rsid TEXT, chrom TEXT, pos INTEGER, mapped_gene TEXT, "
            "trait TEXT NOT NULL, mapped_trait TEXT, risk_allele TEXT, "
            "risk_allele_freq REAL, p_value REAL, or_beta REAL, "
            "ci_text TEXT, pubmed_id TEXT, first_author TEXT, study_accession TEXT)"
        )
        conn.execute(
            "INSERT INTO gwas_associations VALUES ("
            "'rs9939609', 'chr16', 53820527, 'FTO', "
            "'Body mass index', 'body mass index', 'A', "
            "0.42, 1e-50, 1.3, NULL, '17658951', 'Frayling', 'GCST000025')"
        )
        conn.commit()
        conn.close()

    def test_attach_separate_gwas_db(self, tmp_path):
        """LookupDB attaches standalone gwas.db and queries work."""
        lookup_path = tmp_path / "lookup_tables.db"
        gwas_path = tmp_path / "gwas.db"
        self._create_lookup_db(lookup_path)
        self._create_gwas_db(gwas_path)

        config = AppConfig(
            databases={"lookup_db": str(lookup_path), "gwas_db": str(gwas_path)}
        )
        db = LookupDB(config)
        try:
            assert db.has_gwas_table()
            results = db.search_gwas(trait="body mass")
            assert len(results) == 1
            assert results[0]["rsid"] == "rs9939609"
        finally:
            db.close()

    def test_no_gwas_db_returns_empty(self, tmp_path):
        """Without GWAS DB, has_gwas_table returns False and searches return []."""
        lookup_path = tmp_path / "lookup_tables.db"
        self._create_lookup_db(lookup_path)

        config = AppConfig(
            databases={
                "lookup_db": str(lookup_path),
                "gwas_db": str(tmp_path / "nonexistent.db"),
            }
        )
        db = LookupDB(config)
        try:
            assert not db.has_gwas_table()
            assert db.search_gwas(trait="anything") == []
        finally:
            db.close()

    def test_legacy_gwas_in_main_db(self, tmp_path):
        """When GWAS table is in the main DB (legacy layout), no ATTACH needed."""
        lookup_path = tmp_path / "lookup_tables.db"
        conn = sqlite3.connect(str(lookup_path))
        conn.execute(
            "CREATE TABLE genes (symbol TEXT PRIMARY KEY, name TEXT, "
            "chrom TEXT, start INTEGER, end INTEGER, strand TEXT)"
        )
        conn.execute(
            "CREATE TABLE gwas_associations ("
            "rsid TEXT, chrom TEXT, pos INTEGER, mapped_gene TEXT, "
            "trait TEXT NOT NULL, mapped_trait TEXT, risk_allele TEXT, "
            "risk_allele_freq REAL, p_value REAL, or_beta REAL, "
            "ci_text TEXT, pubmed_id TEXT, first_author TEXT, study_accession TEXT)"
        )
        conn.execute(
            "INSERT INTO gwas_associations VALUES ("
            "'rs1234', 'chr1', 100, 'GENE1', 'Test trait', NULL, "
            "'A', NULL, 1e-8, NULL, NULL, NULL, NULL, NULL)"
        )
        conn.commit()
        conn.close()

        config = AppConfig(databases={"lookup_db": str(lookup_path)})
        db = LookupDB(config)
        try:
            assert db.has_gwas_table()
            results = db.search_gwas(trait="Test")
            assert len(results) == 1
        finally:
            db.close()

    def test_corrupt_gwas_db_gracefully_skipped(self, tmp_path):
        """Corrupt GWAS DB doesn't prevent lookup from working."""
        lookup_path = tmp_path / "lookup_tables.db"
        self._create_lookup_db(lookup_path)
        gwas_path = tmp_path / "gwas.db"
        gwas_path.write_bytes(b"not a sqlite database")

        config = AppConfig(
            databases={"lookup_db": str(lookup_path), "gwas_db": str(gwas_path)}
        )
        db = LookupDB(config)
        try:
            assert not db.has_gwas_table()
            # Core lookup still works
            gene = db.get_gene("TP53")
            assert gene is not None
        finally:
            db.close()

    def test_gwas_traits_for_gene(self, tmp_path):
        """gwas_traits_for_gene works with attached DB."""
        lookup_path = tmp_path / "lookup_tables.db"
        gwas_path = tmp_path / "gwas.db"
        self._create_lookup_db(lookup_path)
        self._create_gwas_db(gwas_path)

        config = AppConfig(
            databases={"lookup_db": str(lookup_path), "gwas_db": str(gwas_path)}
        )
        db = LookupDB(config)
        try:
            traits = db.gwas_traits_for_gene("FTO")
            assert len(traits) >= 1
            assert traits[0]["trait"] == "Body mass index"
        finally:
            db.close()
