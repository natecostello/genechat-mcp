"""Tests for query_gwas tool."""

from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_gwas import register


def _setup_tool(mock_engine, mock_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, mock_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_gwas"].fn


SAMPLE_GWAS_RESULT = {
    "rsid": "rs9939609",
    "chrom": "chr16",
    "pos": 53820527,
    "mapped_gene": "FTO",
    "trait": "Body mass index",
    "mapped_trait": "body mass index",
    "risk_allele": "A",
    "risk_allele_freq": 0.42,
    "p_value": 1e-120,
    "or_beta": 0.39,
    "ci_text": "[0.37-0.41]",
    "pubmed_id": "23263489",
    "first_author": "Locke AE",
    "study_accession": "GCST002461",
}


class TestQueryGwas:
    def test_search_by_trait(self, mock_engine, test_config):
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = [SAMPLE_GWAS_RESULT]
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass index")

        assert "FTO" in result
        assert "rs9939609" in result
        assert "Body mass index" in result
        assert "Locke AE" in result

    def test_search_by_gene(self, mock_engine, test_config):
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = [SAMPLE_GWAS_RESULT]
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(gene="FTO")

        assert "FTO" in result

    def test_no_input(self, mock_engine, test_config):
        mock_db = MagicMock()
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_no_gwas_table(self, mock_engine, test_config):
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = False
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="diabetes")
        assert "not loaded" in result

    def test_no_results(self, mock_engine, test_config):
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = []
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="nonexistent_trait_xyz")
        assert "No GWAS associations" in result


class TestGwasDeduplicate:
    def test_dedup_keeps_first_per_rsid(self, mock_engine, test_config):
        """Deduplication keeps the first (best p-value) per rsid."""
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        r1 = dict(SAMPLE_GWAS_RESULT, p_value=1e-120, trait="Body mass index")
        r2 = dict(SAMPLE_GWAS_RESULT, p_value=1e-50, trait="Obesity")
        r3 = {
            "rsid": "rs1421085",
            "mapped_gene": "FTO",
            "trait": "Waist circumference",
            "risk_allele": "C",
            "p_value": 1e-80,
            "or_beta": 0.25,
            "first_author": "Shungin D",
        }
        mock_db.search_gwas.return_value = [r1, r2, r3]
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass", deduplicate=True)

        # rs9939609 should appear once (first occurrence)
        assert result.count("rs9939609") == 1
        # rs1421085 should also appear
        assert "rs1421085" in result

    def test_dedup_disabled_shows_all(self, mock_engine, test_config):
        """With deduplicate=False, duplicate rsIDs show."""
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        r1 = dict(SAMPLE_GWAS_RESULT, trait="Body mass index")
        r2 = dict(SAMPLE_GWAS_RESULT, trait="Obesity")
        mock_db.search_gwas.return_value = [r1, r2]
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass", deduplicate=False)

        # rs9939609 should appear twice
        assert result.count("rs9939609") == 2


class TestGwasCheckVcf:
    def test_check_vcf_adds_genotype_column(self, mock_engine, test_config):
        """check_vcf=True should add Your Genotype column."""
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = [SAMPLE_GWAS_RESULT]
        mock_engine.query_rsids.return_value = {
            "rs9939609": [
                {
                    "genotype": {"display": "T/A", "zygosity": "heterozygous"},
                }
            ]
        }
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass index", check_vcf=True)

        assert "Your Genotype" in result
        assert "T/A (het)" in result
        # Author column should NOT be present when check_vcf is active with results
        assert "Locke AE" not in result

    def test_check_vcf_no_match_shows_dash(self, mock_engine, test_config):
        """check_vcf=True with no VCF match should show dash."""
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = [SAMPLE_GWAS_RESULT]
        mock_engine.query_rsids.return_value = {"rs9939609": []}
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass index", check_vcf=True)

        assert "Your Genotype" in result
        # Should show dash for missing genotype
        assert "—" in result

    def test_check_vcf_false_shows_author(self, mock_engine, test_config):
        """check_vcf=False should show Author column, not Genotype."""
        mock_db = MagicMock()
        mock_db.has_gwas_table.return_value = True
        mock_db.search_gwas.return_value = [SAMPLE_GWAS_RESULT]
        fn = _setup_tool(mock_engine, mock_db, test_config)
        result = fn(trait="body mass index", check_vcf=False)

        assert "Author" in result
        assert "Locke AE" in result
        assert "Your Genotype" not in result
