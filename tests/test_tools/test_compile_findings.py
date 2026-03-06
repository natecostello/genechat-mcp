"""Tests for compile_findings tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.compile_findings import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["compile_findings"].fn


class TestCompileFindings:
    def test_variant_report(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs4149056")

        assert "Genomic Findings Summary" in result
        assert "rs4149056" in result
        assert "T/C" in result
        assert "SLCO1B1" in result
        assert "informational only" in result

    def test_gene_report(self, mock_engine, test_db, test_config):
        mock_engine.query_rsids.return_value = {}
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(genes="SLCO1B1")

        assert "Gene Summaries" in result
        assert "SLCO1B1" in result

    def test_empty_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn()
        assert "Please provide" in result

    def test_variant_not_found(self, mock_engine, test_db, test_config):
        mock_engine.query_rsids.return_value = {
            "rs9999999": [],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs9999999")

        assert "Not found" in result

    def test_combined_report(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(variants="rs4149056", genes="CYP2D6")

        assert "Variant Details" in result
        assert "Gene Summaries" in result
