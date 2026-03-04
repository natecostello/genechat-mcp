"""Tests for query_clinvar tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_clinvar import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_clinvar"].fn


class TestQueryClinvar:
    def test_pathogenic_found(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_clinvar.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(significance="Pathogenic")

        assert "Pathogenic" in result
        assert "CFTR" in result
        assert "NOTE:" in result

    def test_no_results(self, mock_engine, test_db, test_config):
        mock_engine.query_clinvar.return_value = []
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(significance="Pathogenic")

        assert "No" in result
        assert "not guarantee" in result

    def test_with_gene_filter(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR

        mock_engine.query_clinvar.return_value = [SAMPLE_VARIANT_CFTR]
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(significance="Pathogenic", gene="CFTR")

        assert "CFTR" in result
