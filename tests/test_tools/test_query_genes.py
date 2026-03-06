"""Tests for query_genes batch gene tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_genes import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_genes"].fn


class TestQueryGenes:
    def test_multiple_genes(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR, SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_regions.return_value = [
            SAMPLE_VARIANT_SLCO1B1,
            SAMPLE_VARIANT_CFTR,
        ]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1,CFTR")

        assert "Multi-Gene Query" in result
        assert "SLCO1B1" in result
        assert "CFTR" in result

    def test_unknown_gene(self, mock_engine, test_db, test_config):
        mock_engine.query_regions.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="FAKEGENE123")

        assert "None of the genes found" in result

    def test_empty_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="")
        assert "Please provide" in result

    def test_too_many_genes(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        many = ",".join(f"GENE{i}" for i in range(21))
        result = fn(genes=many)
        assert "Too many" in result

    def test_no_notable_variants(self, mock_engine, test_db, test_config):
        """Gene found but no notable variants (no rsID, no ClinVar, no annotation)."""
        unannotated_no_rsid = {
            "chrom": "chr12",
            "pos": 21178700,
            "rsid": None,
            "ref": "A",
            "alt": "G",
            "genotype": {"display": "A/G", "zygosity": "heterozygous"},
            "annotation": {},
            "clinvar": {},
            "population_freq": {},
        }
        mock_engine.query_regions.return_value = [unannotated_no_rsid]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1")

        assert "No notable variants" in result
