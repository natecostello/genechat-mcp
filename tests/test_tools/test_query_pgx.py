"""Tests for query_pgx tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_pgx import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_pgx"].fn


class TestQueryPgx:
    def test_drug_lookup(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_regions.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(drug="simvastatin")

        assert "Simvastatin" in result or "simvastatin" in result
        assert "SLCO1B1" in result
        assert "NOTE:" in result

    def test_gene_lookup(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_regions.return_value = [SAMPLE_VARIANT_SLCO1B1]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(gene="CYP2D6")

        assert "CYP2D6" in result

    def test_no_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_unknown_drug(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(drug="fakepill")
        assert "No pharmacogenomic data" in result
