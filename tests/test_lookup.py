"""Tests for SQLite lookup layer."""

import pytest


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

    def test_by_drug_alias(self, test_db):
        results = test_db.search_pgx_by_drug("zocor")
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


class TestTraitVariants:
    def test_by_category(self, test_db):
        results = test_db.get_trait_variants(category="nutrigenomics")
        assert len(results) >= 1
        assert all(r["trait_category"] == "nutrigenomics" for r in results)

    def test_by_gene(self, test_db):
        results = test_db.get_trait_variants(gene="MTHFR")
        assert len(results) >= 1

    def test_by_trait(self, test_db):
        results = test_db.get_trait_variants(trait="caffeine")
        assert len(results) >= 1

    def test_no_filter(self, test_db):
        results = test_db.get_trait_variants()
        assert len(results) >= 20  # We seeded ~23


class TestCarrierGenes:
    def test_acmg_only(self, test_db):
        results = test_db.get_carrier_genes(acmg_only=True)
        assert len(results) >= 1
        assert all(r["acmg_recommended"] for r in results)

    def test_all_genes(self, test_db):
        all_genes = test_db.get_carrier_genes(acmg_only=False)
        acmg_genes = test_db.get_carrier_genes(acmg_only=True)
        assert len(all_genes) > len(acmg_genes)

    def test_by_condition(self, test_db):
        results = test_db.get_carrier_genes(condition="cystic")
        assert len(results) >= 1
        assert any("Cystic" in r["condition_name"] for r in results)


class TestPrsWeights:
    def test_by_trait(self, test_db):
        results = test_db.get_prs_weights(trait="coronary")
        assert len(results) >= 1

    def test_by_prs_id(self, test_db):
        results = test_db.get_prs_weights(prs_id="PGS000013")
        assert len(results) >= 1

    def test_unknown_trait(self, test_db):
        results = test_db.get_prs_weights(trait="faketraitthatdoesnotexist")
        assert results == []
