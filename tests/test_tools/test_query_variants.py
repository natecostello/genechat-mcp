"""Tests for query_variants batch rsID tool."""

from mcp.server.fastmcp import FastMCP

from genechat.tools.query_variants import register


def _setup_tool(mock_engine, test_db, test_config):
    mcp = FastMCP("test")
    register(mcp, mock_engine, test_db, test_config)
    tools = mcp._tool_manager._tools
    return tools["query_variants"].fn


class TestQueryVariants:
    def test_batch_found(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_CFTR, SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
            "rs113993960": [SAMPLE_VARIANT_CFTR],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(rsids="rs4149056,rs113993960")

        assert "rs4149056" in result
        assert "rs113993960" in result
        assert "2/2 found" in result
        assert "NOTE:" in result

    def test_partial_found(self, mock_engine, test_db, test_config):
        from tests.conftest import SAMPLE_VARIANT_SLCO1B1

        mock_engine.query_rsids.return_value = {
            "rs4149056": [SAMPLE_VARIANT_SLCO1B1],
            "rs9999999": [],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(rsids="rs4149056,rs9999999")

        assert "1/2 found" in result
        assert "rs9999999" in result
        assert "Not Found" in result

    def test_none_found(self, mock_engine, test_db, test_config):
        mock_engine.query_rsids.return_value = {
            "rs9999999": [],
        }
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(rsids="rs9999999")

        assert "0/1 found" in result

    def test_empty_input(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        result = fn(rsids="")
        assert "Please provide" in result

    def test_too_many(self, mock_engine, test_db, test_config):
        fn = _setup_tool(mock_engine, test_db, test_config)
        many = ",".join(f"rs{i}" for i in range(51))
        result = fn(rsids=many)
        assert "Too many" in result
