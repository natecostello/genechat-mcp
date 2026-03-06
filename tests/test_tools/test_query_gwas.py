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
